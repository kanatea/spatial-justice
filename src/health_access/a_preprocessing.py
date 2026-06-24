import logging
import geopandas as gpd
from pathlib import Path
from glob import glob
from typing import Union

# Setup logging
logger = logging.getLogger(__name__)

# Function to transform projections 
def transform_projections(raw_dir: Union[str, Path], transformed_dir: Union[str, Path], target_epsg: int):
    """
    Reads all geojson files in the raw data folder, transforms them to target_epsg,
    and saves them to the transformed folder.
    """
    # Convert inputs to Path objects for consistency
    raw_path = Path(raw_dir)
    transformed_path = Path(transformed_dir)

    # 1. Create output folder if it doesn't exist
    transformed_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Ensured output directory exists: {transformed_path}")

    # 2. Get a list of all .geojson files using Path.glob
    files = list(raw_path.glob("*.geojson"))
    
    if not files:
        logger.warning("No .geojson files found in the specified folder.")
        return

    # 3. Loop through each file
    for file_path in files:
        try:
            # Load the file
            gdf = gpd.read_file(file_path)
            
            # Transform the projection
            logger.info(f"Adjusting projection to EPSG:{target_epsg}...")
            gdf = gdf.to_crs(epsg=target_epsg)
            
            # Define output path
            output_path = transformed_path / file_path.name
            
            # Save the file
            gdf.to_file(output_path, driver='GeoJSON')
            logger.info(f"Successfully saved to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to process {file_path.name}: {e}")



#automated this process to run in main.py

def standardize_data(input_path: Path, output_path: Path):
    """
    Reads ORP census data and calculates demographic variables.
    """
    # Load data
    gdf = gpd.read_file(input_path)

    # --- CALCULATIONS ---
    # Area in km²
    gdf["AREA_KM2"] = gdf["SHAPE_Area"] / 1_000_000

    # Population density
    gdf["POP_DENS"] = gdf["POCET_OBYV"] / gdf["AREA_KM2"]

    # Percentages
    gdf["PCT_WOMEN"] = (gdf["ZENY"] / gdf["POCET_OBYV"]) * 100
    gdf["PCT_CHILD"] = (gdf["OBYV_0_14"] / gdf["POCET_OBYV"]) * 100
    gdf["PCT_WORKING"] = (gdf["OBYV_15_64"] / gdf["POCET_OBYV"]) * 100
    gdf["PCT_ELDERLY"] = (gdf["OBYV_65"] / gdf["POCET_OBYV"]) * 100

    # Indices
    gdf["AGEING_INDEX"] = (gdf["OBYV_65"] / gdf["OBYV_0_14"]) * 100
    gdf["DEPENDENCY"] = ((gdf["OBYV_0_14"] + gdf["OBYV_65"]) / gdf["OBYV_15_64"]) * 100

    # Natural Increase
    gdf["NATURAL_INC"] = gdf["NAROZENI"] - gdf["ZEMRELI"]
    gdf["NATURAL_INC_RATE"] = (gdf["NATURAL_INC"] / gdf["POCET_OBYV"]) * 1000

    # Migration Balance
    gdf["MIG_BAL"] = gdf["PRISTEHOVALI"] - gdf["VYSTEHOVALI"]
    gdf["MIG_BAL_RATE"] = (gdf["MIG_BAL"] / gdf["POCET_OBYV"]) * 1000

    # Save the result
    gdf.to_file(output_path, driver="GeoJSON")
    
    return output_path # Returning the path is helpful for the next step in main.py