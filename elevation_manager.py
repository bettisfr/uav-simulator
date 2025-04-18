import requests
import warnings
import tempfile
from owslib.wcs import WebCoverageService
import rasterio
import os
import glob
from rasterio.warp import transform

class ElevationManager:
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

    def get_elevation_wcs(self, lat, lon, delta_lat=0.00009, delta_lon=0.00013):
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

    def get_elevation_from_file(self, lat, lon, file_path):
        try:
            with rasterio.open(file_path) as dataset:
                # Transform coordinates to the dataset CRS if needed
                if dataset.crs.to_string() != "EPSG:4326":
                    lon, lat = transform(
                        "EPSG:4326", dataset.crs, [lon], [lat]
                    )
                    lon, lat = lon[0], lat[0]

                value = list(dataset.sample([(lon, lat)]))[0][0]
                nodata = dataset.nodata

                if value == nodata or value < -1000:
                    print(f"Value at ({lat}, {lon}) is a no-data value: {value}")
                    return None
                return value
        except Exception as e:
            print(f"Error reading from file {file_path}: {e}")
            return None

    def get_elevation_tiff(self, lat, lon):
        tif_files = glob.glob(os.path.join("elevation/", "*.tif"))

        for file_path in tif_files:
            try:
                with rasterio.open(file_path) as dataset:
                    bounds = dataset.bounds

                    # Transform the coordinate to the dataset's CRS if needed
                    if dataset.crs.to_string() != "EPSG:4326":
                        lon_t, lat_t = transform("EPSG:4326", dataset.crs, [lon], [lat])
                        lon_t, lat_t = lon_t[0], lat_t[0]
                    else:
                        lon_t, lat_t = lon, lat

                    # Check if the point is within this raster's bounds
                    if bounds.left <= lon_t <= bounds.right and bounds.bottom <= lat_t <= bounds.top:
                        value = list(dataset.sample([(lon_t, lat_t)]))[0][0]
                        nodata = dataset.nodata

                        if value == nodata or value < -1000:
                            print(f"Found in {file_path}, but it's a no-data value: {value}")
                            continue  # Try the next file

                        # print(f"Value from {file_path}")
                        return value
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                continue

        print("No valid elevation found in available TIFF files.")
        return None

