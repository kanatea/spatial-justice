import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from pathlib import Path
import pandas as pd
import osmnx as ox


#======================================================================================
# CLUSTER MAP
#=======================================================================================

def create_cluster_map(
    gdf, 
    basemap_gdf,
    project_root, 
    n_clusters, 
    color_palette=None,
    with_points=False, 
    point_mapping=None, # Expects { "Emergency": em_gdf, "Maternity": mat_gdf }
    show_legend=False, 
    title="Cluster Map",
    ax=None
):
    # Dynamic filename
    # If ax is provided, we don't create a new figure or save a file
    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 10))
        output_path = project_root / f"visualizations/map_clusters_{n_clusters}.png"
    
    # 1. Plot the neutral grey basemap (Aesthetic from plot_hospital_distribution)
    basemap_gdf.plot(ax=ax, color="#f2f2f2", edgecolor="#bcbcbc", linewidth=0.5)

    # 2. Plot the clusters
    clusters = sorted(gdf['cluster'].unique())
    
    # Use passed palette or fallback to the professional default
    if color_palette is None:
        color_palette = ["#e6194b", "#4363d8", "#f58231", "#3cb44b", "#ffe119", "#f032e6", "#911eb4", "#42d4f4", "#a9a9a9"]
    
    # Slice to match number of clusters
    selected_colors = color_palette[:len(clusters)]
    color_map = {cluster: color for cluster, color in zip(clusters, selected_colors)}
    gdf['color'] = gdf['cluster'].map(color_map)

    gdf.plot(color=gdf['color'], legend=False, ax=ax, edgecolor='white', linewidth=0.5)

    # 3. OVERLAY POINTS (Using the specific aesthetics requested)
    point_handles = []
    if with_points and point_mapping:
        # Aesthetic Configuration: { Label: (Color, Marker) }
        point_config = {
            "Emergency": ("black", "o"), 
            "Maternity": ("red", "x")
        }
        
        for label, p_gdf in point_mapping.items():
            if p_gdf.crs != gdf.crs:
                p_gdf = p_gdf.to_crs(gdf.crs)
            
            # Get aesthetic settings or fallback to black/circle
            color, marker = point_config.get(label, ("black", "o"))
            
            p_gdf.plot(
                ax=ax, 
                color=color, 
                markersize=15, # Increased size per your distribution map
                alpha=0.6, 
                marker=marker,
                label=label
            )
            
            # Create a proxy artist for the legend that matches the marker style
            point_handles.append(plt.Line2D([0], [0], 
                                          marker=marker, 
                                          color='w', 
                                          markerfacecolor=color, 
                                          markeredgecolor=color,
                                          markersize=10, 
                                          label=label))

    if show_legend:
        # Cluster patches
        patches = [mpatches.Patch(color=selected_colors[i], label=f"Cluster {cluster}") for i, cluster in enumerate(clusters)]
        
        # Combine cluster patches and point handles
        all_handles = patches + point_handles
        ax.legend(handles=all_handles, title_fontsize=14, prop={'size': 12}, loc="lower right", frameon=True)
    
    ax.set_title(title, fontsize=20)
    ax.set_axis_off()

    if ax is not None: # If we were passed an axis, don't save here
        return None 
    
    #plt.title(f"{title} ({suffix}) --- {n_clusters} clusters", fontsize=15)
    #ax.set_axis_off() 
    plt.savefig(output_path, bbox_inches='tight', dpi=300)
    plt.close()
    return output_path






