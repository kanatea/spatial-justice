import logging
import time
import requests
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point
from sklearn.neighbors import BallTree
import numpy as np
import os
import json
from geopy.distance import geodesic

logger = logging.getLogger(__name__)

# Target local Valhalla API URL
VALHALLA_API_URL = "http://localhost:8002" 
VALHALLA_MATRIX_LIMIT = 2400 

def calculate_geodesic_fallback(orp_coords, hospital_coords):
    """
    Calculates the minimum straight-line distance and applies a 
    circuity factor (1.3) to estimate actual road travel time.
    """
    min_dist = float('inf')
    orp_pt = (orp_coords['lat'], orp_coords['lon'])
    
    for hosp in hospital_coords:
        hosp_pt = (hosp['lat'], hosp['lon'])
        dist = geodesic(orp_pt, hosp_pt).kilometers
        if dist < min_dist:
            min_dist = dist
            
    # Estimate: distance * 1.3 (circuity) / avg_speed (60 km/h)
    # (dist * 1.3) / (60/60) = dist * 1.3 minutes
    return (min_dist * 1.3)

def get_min_travel_time_for_orp(orp_coords, hospital_coords):
    """
    Ultra-simplified Valhalla call to diagnose 442 errors.
    """
    try:
        # DEBUG: Print the first request to verify coordinates are actually in Czechia
        # Czechia is roughly Lat: 48-51, Lon: 12-18
        if 'debug_printed' not in globals():
            print(f"DEBUG: Sending to API -> Source: {orp_coords}, Target[0]: {hospital_coords[0]}")
            globals()['debug_printed'] = True

        #payload = {
        #    "sources": [orp_coords],
        #    "targets": hospital_coords,
        #    "costing": "auto",
        #    "units": "kilometers"
            # Removed radius and costing_options to use Valhalla defaults
        #}

        # Assuming orp_coords is (lat, lon) and hospital_coords is a list of (lat, lon)
        payload = {
            "sources": [
                {"lat": orp_coords[0], "lon": orp_coords[1], "radius": 2000}
            ],
            "targets": [
                {"lat": h[0], "lon": h[1], "radius": 2000} for h in hospital_coords
            ],
            "units": "kilometers",
            "costing": "auto", 
            "costing_options": {
                "auto": {
                    "max_distance": 5000000  # This is 5,000km in meters
                }
            }
        }
        
        response = requests.post(f"{VALHALLA_API_URL}/sources_to_targets", json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            targets = data.get('sources', [{}])[0].get('targets', [])
            times = [t.get('travel_time') for t in targets if t.get('travel_time') is not None]
            return min(times) / 60.0 if times else None
            
        elif response.status_code == 400:
            # Log the error but don't spam the console for every point
            # Only print the first few 400 errors
            if 'error_count' not in globals():
                globals()['error_count'] = 0
            globals()['error_count'] += 1
            
            if globals()['error_count'] <= 3:
                print(f"❌ API 400 Error: {response.text}")
            
            return calculate_geodesic_fallback(orp_coords, hospital_coords)
        
        else:
            return calculate_geodesic_fallback(orp_coords, hospital_coords)

    except Exception as e:
        return calculate_geodesic_fallback(orp_coords, hospital_coords)

def compute_nearest_times(origin_coords_rad, dest_coords_rad, dest_list_latlon, origins_list_latlon, census_gdf):
    """
    Internal helper to perform BallTree pruning + Valhalla API calls.
    """
    # 1. Prune to the 20 nearest hospitals using the radians array [lon, lat]
    tree = BallTree(dest_coords_rad, metric='haversine')
    dist, indices = tree.query(origin_coords_rad, k=min(20, len(dest_list_latlon)))
    
    final_times = []
    for i in range(len(origins_list_latlon)):
        # origin_list_latlon[i] is [lat, lon]
        orp_dict = {"lat": origins_list_latlon[i][0], "lon": origins_list_latlon[i][1]}
        
        # Get the 20 nearest hospital indices
        candidate_indices = indices[i]
        
        # dest_list_latlon[idx] is [lat, lon]
        candidates_dicts = [
            {"lat": dest_list_latlon[idx][0], "lon": dest_list_latlon[idx][1]} 
            for idx in candidate_indices
        ]
        
        min_time = get_min_travel_time_for_orp(orp_dict, candidates_dicts)
        
        if min_time is None:
            # Fallback: distance (rad) * 6371 * 1.3 circuity
            straight_dist_km = dist[i][0] * 6371
            min_time = (straight_dist_km * 1.3)
            
        final_times.append(min_time)
        
    return final_times

def calculate_health_accessibility(census_gdf, emergency_gdf, maternity_gdf):
    """
    Calculates travel times to the nearest emergency and maternity facilities.
    """
    census_gdf = census_gdf.copy()
    
    # 1. Extract Origins
    # FIX: Project to Web Mercator (3857) to get accurate centroids, then back to 4326
    centroids_wgs = census_gdf.geometry.to_crs("EPSG:3857").centroid.to_crs("EPSG:4326")
    
    # For BallTree: [lon, lat] in radians
    origins_coords_rad = np.deg2rad(np.array([[pt.x, pt.y] for pt in centroids_wgs]))
    # For API: [lat, lon] in degrees
    origins_list_latlon = [[pt.y, pt.x] for pt in centroids_wgs]

    # 2. Process Emergency Services
    logger.info("Calculating travel times to Emergency services...")
    # FIX: Project to Web Mercator (3857) for accurate centroids
    emerg_wgs = emergency_gdf.geometry.to_crs("EPSG:3857").centroid.to_crs("EPSG:4326")
    
    # For BallTree: [lon, lat] in radians
    emerg_coords_rad = np.deg2rad(np.array([[pt.x, pt.y] for pt in emerg_wgs]))
    # For API: [lat, lon] in degrees
    emerg_list_latlon = [[pt.y, pt.x] for pt in emerg_wgs]
    
    census_gdf['time_emergency'] = compute_nearest_times(
        origins_coords_rad, emerg_coords_rad, emerg_list_latlon, origins_list_latlon, census_gdf
    )

    # 3. Process Maternity Services
    logger.info("Calculating travel times to Maternity services...")
    # FIX: Project to Web Mercator (3857) for accurate centroids
    mat_wgs = maternity_gdf.geometry.to_crs("EPSG:3857").centroid.to_crs("EPSG:4326")
    
    # For BallTree: [lon, lat] in radians
    mat_coords_rad = np.deg2rad(np.array([[pt.x, pt.y] for pt in mat_wgs]))
    # For API: [lat, lon] in degrees
    mat_list_latlon = [[pt.y, pt.x] for pt in mat_wgs]
    
    census_gdf['time_maternity'] = compute_nearest_times(
        origins_coords_rad, mat_coords_rad, mat_list_latlon, origins_list_latlon, census_gdf
    )

    census_gdf['avg_health_time'] = (census_gdf['time_emergency'] + census_gdf['time_maternity']) / 2
    return census_gdf