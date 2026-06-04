import logging
import geopandas as gpd
import os
from glob import glob
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def transform_projections(raw, transformed, target_epsg=5514):
    """
    Reads all geojson files in the raw data folder, transforms them to target_epsg,
    and saves them to the transformed folder.
    """
    # 1. Create output folder if it doesn't exist
    if not os.path.exists(transformed):
        os.makedirs(transformed)
        logger.info(f"Created output directory: {transformed}")

    # 2. Get a list of all .geojson files in the input folder
    search_path = os.path.join(raw, "*.geojson")
    files = glob(search_path)
    
    if not files:
        logger.warning("No .geojson files found in the specified folder.")
        return

    # 3. Loop through each file
    for file_path in files:
        filename = os.path.basename(file_path)
        try:
            logger.info(f"---- processing {filename} ----")
            
            # Load the file
            gdf = gpd.read_file(file_path)
            
            # Transform the projection
            logger.info(f"Adjusting projection to EPSG:{target_epsg}...")
            gdf = gdf.to_crs(epsg=target_epsg)
            
            # Define output path
            output_path = os.path.join(transformed, filename)
            
            # Save the file
            gdf.to_file(output_path, driver='GeoJSON')
            logger.info(f"Successfully saved to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to process {filename}: {e}")

# --- Execution ---
if __name__ == "__main__":
    #navigating to the data folder
    #project_root = Path(r"C:\Users\kana2\OneDrive\Documents\GitHub\spatial-justice\data") 
    current_file_path = Path(__file__).resolve()
    project_root = current_file_path.parents[3]
    
    INPUT_DIR = project_root / "raw" 
    OUTPUT_DIR = project_root / "transformed"
    TARGET_EPSG = 5514

    transform_projections(str(INPUT_DIR), str(OUTPUT_DIR), TARGET_EPSG)