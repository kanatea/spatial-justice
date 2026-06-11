import logging
import geopandas as gpd
import sys
import yaml
from pathlib import Path
from health_access.preprocessing.transform import transform_projections
from health_access.preprocessing.standardize import standardize_data
from health_access.clustering.model import apply_clustering

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    logger.info("Hello from Marie and Kana!")

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

    # 1. PREPROCESSING: Transform all raw files to EPSG:5514
    logger.info("Starting Projection Transformation...")
    transform_projections(
        raw_dir, 
        transformed_dir, 
        target_epsg=config['projection']['target_epsg']
    )

    # PREPROCESSING CONT: Calculate Census Variables
    # We only run this if the file was successfully created in the prior step
    if census_input.exists():
        logger.info("Starting Census Variable Calculation...")
        standardize_data(census_input, census_output)
    else:
        logger.error(f"Census input file not found at {census_input}. Skipping calculation.")

    logger.info("Data preprocessing complete!")

    # 2. CLUSTERING
    if census_output.exists():
        logger.info("Starting Clustering...")
    
        gdf_vars = gpd.read_file(census_output)
        gdf_clustered = apply_clustering(gdf_vars, config)
    
        gdf_clustered.to_file(clustered_output, driver="GeoJSON")
        logger.info(f"Clustered data saved to: {clustered_output}")

    else:
        logger.error("Variables file missing. Skipping Step 3.")

    logger.info("Clustering complete!")

if __name__ == "__main__":
    main()











# Load configuration
#    with open("config/settings.yaml", "r") as f:
#        config = yaml.safe_load(f)

    # Part 1: Data Preprocessing 
    # Function from src.health_access.preprocessing
#    df = pd.read_csv(config['paths']['census_raw'])

    # Part 2: Clustering
#    print("Clustering districts...")
#    df_clustered = apply_clustering(df, config)

    # Part 3: Accessibility (You will implement this later)
    # results = calculate_accessibility(df_clustered, config)

    # Save the results
#    df_clustered.to_csv("data/processed/clustered_districts.csv", index=False)
#    print("Success! Results saved to data/processed/")