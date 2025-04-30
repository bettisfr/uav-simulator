import pandas as pd
import geopandas as gpd
from shapely import geometry, Polygon
import mercantile
import os
import tempfile
import folium


class BuildingsManager:
    def __init__(self, tiles_dir="buildings"):
        self.aoi_points = [
            (11.8367914, 43.6265258),
            (12.864006, 43.6413863),
            (13.0150791, 42.5546002),
            (11.7873966, 42.5424641),
            (11.8367914, 43.6265258)   # Close the polygon
        ]
        self.aoi_polygon = Polygon(self.aoi_points)
        self.aoi_geom = {
            "type": "Polygon",
            "coordinates": [self.aoi_polygon.exterior.coords[:]]
        }
        self.aoi_shape = geometry.shape(self.aoi_geom)
        self.minx, self.miny, self.maxx, self.maxy = self.aoi_shape.bounds
        self.tiles_dir = tiles_dir
        os.makedirs(self.tiles_dir, exist_ok=True)
        self.quad_keys = self.get_tile_aoi_intersection()
        self.ms_csv = pd.read_csv(
            "https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv",
            dtype=str
        )
        self.downloaded_tiles = self.get_tile_buildings()
        self.geo_buildings = self.merge_downloaded_tiles()

    def get_tile_aoi_intersection(self):
        quad_keys = set()
        for tile in list(mercantile.tiles(self.minx, self.miny, self.maxx, self.maxy, zooms=9)):
            quad_keys.add(mercantile.quadkey(tile))
        return list(quad_keys)

    def get_tile_buildings(self):
        downloaded_tiles = []
        with tempfile.TemporaryDirectory() as tmpdir:
            for quad_key in self.quad_keys:
                out_path = os.path.join(self.tiles_dir, f"{quad_key}.geojson")
                if os.path.exists(out_path):
                    downloaded_tiles.append(out_path)
                    continue

                rows = self.ms_csv[self.ms_csv["QuadKey"] == quad_key]
                if rows.empty:
                    continue

                gdfs = []
                for _, row in rows.iterrows():
                    url = row["Url"]
                    df = pd.read_json(url, lines=True)
                    df["geometry"] = df["geometry"].apply(geometry.shape)
                    gdf = gpd.GeoDataFrame(df, crs=4326)
                    gdf = gdf[gdf.geometry.intersects(self.aoi_shape)]
                    gdfs.append(gdf)

                if gdfs:
                    full_gdf = pd.concat(gdfs, ignore_index=True)
                    full_gdf.to_file(out_path, driver="GeoJSON")
                    downloaded_tiles.append(out_path)

        return downloaded_tiles

    def merge_downloaded_tiles(self):
        combined_gdf = gpd.GeoDataFrame()
        idx = 0
        for tile_path in self.downloaded_tiles:
            gdf = gpd.read_file(tile_path)
            gdf = gdf[gdf.geometry.intersects(self.aoi_shape)]
            gdf['id'] = range(idx, idx + len(gdf))
            idx += len(gdf)
            combined_gdf = pd.concat([combined_gdf, gdf], ignore_index=True)

        combined_gdf = combined_gdf.to_crs('EPSG:4326')
        return combined_gdf

    def get_height_building(self, latitude, longitude):
        point = geometry.Point(longitude, latitude)

        if self.geo_buildings.empty:
            print("No buildings to plot.")
            return -1

        _ = self.geo_buildings.sindex  # force creation of spatial index

        possible_matches_index = list(self.geo_buildings.sindex.intersection(point.bounds))
        possible_matches = self.geo_buildings.iloc[possible_matches_index]

        for _, row in possible_matches.iterrows():
            if row['geometry'].covers(point):
                row_id = row['id']
                row_polygon = row['geometry']
                row_altitude = float(row['properties'].split(",")[0].split(":")[1])
                return row_id, row_polygon, row_altitude

        return -1

    def plot_buildings(self, latitude, longitude, side_m, building_map_path):
        if self.geo_buildings.empty:
            print("No buildings to plot.")
            return

        # Define bounding box around center point
        half_deg = side_m / 111320 / 2  # Roughly convert meters to degrees
        min_lat = latitude - half_deg
        max_lat = latitude + half_deg
        min_lon = longitude - half_deg
        max_lon = longitude + half_deg

        bbox = geometry.box(min_lon, min_lat, max_lon, max_lat)
        # print(f"Total buildings loaded: {len(self.geo_buildings)}")
        filtered = self.geo_buildings[self.geo_buildings.geometry.intersects(bbox)]
        # print(f"Filtered buildings in view: {len(filtered)}")

        # Create folium map
        m = folium.Map(location=[latitude, longitude], zoom_start=17)

        if not filtered.empty:
            geojson = folium.GeoJson(filtered.to_json(), name="Buildings")
            geojson.add_to(m)

        folium.Marker(
            [latitude + half_deg, longitude - half_deg],
            tooltip=f"Area: {side_m} m"
        ).add_to(m)

        folium.Marker([latitude, longitude], tooltip="Center Point").add_to(m)

        m.save(building_map_path)
        print(f"Map saved to {building_map_path}")
