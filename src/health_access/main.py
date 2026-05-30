import logging
import sys

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


if __name__ == "__main__":
    main()