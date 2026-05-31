import logging
import sys
import yaml
import pandas as pd

from health_access.clustering.model import apply_clustering
#from health_access.preprocessing.census_cleaner import some_function


#from health_access.io import load_database
#from health_access.weights import create_rook_swm, create_queen_swm
#from health_access.weights import create_knn_swm, create_distance_swm
#from health_access.weights import create_socio_swm
#from health_access.viz import plot_swm_weighted

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

def main():
    print("Hello from Marie and Kana!")

# Load configuration
#    with open("config/settings.yaml", "r") as f:
#        config = yaml.safe_load(f)

    # Part 1: Data Preprocessing 
    # Function from src.health_access_preprocessing
#    df = pd.read_csv(config['paths']['census_raw'])

    # Part 2: Clustering
#    print("Clustering districts...")
#    df_clustered = apply_clustering(df, config)

    # Part 3: Accessibility (You will implement this later)
    # results = calculate_accessibility(df_clustered, config)

    # Save the results
#    df_clustered.to_csv("data/processed/clustered_districts.csv", index=False)
#    print("Success! Results saved to data/processed/")

if __name__ == "__main__":
    main()