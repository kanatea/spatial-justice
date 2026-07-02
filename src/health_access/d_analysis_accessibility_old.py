import requests
import geopandas as gpd
# import pandas as pd


VALHALLA_URL = "http://localhost:8002"
#######################################
# older version of Valhalla analysis, kept just in case

def calculate_health_accessibility(census_gdf, emergency_gdf, maternity_gdf):
    """
    census_gdf:    The GDF containing ORP/census data
    emergency_gdf: The GDF of Emergency care points
    maternity_gdf: The GDF of Maternity care points

    Instead of downloading a road network like Pandana,
    this version sends routing requests to Valhalla running locally in Docker.
    Returns travel time in minutes instead of distance in metres.
    """

    # 1. CONVERT TO WGS84
    census_gdf = census_gdf.copy() # avoid modifying the original GDF
    census_gdf["centroid"] = census_gdf.geometry.centroid # more accurate to calculate the centroids in meters
    # Valhalla needs lat/lon coordinates, not EPSG:5514 -_- reallyyy?
    census_wgs    = census_gdf.to_crs("EPSG:4326").copy()
    emergency_wgs = emergency_gdf.to_crs("EPSG:4326")
    maternity_wgs = maternity_gdf.to_crs("EPSG:4326")

    # Use the centroid of each ORP polygon as the origin point
    census_wgs["centroid"] = census_wgs.geometry.centroid

    # 2. DEFINE HELPER: get travel time between two points
    def get_travel_time(origin_lat, origin_lon, dest_lat, dest_lon):
        body = {
            "locations": [
                {"lat": origin_lat, "lon": origin_lon},
                {"lat": dest_lat,   "lon": dest_lon},
            ],
            "costing": "auto",
        }
        try:
            r = requests.post(f"{VALHALLA_URL}/route", json=body, timeout=10)
            if r.status_code == 200:
                seconds = r.json()["trip"]["summary"]["time"]
                return round(seconds / 60, 1)  # convert to minutes
            return None
        except Exception:
            return None

    # 3. FIND NEAREST HOSPITAL for each ORP centroid
    # Same idea as Pandana's get_poi_distance - find the closest facility
    def get_nearest_travel_time(origin_lat, origin_lon, hospitals_gdf, top_n=5):
        """
        Instead of checking all hospitals, first find the top_n closest
        by straight-line distance, then ask Valhalla only for those.
        """
        best_time = None
        for _, hospital in hospitals_gdf.iterrows():
            time = get_travel_time(
                origin_lat, origin_lon,
                hospital.geometry.y, hospital.geometry.x,
            )
            if time is not None:
                if best_time is None or time < best_time:
                    best_time = time
        return best_time
    

    # 4. CALCULATE ACCESSIBILITY FOR EACH ORP
    # Same idea as Pandana's network.get_poi_distance()
    print("Calculating travel times to nearest Emergency Care...")
    census_wgs["travel_time_emergency"] = [
        get_nearest_travel_time(row.centroid.y, row.centroid.x, emergency_wgs)
        for _, row in census_wgs.iterrows()
    ]

    print("Calculating travel times to nearest Maternity Care...")
    census_wgs["travel_time_maternity"] = [
        get_nearest_travel_time(row.centroid.y, row.centroid.x, maternity_wgs)
        for _, row in census_wgs.iterrows()
    ]

    # 5. ADD RESULTS BACK TO ORIGINAL GDF
    census_gdf = census_gdf.copy()
    census_gdf["travel_time_emergency"] = census_wgs["travel_time_emergency"].values
    census_gdf["travel_time_maternity"] = census_wgs["travel_time_maternity"].values

    return census_gdf