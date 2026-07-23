import logging
import time
import requests
import geopandas as gpd
import numpy as np
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

VALHALLA_API_URL = "http://127.0.0.1:8002" #"http://localhost:8002" #"http://host.docker.internal:8002"
VALHALLA_MATRIX_LIMIT = 2400 

# CALCULATE TRAVEL TRIME MATRICES using Valhalla routing engine
def get_valhalla_matrix(origins, destinations, costing="auto", units="km"):
    """
    Calculates travel time matrices using the Valhalla routing engine.
    Instead of downloading a road network like Pandana,
    this version sends routing requests to Valhalla running locally in Docker.
    Returns travel time in minutes instead of distance in metres.

    1) Batches matrix queries -->
    2) Handles server communication
    3) Processes travel time arrays

    """
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
        
        # Log the batch processing information
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
            response = requests.post(
                endpoint,
                json=payload,
                timeout=60,
                headers={"Connection": "close"}
            )
            response.raise_for_status()
            data = response.json()
            
            results = data.get("sources_to_targets", [])
            for idx, source_results in enumerate(results):
                times = [float(cell["time"]) / 60 for cell in source_results if cell.get("time") is not None]
                min_travel_times[i + idx] = min(times) if times else float('inf')

        #TO KNOW WHAT THE ERROR IS 
        except requests.exceptions.HTTPError as e:
            logger.warning(f"Batch {batch_num} HTTPError: {type(e).__name__}: {e}")
            ...
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Batch {batch_num} ConnectionError: {type(e).__name__}: {e}")
            ...
        except requests.exceptions.Timeout as e:
            logger.warning(f"Batch {batch_num} Timeout: {type(e).__name__}: {e}")
            ...
        except Exception as e:
            logger.warning(f"Batch {batch_num} Other error: {type(e).__name__}: {e}")
        else:
            batch_num += 1
            time.sleep(0.05)
            continue

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
                res = requests.post(
                    endpoint,
                    json=individual_payload,
                    timeout=30,
                    headers={"Connection": "close"}
                )
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
                logger.error(f"XXXXX ORP {global_idx} critical error: {other_err} --> Using Straight-Line Approximation")
                source_lat, source_lon = source['lat'], source['lon']
                min_dist_km = float('inf')
                for target in targets:
                    dist = (((target['lat'] - source_lat)**2 + (target['lon'] - source_lon)**2)**0.5) * 111
                    if dist < min_dist_km: min_dist_km = dist
                min_travel_times[global_idx] = (min_dist_km * CIRCUITY_FACTOR) / (AVG_SPEED_KMPH / 60)

        batch_num += 1
        time.sleep(0.05)

    return min_travel_times


# MAIN ANALYSIS FUNCTION
# --> CALCULATES TRAVEL TIMES TO EMERGENCY AND MATERNITY CARE SITES
def calculate_health_accessibility(census_gdf, emergency_gdf, maternity_gdf):
    """
    Main entry point for accessibility analysis.
    
    1) Cleans invalid or duplicate hospital geometries
    2) Calculates matrices separately for emergency vs. maternity
    """
    census_gdf = census_gdf.copy()
    
    # Reproject and extract coordinates
    census_proj = census_gdf.to_crs("EPSG:3857")
    centroids = census_proj.geometry.centroid
    centroids_wgs = gpd.GeoSeries(centroids, crs="EPSG:3857").to_crs("EPSG:4326")
    origins = [(pt.y, pt.x) for pt in centroids_wgs]
    
    emergency_wgs = emergency_gdf.to_crs("EPSG:4326")
    maternity_wgs = maternity_gdf.to_crs("EPSG:4326")
    emergency_wgs = emergency_wgs[
        emergency_wgs.geometry.notnull() &
        ~emergency_wgs.geometry.is_empty &
        (emergency_wgs.geometry.geom_type == "Point")
    ].copy()

    maternity_wgs = maternity_wgs[
        maternity_wgs.geometry.notnull() &
        ~maternity_wgs.geometry.is_empty &
        (maternity_wgs.geometry.geom_type == "Point")
    ].copy()
    emergency_wgs["__xy"] = emergency_wgs.geometry.apply(lambda g: (round(g.y, 6), round(g.x, 6)))
    emergency_wgs = emergency_wgs.drop_duplicates("__xy").drop(columns="__xy")

    maternity_wgs["__xy"] = maternity_wgs.geometry.apply(lambda g: (round(g.y, 6), round(g.x, 6)))
    maternity_wgs = maternity_wgs.drop_duplicates("__xy").drop(columns="__xy")

    em_dest = [(float(geom.y), float(geom.x)) for geom in emergency_wgs.geometry]
    mat_dest = [(float(geom.y), float(geom.x)) for geom in maternity_wgs.geometry]

    logger.info(f"Processing all ORPs in Czechia: {len(origins)} ORPs")
    logger.info(f"  - Emergency Sites: {len(em_dest)}")
    logger.info(f"  - Maternity Sites: {len(mat_dest)}")

    # Emergency Care TIME CALCULATION
    if len(origins) > 0 and len(em_dest) > 0:
        logger.info("Calculating travel times to Emergency Care sites...")
        census_gdf["time_emergency"] = get_valhalla_matrix(origins, em_dest)
    else:
        census_gdf["time_emergency"] = np.nan

    # Maternity Care TIME CALCULATION
    if len(origins) > 0 and len(mat_dest) > 0:
        logger.info("Calculating travel times to Maternity Care sites...")
        census_gdf["time_maternity"] = get_valhalla_matrix(origins, mat_dest)
    else:
        census_gdf["time_maternity"] = np.nan

    return census_gdf


