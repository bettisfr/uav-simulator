import requests
import warnings
import tempfile
from owslib.wcs import WebCoverageService
import rasterio

class ElevationExtractor:
    def __init__(self):
        self.service_url = "https://tinitaly.pi.ingv.it/TINItaly_1_1/wcs"
        self.coverage_id = "TINItaly_1_1:tinitaly_dem"

        self._suppress_ssl_warnings()
        self._patch_requests_ssl_verification()
        self.wcs = WebCoverageService(self.service_url, version='1.0.0')

    def _suppress_ssl_warnings(self):
        warnings.filterwarnings("ignore", message="Unverified HTTPS request")

    def _patch_requests_ssl_verification(self):
        old_request = requests.request
        def unsafe_request(*args, **kwargs):
            kwargs['verify'] = False
            return old_request(*args, **kwargs)
        requests.request = unsafe_request

    def get_elevation(self, lat, lon, delta_lat=0.00009, delta_lon=0.00013):
        bbox = (lon - delta_lon, lat - delta_lat, lon + delta_lon, lat + delta_lat)

        try:
            response = self.wcs.getCoverage(
                identifier=self.coverage_id,
                bbox=bbox,
                format='GeoTIFF',
                crs='EPSG:4326',
                resx=delta_lon,
                resy=delta_lat
            )
        except Exception as e:
            print(f"Error fetching coverage: {e}")
            return None

        content = response.read()

        with tempfile.NamedTemporaryFile(suffix=".tif") as tmp:
            tmp.write(content)
            tmp.flush()
            try:
                with rasterio.open(tmp.name) as dataset:
                    elevation = list(dataset.sample([(lon, lat)]))[0][0]
                    return elevation
            except rasterio.errors.RasterioIOError:
                print("Not a valid GeoTIFF — check request parameters or server response.")
                return None
