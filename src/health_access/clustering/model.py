import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

def apply_clustering(df, config):
    """
    Takes a dataframe and a config dictionary, performs K-Means clustering,
    and returns the dataframe with a 'cluster' column.
    """
    # 1. Extract the features we want to cluster by from the config
    features = config['clustering']['features']
    X = df[features]

# UNDERSTAND THIS AND SCALE IT
    # 2. Scale the data
    # We keep the scaler inside the function or return it if needed for future data
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # X_scaled = X.values # Use the original values since they are already standardized

    # 3. Initialize and fit the model using config values
    kmeans = KMeans(
        n_clusters=config['clustering']['n_clusters'], 
        random_state=config['clustering']['random_state'],
        n_init='auto' # Added to avoid sklearn warnings in newer versions
    ) 
    
    # Create a copy to avoid SettingWithCopyWarning in pandas
    df_result = df.copy() #can change name
    df_result['cluster'] = kmeans.fit_predict(X_scaled)
    
    return df_result #can change name