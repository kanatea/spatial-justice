import logging
import matplotlib.pyplot as plt
import pandas as pd
import geopandas as gpd
import seaborn as sns
from typing import List, Optional

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



# MULTIVARIATE BOX PLOTS

def plot_cluster_characteristics(df: gpd.DataFrame, scaled_features: List[str], color_palette: Optional[List[str]] = None, ax=None, output_path: str = None):
    """
    Replicates ArcGIS Multivariate Clustering boxplot using pre-scaled data.
        - Boxplots represent the global distribution of each feature.
        - Lines connect the scaled means of each cluster across features.
    Args:
        df: The dataframe containing the scaled features and the cluster assignments.
        scaled_features: List of column names (e.g., ["POP_DENS_scaled", ...])
        output_path: Path to save the resulting image.

    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 6))
    
    # 1. Prepare data for the global distribution (Boxplots)
    # We melt the scaled columns so seaborn can plot them as categories on the X-axis
    df_melted = df[scaled_features].melt(var_name='Feature', value_name='ScaledValue')
    
    
    # A. Draw the Global Distribution (Boxplots)
    # These represent the distribution of the scaled data (Mean=0, Std=1)
    sns.boxplot(
        data=df_melted, 
        x='Feature', 
        y='ScaledValue', 
        color='lightgrey', 
        showfliers=False, 
        width=0.6,
        ax=ax
    )
    
    # B. Calculate Cluster Means of the Scaled Data
    # This is the "Cluster Centroid" in scaled space
    cluster_means_scaled = df.groupby('cluster')[scaled_features].mean()
    # Transpose so features are on the X axis for plotting
    means_t = cluster_means_scaled.T 
    
    # Define a color palette for the clusters
     # If a custom palette is provided, use it; otherwise, fallback to tab10
    if color_palette is None:
        palette = sns.color_palette("tab10", len(cluster_means_scaled))
    else:
        # Ensure the palette is long enough for the number of clusters
        palette = color_palette[:len(cluster_means_scaled)]
    
    # C. Draw the Cluster Profiles (Line Plot)
    for i in range(len(cluster_means_scaled)):
        cluster_id = cluster_means_scaled.index[i]
        ax.plot(
            range(1, len(scaled_features) + 1), 
            means_t[cluster_id], 
            marker='o', 
            linewidth=2.5, 
            markersize=8, 
            #label=f'Cluster {cluster_id}', 
            color=palette[i]
        )
    
    # Formatting
    ax.axhline(0, color='black', linestyle='--', linewidth=1, alpha=0.5) 
    ax.set_title("Cluster Characteristics (Standardized)", fontsize=16, pad=20)
    ax.set_ylabel("Standardized Value (Z-Score)", fontsize=16)
    ax.set_xlabel("Features", fontsize=16)
    
    # Clean up X-axis labels (remove '_scaled' for better readability)
    labels = [feat.replace('_scaled', '') for feat in scaled_features]
    ax.set_xticks(range(1, len(labels) + 1))
    ax.tick_params(axis='x', labelsize=13)
    ax.set_xticklabels(labels, rotation=45)
    #ax.legend(title="Clusters", bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.grid(axis='y', linestyle=':', alpha=0.6)

    if ax is not None and output_path is None:
        return None
    
    if output_path:
        # Only call plt.savefig if we are handling the figure independently
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Cluster characteristic plot saved to: {output_path}")
    
    if ax is None: # Only close if we created the figure inside this function
        plt.close()



