import logging
import time
import requests
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point
import os

logger = logging.getLogger(__name__)

# Target local Valhalla API URL
VALHALLA_API_URL = "http://localhost:8002"

# Safety limit for Valhalla (Sources x Targets) to prevent Error 400 (Max 2500)
VALHALLA_MATRIX_LIMIT = 2400 


#
def get_valhalla_matrix(origins, destinations, costing="auto", units="km"):
    """
    Calculates a travel matrix between origins and destinations.
    Uses dynamic batch calculation to stay within Valhalla's payload capacity limit.
    """
    endpoint = f"{VALHALLA_API_URL}/sources_to_targets"
    
    sources = [
        {
            "lat": float(lat), 
            "lon": float(lon), 
            "radius": 15000  # Increased to 15km
        } 
        for lat, lon in origins
    ]
    
    
    targets = [
        {
            "lat": float(lat), 
            "lon": float(lon), 
            "radius": 15000  # Increased to 15km
        } 
        for lat, lon in destinations
    ]

    total_sources = len(sources)
    total_targets = len(targets)
    
    if total_sources == 0 or total_targets == 0:
        logger.warning("Empty coordinate sets provided to Valhalla routing.")
        return []

    if total_targets > VALHALLA_MATRIX_LIMIT:
        logger.warning(f"Targets ({total_targets}) exceed limit ({VALHALLA_MATRIX_LIMIT}). Forcing unit batching.")
        batch_size = 1
    else:
        calculated_batch_size = int(VALHALLA_MATRIX_LIMIT / total_targets)
        batch_size = max(1, min(calculated_batch_size, 50))
    
    logger.info(f"Routing configuration: {total_sources} Origins x {total_targets} Destinations.")
    logger.info(f"⚡ Calculated Dynamic Batch Size: {batch_size} origins per request.")

    min_travel_times = [None] * total_sources
    

    # Pre-calculate average speed for the fallback (e.g., 60 km/h = 1 km per minute)
    # Adjust this based on your 'costing' (e.g., 40 km/h for local roads)
    AVG_SPEED_KMPH = 60 
    CIRCUITY_FACTOR = 1.3 


    # --- REPLACED SECTION: Simplified Individual Processing ---
    min_travel_times = []
    
    for idx, source in enumerate(sources):
        logger.info(f"Processing ORP {idx + 1}/{total_sources}...")
        
        payload = {
            "sources": [source],
            "targets": targets,
            "costing": costing,
            "units": units,
            "matrix_locations": 1, 
            "costing_options": {
                costing: {
                    "max_distance": 5000000 
                }
            }
        }

        try:
            response = requests.post(endpoint, json=payload, timeout=30)
            response.raise_for_status()
            
            # SUCCESS PATH
            data = response.json()
            
            # sources_to_targets returns a list of lists
            # We take the first list [0] because we only sent one source per request
            target_list = data.get("sources_to_targets", [[]])[0]
            
            # Extract times and convert to minutes (Valhalla usually returns seconds)
            times = [
                float(cell["time"]) / 60 
                for cell in target_list 
                if cell.get("time") is not None
            ]
            
            if times:
                min_travel_times.append(min(times))
            else:
                logger.warning(f"ORP {idx + 1} returned no travel times.")
                min_travel_times.append(float('inf'))
                

        except requests.exceptions.HTTPError as e:
            # ERROR PATH
            if response.status_code == 400:
                logger.warning(f"ORP {idx + 1} failed with status {response.status_code}: {response.text}. Using straight-line approximation.")
                
                source_lat, source_lon = source['lat'], source['lon']
                min_dist_km = float('inf')
                for target in targets:
                    # Approximation: 1 degree ~= 111 km
                    dist = (((target['lat'] - source_lat)**2 + 
                             (target['lon'] - source_lon)**2)**0.5) * 111
                    if dist < min_dist_km:
                        min_dist_km = dist
                
                approx_time = (min_dist_km * CIRCUITY_FACTOR) / (AVG_SPEED_KMPH / 60)
                min_travel_times.append(approx_time)
            else:
                logger.error(f"HTTP Error for ORP {idx + 1}: {e}")
                min_travel_times.append(float('inf'))

        except Exception as e:
            logger.warning(f"ORP {idx + 1} encountered a critical error: {e}")
            min_travel_times.append(float('inf'))

        # Small sleep to prevent API throttling
        time.sleep(0.1)

    return min_travel_times



def calculate_health_accessibility(census_gdf, emergency_gdf, maternity_gdf):
    """
    Calculates travel times to the nearest emergency and maternity facilities
    for the entire dataset provided (Whole of Czechia).
    """
    census_gdf = census_gdf.copy()
    
    # 1. Extract Origins (Centroids of census areas)
    # Reproject (required for Valhalla)
    centroids_wgs = census_gdf.geometry.centroid.to_crs("EPSG:4326")
    origins = [(pt.y, pt.x) for pt in centroids_wgs]
    
    #census_wgs = census_gdf.to_crs("EPSG:4326")
    #origins = [(float(geom.y), float(geom.x)) for geom in census_wgs.geometry.centroid]
    #origins = [(point.y, point.x) for point in census_wgs]

    # 2. Extract Destinations (Emergency Units)
    #reproject
    emergency_wgs = emergency_gdf.to_crs("EPSG:4326")
    maternity_wgs = maternity_gdf.to_crs("EPSG:4326")
    em_dest = [(float(geom.y), float(geom.x)) for geom in emergency_wgs.geometry]
    # 3. Extract Destinations (Maternity Units)
    mat_dest = [(float(geom.y), float(geom.x)) for geom in maternity_wgs.geometry]

    logger.info(f"Processing Whole of Czechia:")
    logger.info(f"  - Origins: {len(origins)}")
    logger.info(f"  - Emergency Sites: {len(em_dest)}")
    logger.info(f"  - Maternity Sites: {len(mat_dest)}")

    # Calculate Emergency Travel Times
    if len(origins) > 0 and len(em_dest) > 0:
        logger.info(f"Calculating travel times to Emergency Care sites...")
        census_gdf["time_emergency"] = get_valhalla_matrix(origins, em_dest)
    else:
        census_gdf["time_emergency"] = None
        # census_gdf["travel_time_emergency"] = census_gdf["travel_time_emergency"].fillna(180)

    # Calculate Maternity Travel Times
    if len(origins) > 0 and len(mat_dest) > 0:
        logger.info(f"Calculating travel times to Maternity Care sites...")
        census_gdf["time_maternity"] = get_valhalla_matrix(origins, mat_dest)
    else:
        census_gdf["time_maternity"] = None
        #census_gdf["travel_time_maternity"] = census_gdf["travel_time_maternity"].fillna(180)


    return census_gdf