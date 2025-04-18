import requests
import pyproj
from io import BytesIO
from PIL import Image

class ImageExtractor:
    def __init__(self):
        self.wms_url = "https://siat.regione.umbria.it/arcgis/services/public/ORTOFOTO_2020_WGS84_UTM33N/MapServer/WMSServer"
        self.layer = "0"
        self.crs = "EPSG:4326"
        self.image_format = "image/png"
        self.project_to_utm = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32633", always_xy=True).transform
        self.project_to_wgs84 = pyproj.Transformer.from_crs("EPSG:32633", "EPSG:4326", always_xy=True).transform

    def get_image(self, lat, lon, bbox_size_m=100, resolution_m_per_pixel=0.2, save_path="satellite_image.png"):
        delta = bbox_size_m / 2

        # Convert lat/lon to UTM
        utm_x, utm_y = self.project_to_utm(lon, lat)

        # Define BBOX in UTM coordinates and convert back to lat/lon
        minx, miny = utm_x - delta, utm_y - delta
        maxx, maxy = utm_x + delta, utm_y + delta
        min_lon, min_lat = self.project_to_wgs84(minx, miny)
        max_lon, max_lat = self.project_to_wgs84(maxx, maxy)

        # Calculate image size
        width_pixels = int(bbox_size_m / resolution_m_per_pixel)
        height_pixels = int(bbox_size_m / resolution_m_per_pixel)

        params = {
            "SERVICE": "WMS",
            "VERSION": "1.1.1",
            "REQUEST": "GetMap",
            "LAYERS": self.layer,
            "STYLES": "",
            "FORMAT": self.image_format,
            "SRS": self.crs,
            "BBOX": f"{min_lon},{min_lat},{max_lon},{max_lat}",
            "WIDTH": str(width_pixels),
            "HEIGHT": str(height_pixels),
        }

        response = requests.get(self.wms_url, params=params)

        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            try:
                img = Image.open(BytesIO(response.content))
                return img
            except Exception as e:
                print(f"Error processing image: {e}")
                return None
        else:
            print(f"Failed to fetch image: {response.status_code}")
            print(response.text)
            return None

