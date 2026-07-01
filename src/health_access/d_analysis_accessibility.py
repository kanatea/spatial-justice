import osmnx as ox
import pandana as pdn
import geopandas as gpd
import pandas as pd

##NEED TO PLUG THIS INTO MAIN.PY 

def calculate_health_accessibility(census_gdf, emergency_gdf, maternity_gdf, bbox):
    """
    census_gdf: The GDF containing your population/census data
    emergency_gdf: The GDF of Emergency care points
    maternity_gdf: The GDF of Maternity care points
    bbox: The bounding box of your study area
    """
    
    # 1. DOWNLOAD THE ROAD NETWORK (Essential for Pandana)
    # We need the roads to calculate "Network Distance" instead of "Straight Line"
    print("Downloading road network...")
    graph = ox.graph_from_bbox(bbox=bbox, network_type='drive')
    
    # 2. BUILD THE PANDANA NETWORK
    # This converts the OSM graph into a high-performance Pandana object
    nodes, edges = ox.graph_to_gdfs(graph)
    
    network = pdn.Network(
        node_x=nodes["x"],
        node_y=nodes["y"],
        edge_from=pd.Series(edges.index.get_level_values("u").values),
        edge_to=pd.Series(edges.index.get_level_values("v").values),
        edge_weights=pd.DataFrame({"distance": edges["length"].values}),
        twoway=False
    )

    # 3. REGISTER YOUR SPECIFIC CARE POINTS
    # We tell Pandana: "These specific coordinates are the health facilities"
    print("Registering health facilities...")
    
    # Register Emergency Care
    network.set_pois(
        category="emergency",
        x_col=emergency_gdf.geometry.x,
        y_col=emergency_gdf.geometry.y,
        maxdist=10000 # Max distance to look for a facility (e.g., 10km)
    )
    
    # Register Maternity Care
    network.set_pois(
        category="maternity",
        x_col=maternity_gdf.geometry.x,
        y_col=maternity_gdf.geometry.y,
        maxdist=10000
    )

    # 4. CALCULATE ACCESSIBILITY FOR CENSUS POINTS
    # We calculate the distance from every census centroid to the nearest facility
    print("Calculating travel distances...")
    
    # Distance to nearest Emergency Care
    census_gdf['dist_emergency'] = network.get_poi_distance(
        x=census_gdf.geometry.x, 
        y=census_gdf.geometry.y, 
        category="emergency"
    )
    
    # Distance to nearest Maternity Care
    census_gdf['dist_maternity'] = network.get_poi_distance(
        x=census_gdf.geometry.x, 
        y=census_gdf.geometry.y, 
        category="maternity"
    )
    
    return census_gdf