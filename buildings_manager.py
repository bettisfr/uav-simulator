import os
import math
import tempfile
import pandas as pd
import geopandas as gpd
from folium import GeoJsonTooltip
from shapely.geometry import Polygon, Point, box, shape
import mercantile
import folium
import json
from geopy.distance import geodesic
from shapely.ops import unary_union


class BuildingsManager:
    """
    Downloads Microsoft Global Buildings tiles intersecting an AOI, merges them into a GeoDataFrame,
    and provides simple statistics/plotting utilities.

    Key changes:
    - AOI can be passed as a Polygon at construction time (lon, lat order).
    - plot_buildings(path) now only uses the AOI polygon (no lat/lon args).
    - All centroid/within operations are performed in a projected CRS (EPSG:32632) to avoid warnings.
    """

    def __init__(self, tiles_dir="buildings", polygon=None):
        # --- AOI polygon (lon, lat order) ---
        if polygon is not None:
            self.aoi_polygon = polygon
        else:
            # Fallback default polygon (lon, lat)
            self.aoi_polygon = Polygon([
                (11.8367914, 43.6265258),
                (12.864006,  43.6413863),
                (13.0150791, 42.5546002),
                (11.7873966, 42.5424641),
                (11.8367914, 43.6265258)   # close
            ])

        self.aoi_geom = {"type": "Polygon", "coordinates": [list(self.aoi_polygon.exterior.coords)]}
        self.aoi_shape = shape(self.aoi_geom)  # shapely geometry

        # Bounds (lon/lat)
        self.minx, self.miny, self.maxx, self.maxy = self.aoi_shape.bounds

        # CRS setup
        self.crs_geo = "EPSG:4326"    # WGS84 lon/lat
        self.crs_proj = "EPSG:32632"  # WGS84 / UTM zone 32N (good for Northern/Central Italy)
        # Projected AOI once
        self.aoi_polygon_proj = gpd.GeoSeries([self.aoi_polygon], crs=self.crs_geo).to_crs(self.crs_proj).iloc[0]

        # IO / tiles
        self.tiles_dir = tiles_dir
        os.makedirs(self.tiles_dir, exist_ok=True)

        # Covering tiles at zoom 9 (coarse; adjust if needed)
        self.quad_keys = self.get_tile_aoi_intersection()

        # Microsoft Buildings index
        self.ms_csv = pd.read_csv(
            "https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv",
            dtype=str
        )

        # Download + merge
        self.downloaded_tiles = self.get_tile_buildings()
        self.geo_buildings = self.merge_downloaded_tiles()  # sets self.geo_buildings and self.geo_buildings_proj

    # ----------------- tiles over AOI -----------------
    def get_tile_aoi_intersection(self, zoom=9):
        quad_keys = set()
        for tile in mercantile.tiles(self.minx, self.miny, self.maxx, self.maxy, zooms=zoom):
            quad_keys.add(mercantile.quadkey(tile))
        return list(quad_keys)

    # ----------------- download / filter tiles -----------------
    def get_tile_buildings(self):
        downloaded_tiles = []
        with tempfile.TemporaryDirectory() as _:
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

                    # Build geometries
                    df["geometry"] = df["geometry"].apply(shape)
                    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs=self.crs_geo)

                    # Quick spatial filter to AOI
                    gdf = gdf[gdf.geometry.intersects(self.aoi_shape)]
                    if not gdf.empty:
                        gdfs.append(gdf)

                if gdfs:
                    full_gdf = pd.concat(gdfs, ignore_index=True)
                    full_gdf.to_file(out_path, driver="GeoJSON")
                    downloaded_tiles.append(out_path)

        return downloaded_tiles

    # ----------------- merge to single GeoDataFrame -----------------
    def merge_downloaded_tiles(self):
        combined_gdf = gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=self.crs_geo)
        idx = 0
        for tile_path in self.downloaded_tiles:
            gdf = gpd.read_file(tile_path)
            # Ensure CRS
            if gdf.crs is None:
                gdf.set_crs(self.crs_geo, inplace=True)
            elif gdf.crs.to_string().lower() != self.crs_geo.lower():
                gdf = gdf.to_crs(self.crs_geo)

            # Clip to AOI bbox/intersection
            gdf = gdf[gdf.geometry.intersects(self.aoi_shape)]
            if gdf.empty:
                continue

            n = len(gdf)
            gdf = gdf.reset_index(drop=True)
            gdf["id"] = range(idx, idx + n)
            idx += n

            combined_gdf = pd.concat([combined_gdf, gdf], ignore_index=True)

        # Store both geographic and projected copies
        self.geo_buildings = combined_gdf
        self.geo_buildings_proj = self.geo_buildings.to_crs(self.crs_proj)
        return self.geo_buildings

    # ----------------- robust height parsing -----------------
    @staticmethod
    def _extract_height(row):
        # common locations
        if "height" in row and pd.notna(row["height"]):
            try:
                return float(row["height"])
            except Exception:
                pass
        props = row.get("properties", None)
        if isinstance(props, dict) and "height" in props:
            try:
                return float(props["height"])
            except Exception:
                pass
        if isinstance(props, str) and "height" in props:
            try:
                for tok in props.split(","):
                    if "height" in tok:
                        return float(tok.split(":")[1])
            except Exception:
                pass
        return None

    # ----------------- stats over a cell polygon -----------------
    def get_number_of_buildings(self, polygon):
        """Count buildings whose centroid (in projected CRS) lies within polygon."""
        if self.geo_buildings.empty:
            return 0

        # shortlist in geographic CRS
        candidates = self.geo_buildings[self.geo_buildings.geometry.intersects(polygon)]
        if candidates.empty:
            return 0

        # project both polygon and candidates for centroid/within
        poly_proj = gpd.GeoSeries([polygon], crs=self.crs_geo).to_crs(self.crs_proj).iloc[0]
        cand_proj = self.geo_buildings_proj.loc[candidates.index]
        inside_idx = cand_proj[cand_proj.geometry.centroid.within(poly_proj)].index

        return int(len(inside_idx))

    def get_average_height_of_buildings(self, polygon):
        """Average height of buildings whose centroid (in projected CRS) lies within polygon."""
        if self.geo_buildings.empty:
            return None

        candidates = self.geo_buildings[self.geo_buildings.geometry.intersects(polygon)]
        if candidates.empty:
            return None

        poly_proj = gpd.GeoSeries([polygon], crs=self.crs_geo).to_crs(self.crs_proj).iloc[0]
        cand_proj = self.geo_buildings_proj.loc[candidates.index]
        inside_idx = cand_proj[cand_proj.geometry.centroid.within(poly_proj)].index

        if len(inside_idx) == 0:
            return None

        heights = self.geo_buildings.loc[inside_idx].apply(self._extract_height, axis=1).dropna()
        return float(heights.mean()) if len(heights) else None

    # ----------------- single-point lookup (kept for compatibility) -----------------
    def get_height_building(self, latitude, longitude):
        """Return (id, polygon, height) of the building covering the given point, if any."""
        if self.geo_buildings.empty:
            print("No buildings to query.")
            return -1

        point = Point(longitude, latitude)

        # spatial index shortlist in geo CRS
        _ = self.geo_buildings.sindex
        idxs = list(self.geo_buildings.sindex.intersection(point.bounds))
        if not idxs:
            return -1
        possible = self.geo_buildings.iloc[idxs]

        for _, row in possible.iterrows():
            if row["geometry"].covers(point):
                row_id = row["id"]
                row_polygon = row["geometry"]
                height = self._extract_height(row)
                return row_id, row_polygon, (float(height) if height is not None else None)

        return -1

    def plot_buildings_grid(self, building_map_path, rows=10, cols=10):
        """
        Render AOI + buildings + a rows×cols grid.
        Each cell popup shows: buildings, avg height, building area, cell area, coverage.
        Cells are color-coded by coverage ratio.
        """
        if self.geo_buildings.empty:
            print("No buildings to plot.")
            return

        # --- map base (center on AOI centroid) ---
        ctr = self.aoi_polygon.centroid
        m = folium.Map(location=[ctr.y, ctr.x], zoom_start=15)

        # --- AOI boundary ---
        folium.GeoJson(
            self.aoi_geom,
            name="AOI",
            style_function=lambda _: {"fillOpacity": 0.05, "color": "black", "weight": 2},
            tooltip="AOI"
        ).add_to(m)

        # --- Buildings layer (intersecting AOI) ---
        buildings_in_aoi = self.geo_buildings[self.geo_buildings.geometry.intersects(self.aoi_shape)]
        if not buildings_in_aoi.empty:
            folium.GeoJson(buildings_in_aoi.to_json(), name="Buildings").add_to(m)

        # --- grid over AOI bounds (rectangular) ---
        minx, miny, maxx, maxy = self.minx, self.miny, self.maxx, self.maxy  # lon/lat
        top_left = (maxy, minx)  # (lat, lon)
        avg_lat = (maxy + miny) / 2

        # Ground dimensions (km)
        total_h_km = geodesic((maxy, minx), (miny, minx)).km  # N–S along west edge
        total_w_km = geodesic((avg_lat, minx), (avg_lat, maxx)).km  # E–W along mid-lat
        cell_h = total_h_km / rows
        cell_w = total_w_km / cols

        # simple color scale for coverage (0.0 -> green, 0.6+ -> red)
        def cov_color(c):
            c = max(0.0, min(0.6, float(c)))
            t = c / 0.6
            r = int(255 * t)
            g = int(255 * (1 - t))
            return f"#{r:02x}{g:02x}00"

        # Build GeoJSON features for cells with stats
        features = []
        for i in range(rows):
            north_edge = geodesic(kilometers=i * cell_h).destination(top_left, 180)  # south
            south_edge = geodesic(kilometers=(i + 1) * cell_h).destination(top_left, 180)

            for j in range(cols):
                nw = geodesic(kilometers=j * cell_w).destination((north_edge.latitude, north_edge.longitude), 90)
                ne = geodesic(kilometers=(j + 1) * cell_w).destination((north_edge.latitude, north_edge.longitude), 90)
                sw = geodesic(kilometers=j * cell_w).destination((south_edge.latitude, south_edge.longitude), 90)
                se = geodesic(kilometers=(j + 1) * cell_w).destination((south_edge.latitude, south_edge.longitude), 90)

                # Cell polygon (lon/lat)
                cell_poly = Polygon([
                    (nw.longitude, nw.latitude),
                    (ne.longitude, ne.latitude),
                    (se.longitude, se.latitude),
                    (sw.longitude, sw.latitude),
                    (nw.longitude, nw.latitude),
                ])

                # Clip to AOI (in case AOI isn’t exactly a rectangle)
                cell_poly = cell_poly.intersection(self.aoi_polygon)
                if cell_poly.is_empty:
                    continue

                # Stats
                num_build = self.get_number_of_buildings(cell_poly)
                avg_h = self.get_average_height_of_buildings(cell_poly)
                area_b_km2, area_cell_km2, coverage = self.get_building_coverage_ratio(cell_poly)

                props = {
                    "row": i, "col": j,
                    "buildings": int(num_build),
                    "avg_height": (None if avg_h is None else float(avg_h)),
                    "area_buildings_km2": float(area_b_km2),
                    "area_cell_km2": float(area_cell_km2),
                    "coverage": float(coverage),
                }

                # Handle MultiPolygons by exterior coords; if multiparts, convert to GeoJSON via __geo_interface__
                geom = cell_poly.__geo_interface__

                features.append({"type": "Feature", "properties": props, "geometry": geom})

        grid_fc = {"type": "FeatureCollection", "features": features}

        # Add grid layer with tooltip/popup + color by coverage
        folium.GeoJson(
            data=grid_fc,
            name="Grid cells",
            style_function=lambda feat: {
                "fillColor": cov_color(feat["properties"]["coverage"]),
                "color": "#333333",
                "weight": 1,
                "fillOpacity": 0.35,
            },
            tooltip=GeoJsonTooltip(fields=["row", "col", "buildings", "avg_height", "coverage"],
                                   aliases=["Row", "Col", "Buildings", "Avg height (m)", "Coverage"],
                                   localize=True),
            popup=folium.GeoJsonPopup(fields=["row", "col", "buildings", "avg_height",
                                              "area_buildings_km2", "area_cell_km2", "coverage"],
                                      aliases=["Row", "Col", "Buildings", "Avg height (m)",
                                               "Building area (km²)", "Cell area (km²)", "Coverage"],
                                      localize=True),
        ).add_to(m)

        folium.LayerControl().add_to(m)
        m.fit_bounds([[self.miny, self.minx], [self.maxy, self.maxx]])
        m.save(building_map_path)
        print(f"Map with grid saved to {building_map_path}")

    # ----------------- AOI plot -----------------
    def plot_buildings(self, building_map_path):
        """Save an interactive map of AOI and buildings to the given path."""
        if self.geo_buildings.empty:
            print("No buildings to plot.")
            return

        # Filter by AOI polygon (intersects)
        filtered = self.geo_buildings[self.geo_buildings.geometry.intersects(self.aoi_shape)]
        num_buildings = len(filtered)

        # Center by AOI centroid (projected if needed)
        ctr = self.aoi_polygon.centroid
        m = folium.Map(location=[ctr.y, ctr.x], zoom_start=15)

        # Draw AOI boundary
        folium.GeoJson(
            self.aoi_geom,
            name="AOI",
            style_function=lambda _: {"fillOpacity": 0.05, "color": "black", "weight": 2},
            tooltip="AOI Boundary"
        ).add_to(m)

        # Draw buildings inside AOI
        if not filtered.empty:
            folium.GeoJson(filtered.to_json(), name="Buildings").add_to(m)

        # Add a marker showing number of buildings
        folium.Marker(
            location=[ctr.y, ctr.x],
            tooltip=f"AOI center — Buildings: {num_buildings}",
            icon=folium.Icon(color="blue", icon="info-sign"),
        ).add_to(m)

        # Fit map to AOI bounds
        m.fit_bounds([[self.miny, self.minx], [self.maxy, self.maxx]])

        m.save(building_map_path)
        print(f"Map saved to {building_map_path} — contains {num_buildings} buildings")

    def get_building_coverage_ratio(self, polygon):
        """
        Return (area_buildings_km2, area_cell_km2, ratio) for the given cell polygon.
        Areas are computed in a projected CRS (EPSG:32632).
        """
        if self.geo_buildings.empty:
            return 0.0, 0.0, 0.0

        # shortlist in geographic CRS
        candidates = self.geo_buildings[self.geo_buildings.geometry.intersects(polygon)]
        if candidates.empty:
            # compute cell area anyway
            cell_proj = gpd.GeoSeries([polygon], crs=self.crs_geo).to_crs(self.crs_proj).iloc[0]
            area_cell_km2 = cell_proj.area / 1e6
            return 0.0, area_cell_km2, 0.0

        # project the cell and candidate buildings
        cell_proj = gpd.GeoSeries([polygon], crs=self.crs_geo).to_crs(self.crs_proj).iloc[0]
        cand_proj = self.geo_buildings_proj.loc[candidates.index]

        # clip buildings to the cell and union (avoid overlapping double-count)
        inter_parts = []
        for geom in cand_proj.geometry:
            if not geom.is_empty and geom.intersects(cell_proj):
                part = geom.intersection(cell_proj)
                if not part.is_empty:
                    inter_parts.append(part)

        if not inter_parts:
            area_cell_km2 = cell_proj.area / 1e6
            return 0.0, area_cell_km2, 0.0

        buildings_union = unary_union(inter_parts)
        area_buildings_km2 = buildings_union.area / 1e6
        area_cell_km2 = cell_proj.area / 1e6
        ratio = (area_buildings_km2 / area_cell_km2) if area_cell_km2 > 0 else 0.0
        return area_buildings_km2, area_cell_km2, ratio