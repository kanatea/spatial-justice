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
        ch_score = calinski_harabasz_score(X, km.labels_) #pseudo f score
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


# characterize each cluster by the mean of each feature per cluster 
def print_cluster_characteristics(df: gpd.DataFrame, features: List[str]):
    """
    Calculates and prints the raw mean values for each feature per cluster.
    Use this to describe the 'average' region in each cluster.
    """
    # Group by cluster and calculate the mean
    characteristics = df.groupby('cluster')[features].mean()
    
    print("\n" + "="*70)
    print("STEP 1: CLUSTER CHARACTERISTICS (Raw Means)")
    print("="*70)
    print(characteristics)
    print("="*70 + "\n")
    
    return characteristics


# highlights the defining features of each cluster by taking the z score of the features in each cluster relative to the global mean
def print_defining_features(df: gpd.DataFrame, features: List[str]):
    """
    Calculates the Z-score of cluster means relative to the global mean.
    Values > 1.0 or < -1.0 indicate a defining characteristic.
    """
    # 1. Calculate global statistics
    global_means = df[features].mean()
    global_stds = df[features].std()
    
    # 2. Calculate cluster means
    cluster_means = df.groupby('cluster')[features].mean()
    
    # 3. Compute Z-scores: (Cluster Mean - Global Mean) / Global Std
    z_scores = (cluster_means - global_means) / global_stds
    
    print("\n" + "="*70)
    print("STEP 2: DEFINING FEATURES (Z-Scores)")
    print("Interpretation: > 1.0 (High) | < -1.0 (Low)")
    print("="*70)
    print(z_scores)
    print("="*70 + "\n")
    
    return z_scores


#CODE TO SEPARATE CLUSTERS TO CONDUCT SUBSEQUENT ANALYSES
#Moran's I and accessibility analyses will run per cluster...

def export_clusters_separately(gdf, output_dir):
    """Saves each cluster into a separate GeoJSON file."""
    for cluster_id in sorted(gdf["cluster"].unique()):
        subset = gdf[gdf["cluster"] == cluster_id]
        path = output_dir / f"cluster_{cluster_id}.geojson"
        subset.to_file(path, driver="GeoJSON")
        logger.info(f"Saved cluster {cluster_id} -> {path.name}")