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