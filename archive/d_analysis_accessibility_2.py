import logging
import time
import requests
import numpy as np
import pandas as pd
import geopandas as gpd

logger = logging.getLogger(__name__)

# Target local Valhalla API URL
VALHALLA_API_URL = "http://localhost:8002"

# Safety limit for Valhalla (Sources x Targets) to prevent Error 400 (Max 2500)
VALHALLA_MATRIX_LIMIT = 2400 


def get_valhalla_matrix(origins, destinations, costing="auto", units="km"):
    """
    Calculates a travel matrix between origins and destinations.
    Uses dynamic batch calculation to stay within Valhalla's payload capacity limit.
    """
    endpoint = f"{VALHALLA_API_URL}/sources_to_targets"
    
    # 1. Format coordinates with search radius safeguards to snap rural centroids to roads
    sources = [
        {
            "lat": float(lat), 
            "lon": float(lon), 
            "radius": 5000  # Allow search up to 5km for a road
        } 
        for lat, lon in origins
    ]
    
    targets = [
        {
            "lat": float(lat), 
            "lon": float(lon), 
            "radius": 5000
        } 
        for lat, lon in destinations
    ]

    total_sources = len(sources)
    total_targets = len(targets)
    
    if total_sources == 0 or total_targets == 0:
        logger.warning("Empty coordinate sets provided to Valhalla routing.")
        return []

    # 2. Dynamic Batch Calculation: How many origins can we fit per API request?
    if total_targets > VALHALLA_MATRIX_LIMIT:
        logger.warning(f"Targets ({total_targets}) exceed limit ({VALHALLA_MATRIX_LIMIT}). Forcing unit batching.")
        batch_size = 1
    else:
        # Calculate dynamic batch size based on number of hospitals
        calculated_batch_size = int(VALHALLA_MATRIX_LIMIT / total_targets)
        # Limit batch size between 1 and 50 to keep request sizes healthy
        batch_size = max(1, min(calculated_batch_size, 50))
    
    logger.info(f"Routing configuration: {total_sources} Origins x {total_targets} Destinations.")
    logger.info(f"⚡ Calculated Dynamic Batch Size: {batch_size} origins per request.")

    # 3. Create clean list to hold calculated minimum times (in minutes) for each origin
    min_travel_times = [None] * total_sources
    
    # 4. Process Batch by Batch
    i = 0
    while i < total_sources:
        batch_sources = sources[i : i + batch_size]
        current_chunk_size = len(batch_sources)
        logger.info(f"  --> Processing batch {(i // batch_size) + 1}: origins {i} to {i + current_chunk_size}...")

        payload = {
            "sources": batch_sources,
            "targets": targets,
            "costing": costing,
            "units": units,
            "matrix_locations": 1,  # Stop calculation tree as soon as the 1 closest target is found
            "costing_options": {
                costing: {
                    "max_distance": 5000000  # Expand search threshold to 5000 km
                }
            }
        }

        try:
            response = requests.post(endpoint, json=payload, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                batch_results = data.get("sources_to_targets", [])

                # Map flat matrix responses back to their corresponding source index
                for local_idx, target_list in enumerate(batch_results):
                    global_idx = i + local_idx
                    
                    # Extract times (in seconds) and convert to minutes
                    times = [
                        cell["time"] / 60 
                        for cell in target_list 
                        if cell.get("time") is not None
                    ]
                    
                    if times:
                        min_travel_times[global_idx] = round(min(times), 1)
                    else:
                        min_travel_times[global_idx] = None
                        
                i += batch_size

            else:
                raise ValueError(f"Server returned status code {response.status_code}: {response.text}")

        except Exception as e:
            # RETRY FALLBACK: If a batch fails, isolate and calculate each origin individually
            logger.warning(f"  !! Batch failed due to: {e}. Falling back to individual processing...")
            
            for local_offset in range(current_chunk_size):
                global_idx = i + local_offset
                single_source = sources[global_idx]
                
                single_payload = {
                    "sources": [single_source],
                    "targets": targets,
                    "costing": costing,
                    "units": units,
                    "matrix_locations": 1
                }
                
                try:
                    res = requests.post(endpoint, json=single_payload, timeout=15)
                    if res.status_code == 200:
                        single_data = res.json().get("sources_to_targets", [[]])[0]
                        times = [
                            cell["time"] / 60 
                            for cell in single_data 
                            if cell.get("time") is not None
                        ]
                        min_travel_times[global_idx] = round(min(times), 1) if times else None
                    else:
                        logger.error(f"     xx Centroid {single_source['lat']:.5f}, {single_source['lon']:.5f} unroutable. Marking None.")
                        min_travel_times[global_idx] = None
                except Exception as individual_err:
                    logger.error(f"     xx Connection error on single origin: {individual_err}. Marking None.")
                    min_travel_times[global_idx] = None
                    
            i += batch_size

        time.sleep(0.1)  # Brief pause to keep Docker stable

    return min_travel_times


def calculate_health_accessibility(census_gdf, emergency_gdf, maternity_gdf):
    """
    Calculates travel times to the nearest emergency and maternity facilities,
    filtered to the loaded Prague map tiles to prevent out-of-bounds snapping errors.
    """
    census_gdf = census_gdf.copy()
    
    # Reproject all data to WGS84
    census_wgs = census_gdf.to_crs("EPSG:4326")
    emergency_wgs = emergency_gdf.to_crs("EPSG:4326")
    maternity_wgs = maternity_gdf.to_crs("EPSG:4326")

    # Bounding Box of Prague Map Tiles
    # Min/Max Latitude: 49.9 to 50.2 | Min/Max Longitude: 14.2 to 14.7
    lat_min, lat_max = 49.9, 50.2
    lon_min, lon_max = 14.2, 14.7

    # Helper to check if a coordinate is inside the Prague bounding box
    def is_in_prague(lat, lon):
        return (lat_min <= lat <= lat_max) and (lon_min <= lon <= lon_max)

    # 1. Extract and Filter Origins (ORPs)
    origins_all = [(float(geom.y), float(geom.x)) for geom in census_wgs.geometry.centroid]
    origins_filtered = [opt for opt in origins_all if is_in_prague(opt[0], opt[1])]
    
    # 2. Extract and Filter Destinations (Emergency Units)
    em_dest_all = [(float(geom.y), float(geom.x)) for geom in emergency_wgs.geometry]
    em_dest_filtered = [dest for dest in em_dest_all if is_in_prague(dest[0], dest[1])]

    # 3. Extract and Filter Destinations (Maternity Units)
    mat_dest_all = [(float(geom.y), float(geom.x)) for geom in maternity_wgs.geometry]
    mat_dest_filtered = [dest for dest in mat_dest_all if is_in_prague(dest[0], dest[1])]

    logger.info(f"Filtered to Prague Area:")
    logger.info(f"  - Origins: {len(origins_filtered)} of {len(origins_all)}")
    logger.info(f"  - Emergency Sites: {len(em_dest_filtered)} of {len(em_dest_all)}")
    logger.info(f"  - Maternity Sites: {len(mat_dest_filtered)} of {len(mat_dest_all)}")

    # Fallback arrays populated with None
    travel_emergency = [None] * len(origins_all)
    travel_maternity = [None] * len(origins_all)

    if len(origins_filtered) > 0 and len(em_dest_filtered) > 0:
        logger.info(f"Calculating travel times to Prague Emergency Care sites...")
        times_em = get_valhalla_matrix(origins_filtered, em_dest_filtered)
        
        # Map calculated times back to their original positions
        idx_filtered = 0
        for i, opt in enumerate(origins_all):
            if is_in_prague(opt[0], opt[1]):
                travel_emergency[i] = times_em[idx_filtered]
                idx_filtered += 1

    if len(origins_filtered) > 0 and len(mat_dest_filtered) > 0:
        logger.info(f"Calculating travel times to Prague Maternity Care sites...")
        times_mat = get_valhalla_matrix(origins_filtered, mat_dest_filtered)
        
        # Map calculated times back to their original positions
        idx_filtered = 0
        for i, opt in enumerate(origins_all):
            if is_in_prague(opt[0], opt[1]):
                travel_maternity[i] = times_mat[idx_filtered]
                idx_filtered += 1

    census_gdf["travel_time_emergency"] = travel_emergency
    census_gdf["travel_time_maternity"] = travel_maternity

    return census_gdf