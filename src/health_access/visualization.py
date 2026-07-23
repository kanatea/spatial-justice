import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from pathlib import Path
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable


# Creating the cluster map
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
    """
        Args:
            gdf: geodataframe containing clusters
            basemap_gdf: the gdf containing the boundaries to use for the basemap
            project_root: directory
            n_clusters: the number of clusters
            with_points: indicates whether we will plug point data in 
            point_mapping: column+location of points
    """
    # Dynamic filename
    # If ax is provided, we don't create a new figure or save a file
    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 10))
        output_path = project_root / f"visualizations/map_clusters_{n_clusters}.png"
    
    #plot the clusters
    basemap_gdf.plot(ax=ax, color='#f2f2f2', edgecolor='#282525', linewidth=0.6)

    clusters = sorted(gdf['cluster'].unique())
    
    # Use passed palette or fallback to the professional default
    if color_palette is None:
        color_palette = ["#e6194b", "#4363d8", "#f58231", "#3cb44b", "#ffe119", "#f032e6", "#911eb4", "#42d4f4", "#a9a9a9"]
    
    # Slice to match number of clusters
    selected_colors = color_palette[:len(clusters)]
    color_map = {cluster: color for cluster, color in zip(clusters, selected_colors)}
    gdf['color'] = gdf['cluster'].map(color_map)

    # Plot the clusters on top of the grey basemap
    gdf.plot(color=gdf['color'], legend=False, ax=ax, edgecolor='#282525', linewidth=0.6)

    # OVERLAY POINTS (Using the specific aesthetics requested)
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
    
    plt.savefig(output_path, bbox_inches='tight', dpi=300)
    plt.close()
    return output_path

#==============================
# CARE CENTER DENSITY WITHIN EACH CLUSTER (CONSOLIDATED GRID LAYOUT)
#==============================
def visualize_cluster_metrics(file, viz_dir, basemap_gdf):
    """
    Iterates through each cluster GeoJSON and creates a single consolidated
    image layout containing all 6 metric subplots (Count vs Density).
    
    Args:
        file: for every file in cluster_files, a specified directory called in run_cluster_viz
        viz_dir: directory for visualization outuput
    """
    # Fallback to engine="fiona" if pyogrio encounters C-level GEOS memory allocation errors
    try:
        gdf = gpd.read_file(file, engine="fiona")
    except Exception:
        gdf = gpd.read_file(file)

    gdf["geometry"] = gdf["geometry"].make_valid() # Ensure geometries are valid for plotting

    cluster_id = file.stem # e.g. "cluster_0"
    
    tasks = [
        ('COUNT_EMERGENCY', 'Emergency Count', 0, 0),
        ('EMERGENCY_PER_CAPITA', 'Emergency Density (per 10k)', 0, 1),
        ('COUNT_MATERNITY', 'Maternity Count', 1, 0),
        ('MATERNITY_PER_CAPITA', 'Maternity Density (per 10k)', 1, 1),
        ('COUNT_TOTAL_CARE', 'Combined Count', 2, 0),
        ('TOTAL_PER_CAPITA', 'Combined Density (per 10k)', 2, 1),
    ]

    # CONSTRAINED_LAYOUT: Automatically distributes maps evenly across the canvas
    fig, axes = plt.subplots(3, 2, figsize=(16, 18), constrained_layout=True)
    
    fig.suptitle(
        f"Socioeconomic Profile Slices: {cluster_id.upper()}", 
        fontsize=30, 
        weight='bold'
    )

    # Plotting loop across the grid axes
    for col, title, row_idx, col_idx in tasks:
        ax = axes[row_idx, col_idx]
        
        # Render grey contextual basemap background
        basemap_gdf.plot(ax=ax, color="#e5e6e8", edgecolor="#282525", linewidth=0.6)
        
        # Overlay clustered geographic attribute boundaries
        gdf.plot(
            column=col, 
            ax=ax, 
            legend=True, 
            cmap='RdYlGn', 
            scheme='natural_breaks', #setting to natural jenks
            edgecolor='#282525',
            linewidth=0.6, 
            k=4,
            legend_kwds={
                'fmt': "{:.2f}",
                # MOVE LEGEND OUTSIDE: Bounding box anchor pushes legend clear of map polygons
                'bbox_to_anchor': (0.98, 0.05),
                'loc': 'lower right',
                'frameon': True,
                'facecolor': 'white',
                'edgecolor': 'none',
                'fontsize': 8
            }
        )
        ax.set_title(title, fontsize=13, weight='semibold', pad=6)
        ax.axis('off')

    # Save the consolidated layout file directly to your visualizations directory
    save_path = viz_dir / f"{cluster_id}_metrics_summary.png"
    plt.savefig(save_path, dpi=300)
    plt.close(fig)


