import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
import pandas as pd
import osmnx as ox


#======================================================================================
# CLUSTER MAP
#=======================================================================================


def create_cluster_map(
    gdf, 
    project_root, 
    n_clusters, 
    with_points=False, 
    point_mapping=None, 
    points_dir=None, 
    show_legend=False, 
    title="Cluster Map"
):
  
    # Dynamic filename based on whether points are included
    suffix = "with_points" if with_points else "no_points"
    output_path = project_root / f"visualizations/map_clusters_{n_clusters}_{suffix}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True) # Ensure the directory exists

    fig, ax = plt.subplots(figsize=(12, 10))
    
    clusters = sorted(gdf['cluster'].unique())
    colors = ["#e6194b", "#4363d8", "#f58231", "#3cb44b", "#ffe119", "#f032e6", "#911eb4", "#42d4f4", "#a9a9a9"][:len(clusters)]
    color_map = {cluster: color for cluster, color in zip(clusters, colors)}
    gdf['color'] = gdf['cluster'].map(color_map)

    # Plot the clusters
    gdf.plot(color=gdf['color'], legend=False, ax=ax, edgecolor='white', linewidth=0.5)

    # OVERLAY POINTS
    point_handles = []
    if with_points and point_mapping and points_dir:
        point_colors = {"OD_emergency_care.geojson": "black", "OD_maternity_care.geojson": "violet"}
        
        for filename, label in point_mapping.items():
            p_path = points_dir / filename
            if p_path.exists():
                p_gdf = gpd.read_file(p_path)
                if p_gdf.crs != gdf.crs:
                    p_gdf = p_gdf.to_crs(gdf.crs)
                
                # Store the plot object to create a legend handle
                p_plot = p_gdf.plot(
                    ax=ax, 
                    color=point_colors.get(filename, "black"), 
                    markersize=5, 
                    alpha=0.7, 
                    label=label
                )
                # Create a proxy artist for the legend
                point_handles.append(plt.Line2D([0], [0], marker='o', color='w', 
                                              markerfacecolor=point_colors.get(filename, "black"), 
                                              markersize=8, label=label))

    if show_legend:
        # Cluster patches
        patches = [mpatches.Patch(color=colors[i], label=f"Cluster {cluster}") for i, cluster in enumerate(clusters)]
        
        # Combine cluster patches and point handles into one legend
        all_handles = patches + point_handles
        ax.legend(handles=all_handles, loc="upper right", frameon=True)
    
    plt.title(f"{title} ({suffix}) --- {n_clusters} clusters", fontsize=15)
    ax.set_axis_off() 
    plt.savefig(output_path, bbox_inches='tight', dpi=300)
    plt.close()
    return output_path






#======================================================================================
# CARE CENTER DENSITY WITHIN EACH CLUSTER
#=======================================================================================
def visualize_cluster_metrics(file, viz_dir):
    """
    Iterates through each cluster GeoJSON and creates 6 maps:
    Emergency (Count/Dens), Maternity (Count/Dens), Combined (Count/Dens)
    """
    gdf = gpd.read_file(file)
    cluster_id = file.stem # e.g., "cluster_0"
    
    # 1. Calculate Metrics
    pop = gdf['POCET_OBYV'].replace(0, 1) 
    gdf['COUNT_TOTAL'] = gdf['COUNT_EMERGENCY'] + gdf['COUNT_MATERNITY']
    gdf['dens_emergency'] = (gdf['COUNT_EMERGENCY'] / pop) * 1000
    gdf['dens_maternity'] = (gdf['COUNT_MATERNITY'] / pop) * 1000
    gdf['dens_combined'] = (gdf['COUNT_TOTAL'] / pop) * 1000
    
    tasks = [
        ('COUNT_EMERGENCY', 'Emergency Count', 'emerg_count'),
        ('dens_emergency', 'Emergency Density (per 1k)', 'emerg_dens'),
        ('COUNT_MATERNITY', 'Maternity Count', 'mat_count'),
        ('dens_maternity', 'Maternity Density (per 1k)', 'mat_dens'),
        ('COUNT_TOTAL', 'Combined Count', 'comb_count'),
        ('dens_combined', 'Combined Density (per 1k)', 'comb_dens'),
    ]


    # Plotting loop
    for col, title, suffix in tasks:
        fig, ax = plt.subplots(1, 1, figsize=(8, 8))
        # Use a sequential colormap (e.g.,  'RdYlGn' (Red-Yellow-Green) Red = Low Density/Poor Access)
        gdf.plot(
            column=col, 
            ax=ax, 
            legend=True, 
            cmap='RdYlGn', 
            scheme='quantiles', 
            k=4,
            legend_kwds={'fmt': "{:.2f}"}
        )
        ax.set_title(f"{cluster_id} - {title}")
        ax.axis('off')
        
        # Save to /visualizations/cluster_viz/cluster_X_suffix.png
        save_path = viz_dir / f"{cluster_id}_{suffix}.png"
        plt.savefig(save_path, bbox_inches='tight', dpi=300)
        plt.close(fig)