#======================================================================================
# CARE CENTER DENSITY WITHIN EACH CLUSTER
#=======================================================================================
def visualize_cluster_metrics(file, viz_dir, basemap_gdf):
    """
    Iterates through each cluster GeoJSON and creates 6 maps:
    Emergency (Count/Dens), Maternity (Count/Dens), Combined (Count/Dens)
    """
    gdf = gpd.read_file(file)
    cluster_id = file.stem # e.g., "cluster_0"
    
    tasks = [
        ('COUNT_EMERGENCY', 'Emergency Count', 'emerg_count'),
        ('EMERGENCY_PER_CAPITA', 'Emergency Density (per 10k)', 'emerg_dens'),
        ('COUNT_MATERNITY', 'Maternity Count', 'mat_count'),
        ('MATERNITY_PER_CAPITA', 'Maternity Density (per 10k)', 'mat_dens'),
        ('COUNT_TOTAL_CARE', 'Combined Count', 'comb_count'),
        ('TOTAL_PER_CAPITA', 'Combined Density (per 10k)', 'comb_dens'),
    ]


    # Plotting loop
    for col, title, suffix in tasks:
        fig, ax = plt.subplots(1, 1, figsize=(8, 8))
        # Use a sequential colormap (e.g.,  'RdYlGn' (Red-Yellow-Green) Red = Low Density/Poor Access)
        basemap_gdf.plot(ax=ax, color='#f2f2f2', edgecolor='#d9d9d9', linewidth=0.5)
        
        gdf.plot(
            column=col, 
            ax=ax, 
            legend=True, 
            cmap='RdYlGn', 
            scheme='natural_breaks',  #setting to natural jenks
            k=4,
            legend_kwds={'fmt': "{:.2f}"}
        )
        ax.set_title(f"{cluster_id} - {title}")
        ax.axis('off')
        
        # Save to /visualizations/cluster_viz/cluster_X_suffix.png
        save_path = viz_dir / f"{cluster_id}_{suffix}.png"
        plt.savefig(save_path, bbox_inches='tight', dpi=100)
        plt.close(fig)


# Main Execution Logic
def run_cluster_viz(clusters_dir, viz_dir, basemap_gdf):
    """
    Finds all cluster files and triggers the worker function for each.
    """
    clusters_dir = Path(clusters_dir)
    viz_dir = Path(viz_dir)
    viz_dir.mkdir(parents=True, exist_ok=True)
    cluster_files = list(clusters_dir.glob("cluster_*.geojson"))
    
    for file in cluster_files:
        print(f"Processing visualizations for {file.name}...")
        visualize_cluster_metrics(file, viz_dir, basemap_gdf)




#======================================================================================
# MORAN VIZ
#=======================================================================================

def plot_lisa(gdf_lisa, output_path):
    """
    Creates a standard LISA visualization showing all clusters 
    (Hotspots, Coldspots, LH, HL).
    """
    fig, ax = plt.subplots(figsize=(12, 12))
    
    # 1. Define the standard LISA color palette
    # HH: Red, LH: Light Blue, LL: Blue, HL: Light Red, Insignificant: Grey
    lisa_colors = {
        'Hotspot (HH)': '#d7191c',      # Deep Red
        'Coldspot (LL)': '#2c7bb6',     # Deep Blue
        'Low-High (LH)': '#abd9e9',     # Light Blue
        'High-Low (HL)': '#fdae61',     # Light Orange/Red
        'Insignificant': '#eeeeee'      # Light Grey
    }
    
    # Create a custom colormap based on the order of categories in the data
    # We ensure the mapping is consistent
    categories = ['Hotspot (HH)', 'Coldspot (LL)', 'Low-High (LH)', 'High-Low (HL)', 'Insignificant']
    colors = [lisa_colors[cat] for cat in categories]
    cmap = ListedColormap(colors)
    
    # 2. Map the 'lisa_cluster' column to integers to use the colormap
    # This ensures that 'Hotspot (HH)' always gets the first color, etc.
    cat_to_int = {cat: i for i, cat in enumerate(categories)}
    gdf_lisa['lisa_color_idx'] = gdf_lisa['lisa_cluster'].map(cat_to_int)

    # 3. Plot the GDF
    gdf_lisa.plot(
        column='lisa_color_idx', 
        ax=ax, 
        cmap=cmap, 
        edgecolor='black', 
        linewidth=0.2
    )
    
    # 4. Create a custom legend
    # Since we used a custom colormap, we create manual patches for the legend
    legend_handles = [
        mpatches.Patch(color=lisa_colors[cat], label=cat) 
        for cat in categories
    ]
    
    plt.legend(handles=legend_handles, loc='upper right', title="LISA Clusters", frameon=True)
    
    # 5. Clean up the visual
    ax.set_axis_off() # Remove the lat/lon axis for a cleaner look
    plt.title("Spatial Autocorrelation of Healthcare Access (LISA)", fontsize=15)
    
    plt.savefig(output_path, bbox_inches='tight', dpi=300)
    plt.close()



