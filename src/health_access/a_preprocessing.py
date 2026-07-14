import logging
import geopandas as gpd
import pandas as pd
from pathlib import Path
from glob import glob
from typing import Union, List, Dict
from sklearn.preprocessing import MinMaxScaler, StandardScaler

# Setup logging
logger = logging.getLogger(__name__)

# Function to transform projections 
##CHANGE NAME TO PROJECTION
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
    Calculates demographic variables and scales them using MinMaxScaler 
    to ensure all features contribute equally to the clustering.
    """
    # Load data
    gdf = gpd.read_file(input_path)

    # --- CALCULATIONS ---
    # We calculate the ratios first because scaling raw counts would 
    # bias the clustering toward larger districts.

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


    
    # --- MIN-MAX SCALING ---
    # Define the columns that will be used for clustering
    cols_to_scale = [
        "POP_DENS", "PCT_WOMEN", "PCT_CHILD", 
        "PCT_WORKING", "PCT_ELDERLY", "AGEING_INDEX", 
        "DEPENDENCY", "NATURAL_INC_RATE", "MIG_BAL_RATE"
    ]

    # Scale the data, StandardScaler is a feature from scikit-learn
    #scaler = StandardScaler()
    #X_scaled = scaler.fit_transform(X)
    #logger.info(f"Data scaled successfully using {len(features)} features.")

    # Initialize the Scaler
    scaler = StandardScaler()

    # Apply scaling. 
    # We create new columns with a '_scaled' suffix to keep the original values for analysis/mapping
    scaled_values = scaler.fit_transform(gdf[cols_to_scale])
    
    # Create a DataFrame from scaled values and join it back to the GDF
    scaled_df = pd.DataFrame(
        scaled_values, 
        columns=[f"{col}_scaled" for col in cols_to_scale], 
        index=gdf.index
    )
    
    #The concat function (short for concatenate) is used to join pandas objects.
    gdf = pd.concat([gdf, scaled_df], axis=1)

    # Save the result
    gdf.to_file(output_path, driver="GeoJSON")
    
    return output_path # Returning the path is helpful for the next step in main.py


def aggregate_poi(boundary_gdf: gpd.GeoDataFrame, point_mapping: Dict[str, str], points_dir: Path) -> gpd.GeoDataFrame:
    """
    Counts points from specific files and adds them as individual columns to the boundary GDF.
    
    Args:
        boundary_gdf: The ORP boundaries GeoDataFrame.
        point_mapping: Dict mapping filename to column name {'OD_emergency_care.geojson': 'COUNT_EMERGENCY'}
        points_dir: Path to the directory containing the point files.
    """
    df_result = boundary_gdf.copy()
    total_sum = 0

    for filename_poi, col_name in point_mapping.items():
        file_path = points_dir / filename_poi
        if not file_path.exists():
            logger.warning(f"Point file {filename_poi} not found at {file_path}. Skipping.")
            continue
        
        logger.info(f"Aggregating {filename_poi} into {col_name}...")
        points_gdf = gpd.read_file(file_path)
        
        # Spatial join: find which polygon each point is in
        # 'within' means the point is inside the polygon
        joined = gpd.sjoin(points_gdf, df_result, predicate='within')
        
        # Count points per polygon index and map back to the main dataframe
        counts = joined.groupby('index_right').size()
        # .reindex ensures that polygons with 0 points get a 0 instead of a NaN
        df_result[col_name] = counts.reindex(df_result.index, fill_value=0)
        
        # Accumulate for the total column
        total_sum += counts.fillna(0)

    # Create the final total column
    df_result['COUNT_TOTAL_CARE'] = total_sum.fillna(0).astype(int)
    
    # Fill NaNs for individual columns with 0
    df_result = df_result.fillna({'COUNT_EMERGENCY': 0, 'COUNT_MATERNITY': 0}) # Adjust names based on mapping
    
    # Ensure all count columns are integers
    count_cols = list(point_mapping.values()) + ['COUNT_TOTAL_CARE']
    df_result[count_cols] = df_result[count_cols].fillna(0).astype(int)

    # A. Define Metric (Per Capita Density)
    # Using the population column POCET_OBYV 
    population = df_result['POCET_OBYV'].replace(0, 1)
    df_result['EMERGENCY_PER_CAPITA'] = (df_result['COUNT_EMERGENCY'] / population) * 10000
    df_result['MATERNITY_PER_CAPITA'] = (df_result['COUNT_MATERNITY'] / population) * 10000
    df_result['TOTAL_PER_CAPITA'] = (df_result['COUNT_TOTAL_CARE'] / population) * 10000

    
    return df_result