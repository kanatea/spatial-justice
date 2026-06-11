import geopandas as gpd
import matplotlib.pyplot as plt
import os
from pathlib import Path

def create_cluster_map(gdf, config, project_root):
    """
    Renders the clustered GeoDataFrame and saves it as a PNG.
    """
    # Resolve the output path
    processed_dir = project_root / config['paths']['processed_dir']
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_path = processed_dir / config['visualization']['output_filename']

    # Create the plot
    fig, ax = plt.subplots(figsize=(12, 10))
    
    gdf.plot(
        column='cluster', 
        cmap=config['visualization']['cmap'], 
        legend=False, 
        ax=ax, 
        edgecolor='white', 
        linewidth=0.5
    )
    
    plt.title(config['visualization']['title'], fontsize=15)
    ax.set_axis_off() 
    
    # Save the file
    plt.savefig(output_path, bbox_inches='tight', dpi=300)
    plt.close()
    
    return output_path