#======================================================================================
# ACCESSIBILITY
#=======================================================================================
def plot_hospital_distribution(orp_gdf, em_gdf, mat_gdf):
    fig, ax = plt.subplots(figsize=(10, 10))

    # 1. Plot the ORP boundaries as a neutral grey background
    orp_gdf.plot(ax=ax, color="#f2f2f2", edgecolor="#bcbcbc", linewidth=0.5)

    # 2. Plot Emergency Hospitals (Blue)
    em_gdf.plot(
        ax=ax, 
        color="blue", 
        markersize=15, 
        alpha=0.6, 
        label="Emergency (Lvl 1-2)",
        marker='o'
    )

    # 3. Plot Maternity Hospitals (Red)
    mat_gdf.plot(
        ax=ax, 
        color="red", 
        markersize=15, 
        alpha=0.6, 
        label="Maternity (Lvl 1-2)",
        marker='x' # Use an 'x' so you can see when they overlap
    )

    ax.set_title("Distribution of Emergency vs. Maternity Hospitals (Level 1-2)", fontsize=14)
    ax.legend(loc="lower right")
    ax.set_axis_off()
    
    plt.tight_layout()
    return fig



def plot_accessibility_map(
    gdf:          gpd.GeoDataFrame,
    column:       str,
    district_col: str,
    title:        str,
    poi_type:     str,
    cmap:         str,
    show_legend:  bool = True,
    label_districts: bool = True, # Added toggle for labels
) -> plt.Figure:
    """
    Choropleth map of an accessibility metric across districts.
    RdYlGn_r: red = poor access (high travel time), green = good access.
    """
    fig, ax = plt.subplots(figsize=(12, 12))

    # 1. Base layer: Plot all polygons in light grey to handle NaNs
    gdf.plot(
        ax=ax, 
        color="#d3d3d3", 
        edgecolor="white", 
        linewidth=0.5
    )

    # 2. Data layer: Plot the travel times
    gdf.plot(
        column=column,
        cmap=cmap,
        legend=show_legend,
        legend_kwds={
            "label": "Travel time (minutes)",
            "shrink": 0.5,
            "orientation": "horizontal",
        },
        edgecolor="white",
        linewidth=0.5,
        ax=ax,
    )

    # 3. District Labels (Optional)
    if label_districts:
        for _, row in gdf.iterrows():
            # Use the centroid of the geometry for text placement
            centroid = row.geometry.centroid
            ax.annotate(
                row[district_col],
                xy=(centroid.x, centroid.y),
                fontsize=6,
                ha="center",
                va="center",
                color="black",
                alpha=0.7
            )

    ax.set_title(title, fontsize=15, pad=20)
    ax.set_axis_off()
    
    return fig