# Main Execution Logic
def run_cluster_viz(clusters_dir, viz_dir, basemap_gdf):
    """
    Finds all cluster files and triggers the worker function for each using visualize_cluster_metrics. 
    Execution function that is called into main.
    
    Args:
            clusters_dir: directory containing clusters to be visualized
            viz_dir: directory for visualization output
    """
    clusters_dir = Path(clusters_dir)
    viz_dir = Path(viz_dir)
    viz_dir.mkdir(parents=True, exist_ok=True)
    cluster_files = list(clusters_dir.glob("cluster_*.geojson"))
    
    for file in cluster_files:
        print(f"Processing consolidated visualizations for {file.name}...")
        visualize_cluster_metrics(file, viz_dir, basemap_gdf)

#==============================
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
    plt.title("Spatial Autocorrelation of Access for All Care Centers (LISA)", fontsize=15)
    
    plt.savefig(output_path, bbox_inches='tight', dpi=300)
    plt.close()

#==============================
# ACCESSIBILITY
#=======================================================================================

#optional and test to see the hospital distribution
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


#main accessibility map
def plot_accessibility_map(
    gdf:          gpd.GeoDataFrame,
    column:       str,
    district_col: str,
    title:        str,
    output_path:  str,
    cmap:         str,
    show_legend:  bool = True,
    label_districts: bool = True, # toggle for labels
) -> plt.Figure:
    """
    Choropleth map of an accessibility metric across districts.
    RdYlGn_r: red = poor access (high travel time), green = good access.
    
    Args:
        gdf: main accessibility gdf
        column: column containing travel time being mapped
        district_col: name of districts
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

    fig.savefig(output_path, bbox_inches="tight", dpi=300)
    
    return fig



#==============================
# ACCESSIBILITY - ONE FIGURE
#=======================================================================================

def visualize_cluster_accessibility_8panel(
    cluster_gdf,
    viz_dir,
    basemap_gdf,
    value_col,
    output_path,
    cluster_col,
    cmap="RdYlGn_r",
    title_label=None,
):
    """
    Create an 8-panel figure:
      - 4 rows = clusters
      - left column = global accessibility scale
      - right column = within-cluster accessibility scale
    Args:
        cluster_gdf: gdf containing cluster information
        value_col: time column
        cluster_col: cluster column
    """
    viz_dir = Path(viz_dir)
    viz_dir.mkdir(parents=True, exist_ok=True)

    gdf = cluster_gdf.copy()
    gdf = gdf[gdf.geometry.notna()].copy()
    gdf = gdf[gdf[value_col].notna()].copy()
    gdf = gdf[gdf.is_valid].copy()

    if gdf.empty:
        raise ValueError(f"No valid rows found for column '{value_col}'")

    if basemap_gdf.crs != gdf.crs:
        basemap_gdf = basemap_gdf.to_crs(gdf.crs)

    cluster_ids = sorted(gdf[cluster_col].dropna().unique())

    fig, axes = plt.subplots(
        nrows=len(cluster_ids),
        ncols=2,
        figsize=(16, 6.2 * len(cluster_ids)),
        gridspec_kw={
        "hspace": 0.18,
        "wspace": 0.05
        }
    )

    fig.subplots_adjust(top=0.93, bottom=0.04, left=0.04, right=0.98)

    if len(cluster_ids) == 1:
        axes = [axes]

    pretty_name = title_label if title_label else value_col.replace("_", " ").title()

    fig.suptitle(
        f"Cluster Accessibility Comparison: {pretty_name}",
        fontsize=22,
        weight="bold",
        y=0.985
    )

    global_vmin = gdf[value_col].min()
    global_vmax = gdf[value_col].max()

    for row_idx, cluster_id in enumerate(cluster_ids):
        cluster_subset = gdf[gdf[cluster_col] == cluster_id].copy()

        ax_left = axes[row_idx][0]
        basemap_gdf.plot(
            ax=ax_left,
            color="#cfcfcf",
            edgecolor="white",
            linewidth=0.5
        )

        cluster_subset.plot(
            column=value_col,
            ax=ax_left,
            cmap=cmap,
            vmin=global_vmin,
            vmax=global_vmax,
            edgecolor="white",
            linewidth=0.5,
            legend=True,
            legend_kwds={
                "label": "Travel time (minutes)",
                "shrink": 0.42,
                "orientation": "horizontal",
                "pad": 0.01,
            }
        )

        ax_left.set_title(
            f"Cluster {cluster_id}: Global Scale",
            fontsize=12,
            weight="semibold",
            pad=10
        )
        ax_left.axis("off")

        ax_right = axes[row_idx][1]
        basemap_gdf.plot(
            ax=ax_right,
            color="#cfcfcf",
            edgecolor="white",
            linewidth=0.5
        )

        local_vmin = cluster_subset[value_col].min()
        local_vmax = cluster_subset[value_col].max()

        cluster_subset.plot(
            column=value_col,
            ax=ax_right,
            cmap=cmap,
            vmin=local_vmin,
            vmax=local_vmax,
            edgecolor="white",
            linewidth=0.5,
            legend=True,
            legend_kwds={
                "label": "Travel time (minutes)",
                "shrink": 0.42,
                "orientation": "horizontal",
                "pad": 0.01,
            }
        )

        ax_right.set_title(
            f"Cluster {cluster_id}: Within-Cluster Scale",
            fontsize=12,
            weight="semibold",
            pad=10
        )
        ax_right.axis("off")

    plt.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"Saved: {output_path}")



#==============================
# ACCESSIBILITY - CLUSTER INDIVIDUAL MAPS 
#=======================================================================================

def get_n_highlight(n_orps):
    """
    Decide how many best/worst ORPs to highlight based on cluster size.
    """
    if n_orps <= 5:
        return 1
    elif n_orps <= 30:
        return 3
    else:
        return 5

#NOT VIZ - for printing
def print_highlighted_orps(
    cluster_gdf,
    cluster_id,
    label_col,
    maternity_col,
    emergency_col,
    maternity_count_col,
    emergency_count_col,
    maternity_rank_col,
    emergency_rank_col,
    n_highlight
):
    """
    Print highlighted ORPs using the union of best/worst ORPs from both
    maternity and emergency rankings, while keeping the original output format.
    
    Args:
            cluster_gdf: gdf containing cluster information
            cluster_id: cluster column
            label_col: district name
            maternity_col: time
            emergency_col: time
            count_col: count of centers
            rank_col: ranking
            n_highlight: number of best/worst 
        """
    maternity_highlighted = select_best_worst_by_rank(
        cluster_gdf, maternity_rank_col, n_highlight
    ).copy()

    emergency_highlighted = select_best_worst_by_rank(
        cluster_gdf, emergency_rank_col, n_highlight
    ).copy()

    combined = pd.concat(
        [maternity_highlighted, emergency_highlighted],
        ignore_index=True
    )

    if combined.empty:
        print("\n" + "=" * 80)
        print(f"Cluster {cluster_id}")
        print("=" * 80)
        print("No highlighted ORPs.")
        print("=" * 80)
        return

    combined = combined.drop_duplicates(subset=[label_col]).copy()

    print("\n" + "=" * 80)
    print(f"Cluster {cluster_id}")
    print("=" * 80)

    for group in ["Best", "Worst"]:
        subset = combined[combined["highlight_group"] == group].copy()

        print(f"\n{group} ORPs shown on map:")
        print("-" * 80)

        if subset.empty:
            print("None")
            continue

        printable = subset[
            [
                label_col,
                maternity_col,
                emergency_col,
                maternity_count_col,
                emergency_count_col
            ]
        ].copy()

        printable = printable.rename(columns={
            label_col: "ORP Name",
            maternity_col: "Maternity Travel Time",
            emergency_col: "Emergency Travel Time",
            maternity_count_col: "Maternity Locations",
            emergency_count_col: "Emergency Locations"
        })

        print(printable.to_string(index=False))

    print("=" * 80)


def compute_summary_stats(series):
    """
    Return rounded summary statistics for a numeric series.
    """
    return {
        "Mean": round(series.mean(), 1),
        "Min": round(series.min(), 1),
        "Max": round(series.max(), 1),
        "Std Dev": round(series.std(), 1) if len(series) > 1 else 0.0
    }


def select_best_worst_by_rank(gdf, rank_col, n_select):
    """
    Select top best (lowest rank) and worst (highest rank).
    """
    gdf_valid = gdf[gdf[rank_col].notna()].copy()

    best = gdf_valid.nsmallest(n_select, rank_col).copy()
    worst = gdf_valid.nlargest(n_select, rank_col).copy()

    best["highlight_group"] = "Best"
    worst["highlight_group"] = "Worst"

    selected = pd.concat([best, worst], axis=0)
    selected = selected.loc[~selected.index.duplicated(keep="first")].copy()

    return selected


def add_labels(ax, gdf, label_col, dx=8, dy=8):
    """
    Label selected ORPs using representative points.
    """
    for _, row in gdf.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue

        pt = row.geometry.representative_point()
        ax.annotate(
            text=str(row[label_col]),
            xy=(pt.x, pt.y),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=7,
            fontweight="bold",
            ha="left",
            va="bottom",
            #bbox=dict(
            #    boxstyle="round,pad=0.2",
            #    fc="white",
            #    ec="none",
            #    alpha=0.85
        )


def add_stats_table(ax, stats_dict):
    """
    Add a horizontal summary-stat table below a map.
    Labels appear across the top row.
    """
    col_labels = list(stats_dict.keys())
    cell_text = [[v for v in stats_dict.values()]]

    table = ax.table(
        cellText=cell_text,
        colLabels=col_labels,
        loc="bottom",
        cellLoc="center",
        bbox=[0.05, -0.38, 0.90, 0.14]  # x, y, width, height
    )

    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.0, 1.3) #increases row height

def add_horizontal_colorbar(fig, ax, vmin, vmax, cmap, label="Travel time (minutes)"):
    """
    Add a horizontal colorbar below a subplot, outside the map area
    and above the stats table.
    """
    norm = Normalize(vmin=vmin, vmax=vmax)
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])

    pos = ax.get_position()

    # [left, bottom, width, height] in figure coordinates
    cax = fig.add_axes([
        pos.x0 + 0.10 * pos.width, #left right
        pos.y0 + 0.01, #moves higher
        pos.width * 0.84, 
        0.015 #height?
    ])

    cbar = fig.colorbar(sm, cax=cax, orientation="horizontal")
    cbar.set_label(label, fontsize=9)
    cbar.ax.tick_params(labelsize=8)


def plot_single_cluster_access_pair(
    cluster_subset,
    basemap_gdf,
    cluster_id,
    maternity_col,
    emergency_col,
    maternity_rank_col,
    emergency_rank_col,
    label_col,
    output_path,
    cmap="RdYlGn_r"
):
    """
    Create one figure for a single cluster with two maps:
    - left: maternity
    - right: emergency

    Uses precomputed ranking columns to highlight best/worst ORPs.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cluster_subset = cluster_subset.copy()
    cluster_subset = cluster_subset[
        cluster_subset.geometry.notna() &
        cluster_subset.is_valid
    ].copy()

    if cluster_subset.empty:
        raise ValueError(f"Cluster {cluster_id} has no valid geometries")

    if basemap_gdf.crs != cluster_subset.crs:
        basemap_gdf = basemap_gdf.to_crs(cluster_subset.crs)

    n_highlight = get_n_highlight(len(cluster_subset))

    fig, axes = plt.subplots(1, 2, figsize=(16, 10))
    fig.suptitle(
        f"Cluster {cluster_id}: Accessibility to Nearest Care",
        fontsize=18,
        weight="bold",
        y=0.9 #can decrease, moves the title down
    )
    fig.subplots_adjust(top=0.92) #can increase, moves plots up

    map_specs = [
        (axes[0], maternity_col, maternity_rank_col, "Nearest Maternity Drive Time"),
        (axes[1], emergency_col, emergency_rank_col, "Nearest Emergency Drive Time"),
    ]

    for ax, value_col, rank_col, title in map_specs:
        plot_gdf = cluster_subset[cluster_subset[value_col].notna()].copy()

        if plot_gdf.empty:
            ax.set_title(f"{title}\nNo data")
            ax.axis("off")
            continue

        basemap_gdf.plot(
            ax=ax,
            color="#cfcfcf",
            edgecolor="white",
            linewidth=0.5
        )

        vmin = plot_gdf[value_col].min()
        vmax = plot_gdf[value_col].max()

        plot_gdf.plot(
            column=value_col,
            ax=ax,
            cmap=cmap,
            edgecolor="white",
            linewidth=0.5,
            legend=False,
            vmin=vmin,
            vmax=vmax
        )

        highlighted = select_best_worst_by_rank(plot_gdf, rank_col, n_highlight)

        best_gdf = highlighted[highlighted["highlight_group"] == "Best"]
        worst_gdf = highlighted[highlighted["highlight_group"] == "Worst"]

        if not best_gdf.empty:
            best_gdf.boundary.plot(
                ax=ax,
                color="#0C470F",
                linewidth=1.5,
                linestyle="solid"
            )

        if not worst_gdf.empty:
            worst_gdf.boundary.plot(
                ax=ax,
                color="#600910",
                linewidth=1.5,
                linestyle="solid"
            )

        add_labels(ax, highlighted, label_col)

        legend_handles = [
            Line2D(
                [0], [0],
                color="#0C470F",
                lw=2,
                linestyle="solid",
                label=f"Best {n_highlight}"
            ),
            Line2D(
                [0], [0],
                color="#600910",
                lw=2,
                linestyle="solid",
                label=f"Worst {n_highlight}"
            ),
        ]
        ax.legend(
            handles=legend_handles,
            loc="upper left",
            bbox_to_anchor=(0.01, -0.01), #y anchor higher or lower 
            fontsize=9,
            frameon=True,
            borderaxespad=0.0
        )

        add_horizontal_colorbar(fig, ax, vmin, vmax, cmap)

        stats_dict = compute_summary_stats(plot_gdf[value_col])

        ax.set_title(title, fontsize=12, weight="semibold")
        ax.axis("off")

        add_stats_table(ax, stats_dict)

    fig.subplots_adjust(top=0.90, bottom=0.30, left=0.05, right=0.95, wspace=0.08) #adjust the size of the image

    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")
        