# Access rankings --> individual clusters
def add_access_rankings(
    gdf,
    maternity_col="time_maternity",
    emergency_col="time_emergency",
    rank_maternity_col="ranking_maternity",
    rank_emergency_col="ranking_emergency",
):
    """
    1) Adds ranking columns based on ascending travel time - within each demographic cluster
    2) Exports individual GeoJSONs
    
    Rank 1 = shortest/best access
    NaN travel times remain NaN in ranking columns
    """
    gdf = gdf.copy()

    if maternity_col in gdf.columns:
        gdf[rank_maternity_col] = (
            gdf[maternity_col]
            .rank(method="min", ascending=True)
            .where(gdf[maternity_col].notna())
            .astype("Int64")
        )

    if emergency_col in gdf.columns:
        gdf[rank_emergency_col] = (
            gdf[emergency_col]
            .rank(method="min", ascending=True)
            .where(gdf[emergency_col].notna())
            .astype("Int64")
        )

    return gdf


# SEPARATE CLUSTERS TO CONDUCT SUBSEQUENT ANALYSES
def export_clusters_separately(
    gdf,
    output_dir,
    cluster_col="cluster",
    maternity_col="time_maternity",
    emergency_col="time_emergency",
):
    """
    Saves each cluster into a separate GeoJSON file.
    Adds within-cluster ranking_maternity and ranking_emergency columns.

    e.g.: Comparing a rural peripheral ORPs withing cluster.
    Instead of comparing rural vs. urban.
    
    Comparing spatial justice relative to peer regions --> with similar socioeconomic conditions.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for cluster_id in sorted(gdf[cluster_col].dropna().unique()):
        subset = gdf[gdf[cluster_col] == cluster_id].copy()

        subset = add_access_rankings(
            subset,
            maternity_col=maternity_col,
            emergency_col=emergency_col,
            rank_maternity_col="ranking_maternity",
            rank_emergency_col="ranking_emergency",
        )

        path = output_dir / f"cluster_{cluster_id}.geojson"
        subset.to_file(path, driver="GeoJSON")
        logger.info(f"Saved cluster {cluster_id} -> {path.name}")



def print_defining_features(df: gpd.DataFrame, features: List[str]):
    """
    Calculates the Z-score of cluster means relative to the global mean.
    Values > 1.0 or < -1.0 indicate a defining characteristic.
    """
    # 1. Calculate global statistics
    global_means = df[features].mean()
    global_stds = df[features].std()
    
    # 2. Calculate cluster means
    cluster_means = df.groupby('cluster')[features].mean()
    
    # 3. Compute Z-scores: (Cluster Mean - Global Mean) / Global Std
    z_scores = (cluster_means - global_means) / global_stds
    
    print("\n" + "="*70)
    print("STEP 2: DEFINING FEATURES (Z-Scores)")
    print("Interpretation: > 1.0 (High) | < -1.0 (Low)")
    print("="*70)
    print(z_scores)
    print("="*70 + "\n")
    
    return z_scores