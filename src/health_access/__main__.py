import logging
import geopandas as gpd
import sys
import yaml
import typer
from pathlib import Path

from health_access.preprocessing.transform import transform_projections
from health_access.preprocessing.standardize import standardize_data
from health_access.clustering.model import apply_clustering
from health_access.clustering.visualization import create_cluster_map

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})

@app.command()
def main(
    skip_transform: bool = typer.Option(False, "--skip-transform", "-st", help="Skip projection transformation (use already transformed data)."),
    skip_clustering: bool = typer.Option(False, "--skip-clustering", "-sc", help="Skip clustering step."),
    n_clusters: int = typer.Option(None, "--n-clusters", "-n", help="Number of KMeans clusters (overrides config). Default: 5."),
    show_legend: bool = typer.Option(False, "--legend", "-l", help="Add a legend to the cluster map."),
):
    
    # Loading Configuration
    project_root = Path(__file__).resolve().parents[2] 
    config_path = project_root / "config" / "settings.yaml"
    
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

   # Resolve paths relative to project root
    raw_dir = project_root / config['paths']['raw_dir']
    transformed_dir = project_root / config['paths']['transformed_dir']
    census_input = project_root / config['paths']['census_input']
    census_output = project_root / config['paths']['census_output']
    clustered_output = project_root / config['paths']['clustered_output']

    # Override config with CLI arguments if provided
    if n_clusters is not None:
        config['clustering']['n_clusters'] = n_clusters
        logger.info(f"Using n_clusters={n_clusters} from CLI.")    

   # 1. PREPROCESSING: Transform all raw files to EPSG:5514
    if not skip_transform:
        logger.info("Starting Projection Transformation...")
        transform_projections(
            raw_dir, 
            transformed_dir, 
            target_epsg=config['projection']['target_epsg']
        )
    else:
        logger.info("Skipping transform (--skip-transform set).")


    # PREPROCESSING CONT: Calculate New Census Variables
    # We only run this if the file was successfully created in the prior step
    if census_input.exists():
        logger.info("Starting Census Variable Calculation...")
        standardize_data(census_input, census_output)
    else:
        logger.error(f"Census input file not found at {census_input}. Skipping calculation.")

    logger.info("Data preprocessing complete!")

    # 2. CLUSTERING - We only run this if the file was successfully created in the prior step, and if the user didn't specify to skip clustering
    if not skip_clustering: # We check for the file first.
        if census_output.exists():
            logger.info("Starting Clustering...")

            gdf_vars = gpd.read_file(census_output)
            gdf_clustered = apply_clustering(gdf_vars, config)

            gdf_clustered.to_file(clustered_output, driver="GeoJSON")
            logger.info(f"Clustered data saved to: {clustered_output}")
        
        else:
            logger.error("Variables file missing. Skipping clustering.")

    # CLUSTERING CONT - VISUALIZATION
        logger.info("Generating cluster map...")
        saved_map_path = create_cluster_map(gdf_clustered, config, project_root, show_legend=show_legend)
        logger.info(f"Visualization saved to: {saved_map_path}")

    else:
        logger.info("Skipping clustering (--skip-clustering set).")
    # logger.error("Variables file missing. Skipping Clustering and Visualization.")

    logger.info("Complete! :) ")


if __name__ == "__main__":
    app()
