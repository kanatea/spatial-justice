import pandas as pd
import geopandas as gpd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import logging

logger = logging.getLogger(__name__)

def apply_clustering(df: gpd.DataFrame, config: dict) -> gpd.DataFrame:
    """
    Performs K-Means clustering based on a configuration dictionary.
    
    Args:
        df: DataFrame containing the census variables.
        config: Dictionary containing 'clustering' settings (features, n_clusters, random_state).
    Returns:
        DataFrame with an added 'cluster' column.
    """
    # Extract features from the config
    features = config['clustering']['features']
    
    # Ensure all requested features exist in the dataframe
    missing_cols = [col for col in features if col not in df.columns]
    if missing_cols:
        raise KeyError(f"The following features are missing from the DataFrame: {missing_cols}")

    X = df[features]

    # Scale the data, StandardScaler is a feature from scikit-learn
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    logger.info(f"Data scaled successfully using {len(features)} features.")

    # Initialize and fit the model
    n_clusters = config['clustering']['n_clusters']
    random_state = config['clustering']['random_state']
    
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
    
    logger.info("Clustering complete. Cluster labels added to dataframe.")
    return df_result