# Main Execution Logic
def run_cluster_viz(clusters_dir, viz_dir):
    """
    Finds all cluster files and triggers the worker function for each.
    """
    clusters_dir = Path(clusters_dir)
    viz_dir = Path(viz_dir)
    viz_dir.mkdir(parents=True, exist_ok=True)
    cluster_files = list(clusters_dir.glob("cluster_*.geojson"))
    
    for file in cluster_files:
        print(f"Processing visualizations for {file.name}...")
        visualize_cluster_metrics(file, viz_dir)




#======================================================================================
# MORAN VIZ
#=======================================================================================
def plot_lisa_overlay(gdf_clustered, lisa_results, output_path):
    fig, ax = plt.subplots(figsize=(12, 12))
    
    if 'lisa_cluster' not in gdf_clustered.columns:
        category_map = {0: 'Insignificant', 1: 'Hotspot (HH)', 2: 'Low-High (LH)', 3: 'Coldspot (LL)', 4: 'High-Low (HL)'}
        gdf_clustered['lisa_cluster'] = [category_map[val] for val in lisa_results.q]

    # 1. Plot the socio-economic clusters as the base layer
    gdf_clustered.plot(
        column='cluster', 
        ax=ax, 
        cmap='Pastel1', 
        legend=True, 
        legend_kwds={'label': "Socio-Economic Cluster"}
    )
    
    # 2. Filter the Coldspots
    coldspots = gdf_clustered[gdf_clustered['lisa_cluster'] == 'Coldspot (LL)']
    
    # 3. Overlay the Coldspots
    if not coldspots.empty:
        coldspots.plot(
            ax=ax, 
            color='red', 
            edgecolor='black', 
            linewidth=1
        )
        
        # 4. FIX: Create a manual proxy artist for the legend
        # This creates a small red square for the legend without needing to link it to the plot
        red_patch = mpatches.Patch(facecolor='red', edgecolor='black', label='Care Center Desert (Coldspot)')
        plt.legend(handles=[red_patch])
    else:
        # If no coldspots, we still want the socio-economic legend to show, 
        # but we don't need the red patch.
        plt.legend()
    
    plt.title("Care Center Deserts vs. Socio-Economic Clusters")
    plt.savefig(output_path)
    plt.close()



#======================================================================================
# ACCESSIBILITY
#=======================================================================================


def plot_accessibility_map(
    gdf:          gpd.GeoDataFrame,
    column:       str,
    district_col: str,
    title:        str,
    poi_type:     str,
    cmap:         str,
    show_legend:  bool = True,
) -> plt.Figure:
    """
    Choropleth map of an accessibility metric across districts.
    RdYlGn_r: red = poor access (high distance), green = good access.
    """
    if title is None:
        title = f"{column} to nearest {poi_type} (meters)"

    fig, ax = plt.subplots(figsize=(10, 10))
    gdf.plot(
        column=column,
        cmap="RdYlGn_r",
        legend=show_legend,
        legend_kwds={
            "label": "Travel time (minutes)",
            "shrink": 0.6,
            "orientation": "horizontal",
        },
        edgecolor="white",
        linewidth=0.5,
        ax=ax,
    )


    # label each district
    for _, row in gdf.iterrows():
        if pd.notna(row[column]):
            ax.annotate(
                row[district_col],
                xy=(row.geometry.centroid.x, row.geometry.centroid.y),
                fontsize=5,
                ha="center",
                color="black",
            )
    ax.set_title(title, fontsize=13, pad=12)
    ax.annotate(
        "Red = maternity takes longer than emergency\nGreen = emergency takes longer than maternity",
        xy=(0.02, 0.02),
        xycoords="axes fraction",
        fontsize=8,
        color="#444444",
    )
    ax.set_axis_off()
    return fig



def plot_access_vs_socio(
    gdf:          gpd.GeoDataFrame,
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
    data = gdf[[district_col, "travel_time", socio_col]].dropna()

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.scatter(
        data["travel_time"],
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
            xy=(row["travel_time"], row[socio_col]),
            fontsize=7,
            xytext=(4, 4),
            textcoords="offset points",
        )

    # quadrant lines at medians
    ax.axvline(data["travel_time"].median(), color="grey",
               linestyle="--", linewidth=0.8, alpha=0.6)
    ax.axhline(data[socio_col].median(), color="grey",
               linestyle="--", linewidth=0.8, alpha=0.6)

    # annotate quadrants
    xmax = data["travel_time"].max()
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