def plot_access_vs_socio(
    gdf:          gpd.GeoDataFrame,
    travel_col:   str,
    socio_col:    str,
    district_col: str,
    poi_type:     str,
    max_distance: float,
    show_legend:  bool = True,
) -> plt.Figure:
    """
    Scatter plot of mean accessibility distance vs socioeconomic index.

    Each point is a district. Points in the top-right quadrant
    (high distance + high poverty) are experiencing compound
    deprivation — the core spatial justice finding.
    """
    data = gdf[[district_col, travel_col, socio_col]].dropna()

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.scatter(
        data[travel_col],
        data[socio_col],
        color="steelblue",
        alpha=0.7,
        s=60,
        edgecolors="white",
        linewidth=0.5,
    )

    # label each point
    for _, row in data.iterrows():
        ax.annotate(
            row[district_col],
            xy=(row[travel_col], row[socio_col]),
            fontsize=7,
            xytext=(4, 4),
            textcoords="offset points",
        )

    # quadrant lines at medians
    ax.axvline(data[travel_col].median(), color="grey",
               linestyle="--", linewidth=0.8, alpha=0.6)
    ax.axhline(data[socio_col].median(), color="grey",
               linestyle="--", linewidth=0.8, alpha=0.6)

    # annotate quadrants
    xmax = data[travel_col].max()
    ymax = data[socio_col].max()
    ax.text(xmax * 0.98, ymax * 0.98, "Compound\ndeprivation",
            ha="right", va="top", fontsize=8,
            color="red", alpha=0.7)
    
    ax.set_xlabel(f"Travel time to nearest {poi_type} (minutes)", fontsize=11)
    ax.set_ylabel(f"{socio_col} (%)", fontsize=11)

    if show_legend:
        ax.legend(
            handles=[
                plt.Line2D([0], [0], color="grey", linestyle="--", linewidth=0.8,
                        label="Median (dashed lines)"),
                plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="steelblue",
                        markersize=8, label="ORP unit"),
            ],
            loc="lower right",
            fontsize=8,
            frameon=True,
        )

    ax.set_title(
        f"Accessibility vs Socioeconomic Index\n"
        f"{poi_type.capitalize()} within {max_distance}minutes — Czech Republic",
        fontsize=12
    )
    return fig



def plot_network_accessibility(
    gdf:           gpd.GeoDataFrame,
    graph,
    accessibility: gpd.DataFrame,
    column:        str,
    title:         str,
    cmap:          str,
    poi_type:      str,
) -> plt.Figure:
    """
    Plots node-level accessibility as a colored scatter overlay
    on top of the district polygon boundaries.

    Each dot is a network node colored by its accessibility value.
    RdYlGn_r: red = far from POI (poor access), green = close (good access).
    The district boundaries give spatial reference without dominating the map.

    Args:
        gdf:           GeoDataFrame of district polygons
        graph:         osmnx graph — used to retrieve node coordinates
        accessibility: DataFrame from compute_accessibility
        column:        which column to visualize (dist_1, opportunities, etc.)
        title:         plot title — auto-generated if None
        cmap:          matplotlib colormap

    Returns:
        matplotlib Figure
    """

    nodes  = ox.graph_to_gdfs(graph, nodes=True, edges=False)
    values = accessibility[column].reindex(nodes.index)

    # clip nodes to the GeoDataFrame boundary
    # routing used the full network — display only what's inside
    boundary       = gdf.to_crs(epsg=4326).union_all()
    nodes_clipped  = nodes[nodes.geometry.within(boundary)]
    values_clipped = values.reindex(nodes_clipped.index)

    if title is None:
        label = "Distance to nearest POI (m)" if "dist" in column else "Opportunities"
        title = f"Network Accessibility — {label}\n{poi_type.capitalize()} within {max_distance}min — Czech Republic"

    fig, ax = plt.subplots(figsize=(12, 12))

    gdf.to_crs(epsg=4326).plot(
        ax=ax,
        color="lightgrey",
        edgecolor="white",
        linewidth=0.8,
        alpha=0.6,
    )

    sc = ax.scatter(
        nodes_clipped["x"],
        nodes_clipped["y"],
        c=values_clipped,
        cmap=cmap,
        s=3,
        alpha=0.7,
        linewidths=0,
    )

    plt.colorbar(
        sc, ax=ax,
        label="minutes" if "dist" in column else "count",
        shrink=0.5,
        pad=0.01,
    )

    ax.set_title(title, fontsize=13, pad=12)
    ax.set_axis_off()
    return fig






