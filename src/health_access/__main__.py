import logging
import geopandas as gpd
import sys
import typer
from pathlib import Path

from health_access.a_preprocessing import transform_projections, standardize_data, aggregate_poi
from health_access.b_clustering import apply_clustering, export_clusters_separately
# later import the Moran's I
from health_access.d_analysis_accessibility import calculate_health_accessibility
from health_access.visualization import create_cluster_map, plot_accessibility_map, plot_access_vs_socio, plot_network_accessibility

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
    "DEPENDENCY", "NATURAL_INC_RATE", "MIG_BAL_RATE" #,
    # "COUNT_EMERGENCY", "COUNT_MATERNITY", "COUNT_TOTAL_CARE"
]

# Define the mapping for the point files
POINT_MAPPING = {
    "OD_emergency_care.geojson": "COUNT_EMERGENCY",
    "OD_maternity_care.geojson": "COUNT_MATERNITY"
}


@app.command()
def main(
    filename: str = typer.Option(
        "admin_boundaries_ORP.geojson",
        "--input",
        "-i",
        help="GeoJSON filename inside the data/transformed/ folder to be used for clustering.",
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
    skip_accessibility: bool = typer.Option( # define
        False, 
        "--skip-accessibility", 
        "-sa", 
        help="Skip accessibility analysis step."
        ),
    show_legend: bool = typer.Option(
        False, 
        "--legend", 
        "-l", 
        help="Add a legend to the cluster map." # is this just for the cluster map or all legends?
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
    access_output = project_root / f"data/processed/accessibility_{n_clusters}.geojson"

   # 1. PREPROCESSING: Transform (reproject) all raw files to EPSG:5514
    if not skip_transform:
        logger.info("Starting Projection Transformation...")
        transform_projections(
            raw_dir, 
            transformed_dir, 
            target_epsg
        )
    else:
        logger.info("Skipping transform.")


    # PREPROCESSING CONT: Calculate Standardized Census Variables + Add POI 
    # We only run this if the file was successfully created in the prior step
    if not skip_standardize:
        if input_file.exists():
            logger.info("Starting Census Variable Standardization...")
            standardize_data(input_file, census_output)

            # We load the GDF here so we can pass it to the aggregator
            gdf = gpd.read_file(census_output)

            # AGGREGATE POINTS
            logger.info("Aggregating point data...")
            gdf = aggregate_poi(gdf, POINT_MAPPING, transformed_dir)
            
            # Save the updated GDF to the variables file
            gdf.to_file(census_output, driver="GeoJSON")

        else:
            logger.error(f"Input file not found at {input_file}. Skipping calculation.")

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

            clusters_dir = project_root / "data/processed/clusters"
            clusters_dir.mkdir(parents=True, exist_ok=True)
            export_clusters_separately(gdf_clustered, clusters_dir)
        
        else:
            logger.error("Variables file missing. Skipping clustering.")
            return  # Exit the function if the variables file is missing

    #  CLUSTER CONT  - VISUALIZATION
        # Image A: Clusters only
        logger.info("Generating cluster map...")
        saved_map_path = create_cluster_map(
            gdf_clustered,
            project_root = project_root, 
            n_clusters = n_clusters,
            show_legend=show_legend,
            title="ORP Clusters based on 9 Selected Variables"
        )

        # Image B: Clusters + Points
        logger.info("Generating cluster map with point overlays...")
        create_cluster_map(
            gdf_clustered, 
            project_root=project_root, 
            n_clusters=n_clusters, 
            with_points=True, 
            point_mapping=POINT_MAPPING, 
            points_dir=raw_dir, 
            show_legend=show_legend,
            title="Spatial Justice Analysis"
        )
        logger.info(f"Visualization saved to: {saved_map_path}")

    else:
        logger.info("Skipping clustering (--skip-clustering set).")
    # logger.error("Variables file missing. Skipping Clustering and Visualization.")

    logger.info("Complete! :) ")


if __name__ == "__main__":
    app()
