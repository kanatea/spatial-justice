import pandas as pd
import geopandas as gpd
import logging
from typing import List

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import calinski_harabasz_score, silhouette_score
#from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

def find_optimal_k(df: gpd.DataFrame, features: List[str], random_state: int, max_k=10):
    #Make sure all requested features exist
    missing_cols = [col for col in features if col not in df.columns]
    if missing_cols:
        raise KeyError(f"The following features are missing from the DataFrame: {missing_cols}")

    X = df[features]
    
    ch_scores = []
    sil_scores = []
    k_range = range(2, max_k + 1)

    for k in k_range:
        # n_init=10 is explicitly set to avoid warnings in newer sklearn versions
        km = KMeans(n_clusters=k, random_state=random_state, n_init=10).fit(X)
        
        # Calculate scores
        ch_score = calinski_harabasz_score(X, km.labels_)
        sil_score = silhouette_score(X, km.labels_)
        
        ch_scores.append(ch_score)
        sil_scores.append(sil_score)

    # --- PRINTING SECTION ---
    print("\n" + "="*45)
    print(f"{'K':<5} | {'Pseudo F (CH)':<18} | {'Silhouette':<12}")
    print("-" * 45)
    
    for k, ch, sil in zip(k_range, ch_scores, sil_scores):
        print(f"{k:<5} | {ch:<18.2f} | {sil:<12.4f}")
    
    print("="*45)
    # ------------------------

    # Return the K that maximizes the Pseudo F-statistic
    optimal_k = k_range[np.argmax(ch_scores)]
    return optimal_k, ch_scores, sil_scores


def apply_clustering(df: gpd.DataFrame, features: List[str], n_clusters: int, random_state: int) -> gpd.DataFrame:
    """
    Performs K-Means clustering using explicit parameters
    Returns:
        DataFrame with an added 'cluster' column.
    """
    missing_cols = [col for col in features if col not in df.columns]
    if missing_cols:
        raise KeyError(f"The following features are missing from the DataFrame: {missing_cols}")
    
    X = df[features]

    # Fit the model
    logger.info(f"Fitting KMeans with n_clusters={n_clusters}...")
    kmeans = KMeans(
        n_clusters=n_clusters, 
        #random state is for randomization seed
        random_state=random_state,
        n_init=10  # Defining 10 for reproducibility
    ) 
    
    # Create a copy to avoid SettingWithCopyWarning
    df_result = df.copy()
    df_result['cluster'] = kmeans.fit_predict(X)
    
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