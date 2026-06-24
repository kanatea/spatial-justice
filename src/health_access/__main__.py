import logging
import geopandas as gpd
import sys
#import yaml
import typer
from pathlib import Path

from health_access.a_preprocessing import transform_projections, standardize_data
from health_access.b_clustering import apply_clustering
from health_access.visualization import create_cluster_map

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})

CLUSTERING_FEATURES = [
    "POP_DENS", "PCT_WOMEN", "PCT_CHILD", 
    "PCT_WORKING", "PCT_ELDERLY", "AGEING_INDEX", 
    "DEPENDENCY", "NATURAL_INC_RATE", "MIG_BAL_RATE"
]


@app.command()
def main(
    filename: str = typer.Option(
        "admin_boundaries_ORP.geojson",
        "--input",
        "-i",
        help="GeoJSON filename inside the data/raw/ folder.",
    ),
    target_epsg: int = typer.Option(
        5514,
        "--epsg_projection",
        "-proj",
        help="EPSG Projection",
    ),
    n_clusters: int = typer.Option(
        5, 
        "--n-clusters", 
        "-n", 
        help="Number of KMeans clusters (overrides config). Default: 5."
        ),
    random_state: int = typer.Option(
        42, 
        "--random_state", 
        "-rs", 
        help="Randomization seed for replicability (overrides config). Default: 42."
        ),    
    skip_transform: bool = typer.Option(
        False, 
        "--skip-transform", 
        "-st", 
        help="Skip projection transformation (use already transformed data)."
        ),
    skip_standardize: bool = typer.Option(
        False, 
        "--skip_standardize",
        "-ss",
        help="Skip variable standardization."
    ),
    skip_clustering: bool = typer.Option(
        False, 
        "--skip-clustering", 
        "-sc", 
        help="Skip clustering step."
        ),
    show_legend: bool = typer.Option(
        False, 
        "--legend", 
        "-l", 
        help="Add a legend to the cluster map."
        ),
):
    
    # Loading Configuration
    project_root = Path(__file__).resolve().parents[2] 

   # Resolve paths relative to project root
    raw_dir = project_root / "data/raw"
    transformed_dir = project_root / "data/transformed"
    input_file = transformed_dir / filename
    census_output = transformed_dir / "data_variables.geojson"
    clustered_output = project_root / f"data/processed/clusters_{n_clusters}.geojson"

   # 1. PREPROCESSING: Transform all raw files to EPSG:5514
    if not skip_transform:
        logger.info("Starting Projection Transformation...")
        transform_projections(
            raw_dir, 
            transformed_dir, 
            target_epsg
        )
    else:
        logger.info("Skipping transform.")


    # PREPROCESSING CONT: Calculate New Census Variables
    # We only run this if the file was successfully created in the prior step
    if not skip_standardize:
        if input_file.exists():
            logger.info("Starting Census Variable Calculation...")
            standardize_data(input_file, census_output)
        else:
            logger.error(f"Census input file not found at {input_file}. Skipping calculation.")

    else:
        logger.info("Data preprocessing complete!")

    # 2. CLUSTERING - We only run this if the file was successfully created in the prior step, and if the user didn't specify to skip clustering
    if not skip_clustering: # We check for the file first.
        if census_output.exists():
            logger.info(f"Starting Clustering with {n_clusters} clusters...")
            gdf_vars = gpd.read_file(census_output)

            gdf_clustered = apply_clustering(
                gdf_vars,
                features = CLUSTERING_FEATURES,
                n_clusters = n_clusters,
                random_state = random_state
            )

            gdf_clustered.to_file(clustered_output, driver="GeoJSON")
            logger.info(f"Clustered data saved to: {clustered_output}")
        
        else:
            logger.error("Variables file missing. Skipping clustering.")

    # CLUSTERING CONT - VISUALIZATION
        logger.info("Generating cluster map...")
        saved_map_path = create_cluster_map(
            gdf_clustered,
            project_root = project_root, 
            n_clusters = n_clusters,
            show_legend=show_legend,
            title="ORP Clusters based on 9 Selected Variables"
        )
        logger.info(f"Visualization saved to: {saved_map_path}")

    else:
        logger.info("Skipping clustering (--skip-clustering set).")
    # logger.error("Variables file missing. Skipping Clustering and Visualization.")

    logger.info("Complete! :) ")


if __name__ == "__main__":
    app()
