
from pathlib import Path
import sys

# Tìm thư mục gốc Logistics-eta-system
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Cho phép Backend sử dụng module osm/
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Sử dụng lại code OSM của Người 1
from osm.routing.route_service import get_route_from_osrm


def get_candidate_routes(origin, destination):
    """
    origin, destination có dạng:
    {"lat": 10.77, "lng": 106.69}
    """

    return get_route_from_osrm(
        origin["lng"],
        origin["lat"],
        destination["lng"],
        destination["lat"]
    )
