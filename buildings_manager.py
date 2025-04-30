import pandas as pd
import geopandas as gpd
from shapely import geometry
import mercantile
from tqdm import tqdm
import os
import tempfile


class BuildingsManager:
    def __init__(self, aoi):
        self.aoi_geom = aoi
        self.aoi_shape = geometry.shape(self.aoi_geom)
        self.minx, self.miny, self.maxx, self.maxy = self.aoi_shape.bounds
        self.dest = os.path.join("buildings", "buildings.geojson")
        self.quad_keys = self.get_tile_aoi_intersection()
        self.ms_csv = pd.read_csv("https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv", dtype=str)
        self.geo_buildings = self.get_tile_buildings()

    def get_tile_aoi_intersection(self):
        quad_keys = set()
        for tile in list(mercantile.tiles(self.minx, self.miny, self.maxx, self.maxy, zooms=9)):
            quad_keys.add(mercantile.quadkey(tile))
        quad_keys = list(quad_keys)
        print(f"The input area spans {len(quad_keys)} tiles: {quad_keys}")
        return quad_keys

    def get_tile_buildings(self):
        if os.path.exists(self.dest):
            print(f"GeoJson already exists in {self.dest}")
            return gpd.read_file(self.dest)
        idx = 0
        combined_gdf = gpd.GeoDataFrame()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Download the GeoJSON files for each tile that intersects the input geometry
            tmp_fns = []
            for quad_key in tqdm(self.quad_keys):
                rows = self.ms_csv[self.ms_csv["QuadKey"] == quad_key]
                if rows.shape[0] == 1:
                    url = rows.iloc[0]["Url"]

                    df2 = pd.read_json(url, lines=True)
                    df2["geometry"] = df2["geometry"].apply(geometry.shape)

                    gdf = gpd.GeoDataFrame(df2, crs=4326)
                    fn = os.path.join(tmpdir, f"{quad_key}.geojson")
                    tmp_fns.append(fn)
                    if not os.path.exists(fn):
                        gdf.to_file(fn, driver="GeoJSON")
                elif rows.shape[0] > 1:
                    raise ValueError(f"Multiple rows found for QuadKey: {quad_key}")
                else:
                    raise ValueError(f"QuadKey not found in dataset: {quad_key}")

            # Merge the GeoJSON files into a single file
            for fn in tmp_fns:
                gdf = gpd.read_file(fn)  # Read each file into a GeoDataFrame
                gdf = gdf[gdf.geometry.within(self.aoi_shape)]  # Filter geometries within the AOI
                gdf['id'] = range(idx, idx + len(gdf))  # Update 'id' based on idx
                idx += len(gdf)
                combined_gdf = pd.concat([combined_gdf, gdf], ignore_index=True)

            combined_gdf = combined_gdf.to_crs('EPSG:4326')
            combined_gdf.to_file(self.dest, driver='GeoJSON')
            print(f"GeoJson generated in {self.dest}")
            return combined_gdf

    def find_intersection_id(self, latitude, longitude):
        # Ensure GeoDataFrame has a spatial index (install rtree package)
        if not self.geo_buildings.sindex:
            self.geo_buildings.sindex()

        point = geometry.Point([latitude, longitude])

        possible_matches_index = list(self.geo_buildings.sindex.intersection(point.bounds))
        possible_matches = self.geo_buildings.iloc[possible_matches_index]

        for _, row in possible_matches.iterrows():
            if row['geometry'].covers(point):
                row_id = row['id']
                row_polygon = row['geometry']
                row_altitude = float(row['properties'].split(",")[0].split(":")[1])
                print(f"you are at {point}, there is a fabricate with id {row_id} and bounds {row_polygon} with altitude {row_altitude}")
                return (row_id, row_polygon, row_altitude)
        return -1