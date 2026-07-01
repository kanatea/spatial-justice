import pandas as pd
import geopandas as gpd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import logging
from typing import List

logger = logging.getLogger(__name__)

def apply_clustering(df: gpd.DataFrame, features: List[str], n_clusters: int, random_state: int) -> gpd.DataFrame:
    """
    Performs K-Means clustering using explicit parameters
    Returns:
        DataFrame with an added 'cluster' column.
    """
    #Make sure all requested features exist
    missing_cols = [col for col in features if col not in df.columns]
    if missing_cols:
        raise KeyError(f"The following features are missing from the DataFrame: {missing_cols}")

    X = df[features]

    # Scale the data, StandardScaler is a feature from scikit-learn
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    logger.info(f"Data scaled successfully using {len(features)} features.")

    # Fit the model
    logger.info(f"Fitting KMeans with n_clusters={n_clusters}...")
    kmeans = KMeans(
        n_clusters=n_clusters, 
        #random state is for randomization seed
        random_state=random_state,
        n_init='auto'  # Added to avoid sklearn warnings in newer versions
    ) 
    
    # Create a copy to avoid SettingWithCopyWarning
    df_result = df.copy()
    df_result['cluster'] = kmeans.fit_predict(X_scaled)
    
    # this line changes the cluster labels to start from 1 instead of 0, which is more intuitive for users and it will be easier to read in the visualizations.
    # we can delete it if we want to keep the original labels.
    df_result['cluster'] = df_result['cluster'] + 1
    
    logger.info("Clustering complete. Cluster labels added to dataframe.")
    return df_result

#CODE TO SEPARATE CLUSTERS TO CONDUCT SUBSEQUENT ANALYSES
#Moran's I and accessibility analyses will run per cluster...

def export_clusters_separately(gdf, output_dir):
    """Saves each cluster into a separate GeoJSON file."""
    for cluster_id in sorted(gdf["cluster"].unique()):
        subset = gdf[gdf["cluster"] == cluster_id]
        path = output_dir / f"cluster_{cluster_id}.geojson"
        subset.to_file(path, driver="GeoJSON")
        logger.info(f"Saved cluster {cluster_id} -> {path.name}")