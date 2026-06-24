import logging
import geopandas as gpd
from pathlib import Path
from glob import glob
from typing import Union

# Setup logging
logger = logging.getLogger(__name__)

# Function to transform projections 
def transform_projections(raw_dir: Union[str, Path], transformed_dir: Union[str, Path], target_epsg: int = 5514):
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
        filename = file_path.name
        try:
            logger.info(f"---- processing {filename} ----")
            
            # Load the file
            gdf = gpd.read_file(file_path)
            
            # Transform the projection
            logger.info(f"Adjusting projection to EPSG:{target_epsg}...")
            gdf = gdf.to_crs(epsg=target_epsg)
            
            # Define output path
            output_path = transformed_path / filename
            
            # Save the file
            gdf.to_file(output_path, driver='GeoJSON')
            logger.info(f"Successfully saved to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to process {filename}: {e}")