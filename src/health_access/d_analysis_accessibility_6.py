import logging
import time
import requests
import geopandas as gpd
import numpy as np
from shapely.geometry import Point

logger = logging.getLogger(__name__)

VALHALLA_API_URL = "http://localhost:8002"
VALHALLA_MATRIX_LIMIT = 2400 

def get_valhalla_matrix(origins, destinations, costing="auto", units="km"):
    endpoint = f"{VALHALLA_API_URL}/sources_to_targets"
    
    sources = [{"lat": float(lat), "lon": float(lon), "radius": 15000} for lat, lon in origins]
    targets = [{"lat": float(lat), "lon": float(lon), "radius": 15000} for lat, lon in destinations]

    total_sources = len(sources)
    total_targets = len(targets)
    
    if total_sources == 0 or total_targets == 0:
        return []

    # Dynamic batching logic
    if total_targets > VALHALLA_MATRIX_LIMIT:
        batch_size = 1
    else:
        calculated_batch_size = int(VALHALLA_MATRIX_LIMIT / total_targets)
        batch_size = max(1, min(calculated_batch_size, 50))
    
    logger.info(f"Routing: {total_sources} Origins x {total_targets} Targets. Batch Size: {batch_size}")

    AVG_SPEED_KMPH = 60 
    CIRCUITY_FACTOR = 1.3 
    min_travel_times = [None] * total_sources
    
    # Track batch number for the console output
    batch_num = 1
    for i in range(0, total_sources, batch_size):
        batch_sources = sources[i : i + batch_size]
        current_batch_size = len(batch_sources)
        
        # RESTORED: The specific labeling style you prefer
        logger.info(f"--> Processing batch {batch_num}: origins {i} to {min(i + batch_size, total_sources)}...")
        
        payload = {
            "sources": batch_sources,
            "targets": targets,
            "costing": costing,
            "units": units,
            "matrix_locations": 1, 
            "costing_options": {costing: {"max_distance": 5000000}}
        }

        try:
            response = requests.post(endpoint, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            results = data.get("sources_to_targets", [])
            for idx, source_results in enumerate(results):
                times = [float(cell["time"]) / 60 for cell in source_results if cell.get("time") is not None]
                min_travel_times[i + idx] = min(times) if times else float('inf')

        except (requests.exceptions.HTTPError, Exception) as e:
            # Log the batch failure using the same logger style
            logger.warning(f"Batch {batch_num} failed. Falling back to individual processing for {i} to {min(i + batch_size, total_sources)}...")
            
            for j in range(current_batch_size):
                global_idx = i + j
                source = batch_sources[j]
                
                individual_payload = {
                    "sources": [source],
                    "targets": targets,
                    "costing": costing,
                    "units": units,
                    "matrix_locations": 1,
                    "costing_options": {costing: {"max_distance": 5000000}}
                }
                
                try:
                    res = requests.post(endpoint, json=individual_payload, timeout=10)
                    res.raise_for_status()
                    res_data = res.json()
                    target_list = res_data.get("sources_to_targets", [[]])[0]
                    times = [float(cell["time"]) / 60 for cell in target_list if cell.get("time") is not None]
                    min_travel_times[global_idx] = min(times) if times else float('inf')
                
                except requests.exceptions.HTTPError as http_err:
                    # DETAILED ERROR LOGGING: Matches your logger format
                    error_code = http_err.response.status_code
                    error_msg = http_err.response.text
                    logger.warning(f"ORP {global_idx} failed | Code: {error_code} | Msg: {error_msg} --> Using Straight-Line Approximation")
                    
                    # Straight-line Fallback
                    source_lat, source_lon = source['lat'], source['lon']
                    min_dist_km = float('inf')
                    for target in targets:
                        dist = (((target['lat'] - source_lat)**2 + (target['lon'] - source_lon)**2)**0.5) * 111
                        if dist < min_dist_km: min_dist_km = dist
                    min_travel_times[global_idx] = (min_dist_km * CIRCUITY_FACTOR) / (AVG_SPEED_KMPH / 60)
                
                except Exception as other_err:
                    logger.error(f"❌ ORP {global_idx} critical error: {other_err} --> Using Straight-Line Approximation")
                    source_lat, source_lon = source['lat'], source['lon']
                    min_dist_km = float('inf')
                    for target in targets:
                        dist = (((target['lat'] - source_lat)**2 + (target['lon'] - source_lon)**2)**0.5) * 111
                        if dist < min_dist_km: min_dist_km = dist
                    min_travel_times[global_idx] = (min_dist_km * CIRCUITY_FACTOR) / (AVG_SPEED_KMPH / 60)

        batch_num += 1
        time.sleep(0.05)

    return min_travel_times

def calculate_health_accessibility(census_gdf, emergency_gdf, maternity_gdf):
    """
    Main entry point for accessibility analysis.
    """
    census_gdf = census_gdf.copy()
    
    # Reproject and extract coordinates
    centroids_wgs = census_gdf.geometry.centroid.to_crs("EPSG:4326")
    origins = [(pt.y, pt.x) for pt in centroids_wgs]
    
    emergency_wgs = emergency_gdf.to_crs("EPSG:4326")
    maternity_wgs = maternity_gdf.to_crs("EPSG:4326")
    em_dest = [(float(geom.y), float(geom.x)) for geom in emergency_wgs.geometry]
    mat_dest = [(float(geom.y), float(geom.x)) for geom in maternity_wgs.geometry]

    logger.info(f"Processing all ORPs in Czechia: {len(origins)} ORPs")
    logger.info(f"  - Emergency Sites: {len(em_dest)}")
    logger.info(f"  - Maternity Sites: {len(mat_dest)}")

    # Emergency Care
    if len(origins) > 0 and len(em_dest) > 0:
        logger.info("Calculating travel times to Emergency Care sites...")
        census_gdf["time_emergency"] = get_valhalla_matrix(origins, em_dest)
    else:
        census_gdf["time_emergency"] = np.nan

    # Maternity Care
    if len(origins) > 0 and len(mat_dest) > 0:
        logger.info("Calculating travel times to Maternity Care sites...")
        census_gdf["time_maternity"] = get_valhalla_matrix(origins, mat_dest)
    else:
        census_gdf["time_maternity"] = np.nan

    return census_gdf