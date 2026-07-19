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
    

    #dynamic batch matrix
    # --- REPLACED SECTION: Simplified Individual Processing ---
    min_travel_times = []
    
    for idx, source in enumerate(sources):
        logger.info(f"Processing ORP {idx + 1}/{total_sources}...")
        
        # We send ONE source and ALL targets per request
        payload = {
            "sources": [source],
            "targets": targets,
            "costing": costing,
            "units": units,
            "matrix_locations": 1, 
            #"options": {
            #    "radius": 15000  # <--- THIS IS THE KEY ADDITION
            #},
            "costing_options": {
                costing: {
                    "max_distance": 5000000 
                }
            }
        }

        try:
            response = requests.post(endpoint, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                # sources_to_targets is a list of lists; we take the first list [0]
                target_list = data.get("sources_to_targets", [[]])[0]
                
                times = [
                    cell["time"] / 60 
                    for cell in target_list 
                    if cell.get("time") is not None
                ]
                
                if times:
                    min_travel_times.append(round(min(times), 1))
                else:
                    min_travel_times.append(None)
            else:
                logger.warning(f"ORP {idx} failed with status {response.status_code}: {response.text}")
                min_travel_times.append(None)

        except Exception as e:
            logger.warning(f"ORP {idx} encountered an error: {e}")
            min_travel_times.append(None)

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
    #census_projected = census_gdf.to_crs("EPSG:2173")
    centroids_projected = census_gdf.to_crs(epsg=2173).centroid
    centroids_latlon = centroids_projected.to_crs(epsg=4326)
    #census_wgs_centroids = gpd.GeoSeries(centroids_projected, crs="EPSG:2173").to_crs("EPSG:4326")

    #origins = [(float(geom.y), float(geom.x)) for geom in census_wgs_centroids]
    origins = [(point.y, point.x) for point in centroids_latlon]

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




    #VISUALIZATOIN
    # --- Assuming you already have census_gdf and the 'origins' list ---
    # origins = [(lat, lon), (lat, lon), ...]

    # 2. Convert the 'origins' list of tuples back into a GeoDataFrame of Points
    points_geometry = [Point(lon, lat) for lat, lon in origins]
    gdf_centroids = gpd.GeoDataFrame(geometry=points_geometry, crs="EPSG:4326")

    # 3. Ensure the original census_gdf is also in WGS84
    census_wgs = census_gdf.to_crs("EPSG:4326")
    

    # 4. Create the Static Map
    fig, ax = plt.subplots(figsize=(15, 15))

    # Plot the polygons (the ORPs) as the background
    census_wgs.plot(ax=ax, color='white', edgecolor='black', linewidth=0.5)

    # Plot the centroids (the 'origins') as red dots
    gdf_centroids.plot(ax=ax, color='red', markersize=10, zorder=3)

    # 5. Label each centroid with its Index/ID
    # We iterate through the census_wgs index and the coordinates
    for idx, geom in zip(census_wgs.index, centroids_latlon):
        # Offset the text slightly (0.01 degrees) so it doesn't sit directly on the dot
        ax.text(geom.x + 0.01, geom.y + 0.01, str(idx), 
                fontsize=8, 
                fontweight='bold', 
                ha='left', 
                va='bottom', 
                zorder=4)

    # Formatting
    plt.title("Czechia ORP Centroids with ID Labels", fontsize=16)
    plt.axis('off') 

    output_folder = "visualizations"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    # 6. Save to the visualizations folder instead of showing the popup
    save_path = os.path.join(output_folder, "orp_centroids_labeled.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close() # Closes the plot so it doesn't pop up in the notebook

    print(f"Map successfully saved to: {save_path}")




    # Calculate Emergency Travel Times
    if len(origins) > 0 and len(em_dest) > 0:
        logger.info(f"Calculating travel times to Emergency Care sites...")
        census_gdf["travel_time_emergency"] = get_valhalla_matrix(origins, em_dest)
    else:
        census_gdf["travel_time_emergency"] = None
        # census_gdf["travel_time_emergency"] = census_gdf["travel_time_emergency"].fillna(180)

    # Calculate Maternity Travel Times
    if len(origins) > 0 and len(mat_dest) > 0:
        logger.info(f"Calculating travel times to Maternity Care sites...")
        census_gdf["travel_time_maternity"] = get_valhalla_matrix(origins, mat_dest)
    else:
        census_gdf["travel_time_maternity"] = None
        #census_gdf["travel_time_maternity"] = census_gdf["travel_time_maternity"].fillna(180)


    return census_gdf