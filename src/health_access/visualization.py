import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from pathlib import Path
import pandas as pd
import osmnx as ox


def create_cluster_map(gdf, project_root, n_clusters, show_legend=False, title="ORP Clusters based on 9 Selected Variables"):
    """
    Renders the clustered GeoDataFrame and saves it as a PNG.
    
    """
    # Resolve the output path
    processed_dir = project_root / "visualizations"
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_path = processed_dir / f"map_clusters_{n_clusters}.png"

    # Create the plot
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Define a color palette for clusters
    clusters = sorted(gdf['cluster'].unique())
    colors = [
            "#e6194b",  # red
            "#4363d8",  # blue
            "#f58231",  # orange
            "#3cb44b",  # green
            "#ffe119",  # yellow
            "#f032e6",  # pink
            "#911eb4",  # purple
            "#42d4f4",  # cyan
            "#a9a9a9",  # grey
        ][:len(clusters)]

    color_map = {cluster: color for cluster, color in zip(clusters, colors)}
    gdf['color'] = gdf['cluster'].map(color_map)
    gdf.plot(
        color=gdf['color'],
        legend=False, 
        ax=ax, 
        edgecolor='white', 
        linewidth=0.5
    )

    # Add legend if requested buy the user via CLI
    if show_legend:
        patches = [
            mpatches.Patch(color=colors[i], label=f"Cluster {cluster}")
            for i, cluster in enumerate(clusters)
        ]
        ax.legend(handles=patches, loc="upper right", frameon=True)
    
    plt.title(f"{title} --- {n_clusters} clusters", fontsize=15)
    ax.set_axis_off() 
    
    # Save the file
    plt.savefig(output_path, bbox_inches='tight', dpi=300)
    plt.close()
    
    return output_path


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
    processed_dir = project_root / "data/transformed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    # Dynamic filename based on whether points are included
    suffix = "with_points" if with_points else "no_points"
    output_path = project_root / f"visualizations/map_clusters_{n_clusters}_{suffix}.png"

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
        point_colors = {"OD_emergency_care.geojson": "red", "OD_maternity_care.geojson": "blue"}
        
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

## should add something for the legend, poitn colors are not explained right now




## DID NOT PLUG THIS INTO MAIN YET, JUST COPIED AND PASTED FROM ACCESSIBILITY PROJ

def plot_accessibility_map(
    gdf:          gpd.GeoDataFrame,
    column:       str,
    district_col: str,
    title:        str,
    poi_type:     str,
    cmap:         str,
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
        legend=True,
        legend_kwds={"label": "meters", "shrink": 0.6},
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
    ax.set_axis_off()
    return fig


def plot_access_vs_socio(
    gdf:          gpd.GeoDataFrame,
    socio_col:    str,
    district_col: str,
    poi_type:     str,
    max_distance: float,
) -> plt.Figure:
    """
    Scatter plot of mean accessibility distance vs socioeconomic index.

    Each point is a district. Points in the top-right quadrant
    (high distance + high poverty) are experiencing compound
    deprivation — the core spatial justice finding.
    """
    data = gdf[[district_col, "mean_dist", socio_col]].dropna()

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.scatter(
        data["mean_dist"],
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
            xy=(row["mean_dist"], row[socio_col]),
            fontsize=7,
            xytext=(4, 4),
            textcoords="offset points",
        )

    # quadrant lines at medians
    ax.axvline(data["mean_dist"].median(), color="grey",
               linestyle="--", linewidth=0.8, alpha=0.6)
    ax.axhline(data[socio_col].median(), color="grey",
               linestyle="--", linewidth=0.8, alpha=0.6)

    # annotate quadrants
    xmax = data["mean_dist"].max()
    ymax = data[socio_col].max()
    ax.text(xmax * 0.98, ymax * 0.98, "Compound\ndeprivation",
            ha="right", va="top", fontsize=8,
            color="red", alpha=0.7)

    ax.set_xlabel(f"Mean distance to nearest {poi_type} (meters)", fontsize=11)
    ax.set_ylabel(f"{socio_col} (%)", fontsize=11)
    ax.set_title(
        f"Accessibility vs Socioeconomic Index\n"
        f"{poi_type.capitalize()} within {max_distance}m — Münster",
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
        title = f"Network Accessibility — {label}\n{poi_type.capitalize()} within {max_distance}m — Münster"

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
        label="meters" if "dist" in column else "count",
        shrink=0.5,
        pad=0.01,
    )

    ax.set_title(title, fontsize=13, pad=12)
    ax.set_axis_off()
    return fig