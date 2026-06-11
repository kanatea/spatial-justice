import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from pathlib import Path


def create_cluster_map(gdf, config, project_root, show_legend=False):
    """
    Renders the clustered GeoDataFrame and saves it as a PNG.
    ### ADD MORE DESRCIPTION
    """
    # Resolve the output path
    processed_dir = project_root / config['paths']['processed_dir']
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_path = processed_dir / config['visualization']['output_filename']

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


    gdf['color'] = gdf['cluster'].apply(lambda x: colors[clusters.index(x)])
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
            mpatches.Patch(color=colors[i], label=f"Cluster {i + 1}")
            for i, cluster in enumerate(clusters)
        ]
        ax.legend(handles=patches, loc="upper right", frameon=True)
    
    n = config['clustering']['n_clusters']
    plt.title(f"{config['visualization']['title']} --- {n} clusters", fontsize=15)
    ax.set_axis_off() 
    
    # Save the file
    plt.savefig(output_path, bbox_inches='tight', dpi=300)
    plt.close()
    
    return output_path