def visualize_all_clusters_access_pairs(
    cluster_gdf,
    basemap_gdf,
    output_dir,
    cluster_col,
    label_col,
    maternity_col,
    emergency_col,
    maternity_count_col,
    emergency_count_col,
    maternity_rank_col="ranking_maternity",
    emergency_rank_col="ranking_emergency",
    cmap="RdYlGn_r"
):
    """
    Create one 2-map figure per cluster using precomputed ranking columns.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    gdf = cluster_gdf.copy()
    gdf = gdf[gdf.geometry.notna()].copy()
    gdf = gdf[gdf.is_valid].copy()

    cluster_ids = sorted(gdf[cluster_col].dropna().unique())

    for cluster_id in cluster_ids:
        cluster_subset = gdf[gdf[cluster_col] == cluster_id].copy()
        n_highlight = get_n_highlight(len(cluster_subset))

        print_highlighted_orps(
            cluster_gdf=cluster_subset,
            cluster_id=cluster_id,
            title="Nearest Maternity Drive Time",
            label_col=label_col,
            maternity_col=maternity_col,
            emergency_col=emergency_col,
            maternity_count_col=maternity_count_col,
            emergency_count_col=emergency_count_col,
            maternity_rank_col=maternity_rank_col,
            emergency_rank_col=emergency_rank_col,
            n_highlight=n_highlight
        )

        output_path = output_dir / f"cluster_{cluster_id}_access_pair.png"

        plot_single_cluster_access_pair(
            cluster_subset=cluster_subset,
            basemap_gdf=basemap_gdf,
            cluster_id=cluster_id,
            maternity_col=maternity_col,
            emergency_col=emergency_col,
            maternity_rank_col=maternity_rank_col,
            emergency_rank_col=emergency_rank_col,
            label_col=label_col,
            output_path=output_path,
            cmap=cmap
        )



# SCATTERPLOTS

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
    Each point is a district. Points in the top-right quadrant (high distance + high poverty)
    are experiencing compound deprivation.
    """
    data = gdf[[district_col, travel_col, socio_col]].dropna()

    # create the scatter plot
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
               linestyle="--", linewidth=1, alpha=0.6)
    ax.axhline(data[socio_col].median(), color="grey",
               linestyle="--", linewidth=1, alpha=0.6)

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
        f"{poi_type.capitalize()} within {round(max_distance, 2)} minutes — Czech Republic",
        fontsize=12
    )
    return fig