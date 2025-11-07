import json
from geopy.distance import geodesic
from shapely.geometry import Polygon
from buildings_manager import BuildingsManager

if __name__ == "__main__":
    # Bounding box (top-left & bottom-right)
    top_left_lat, top_left_lon = 45.1891197, 7.6604515
    bottom_right_lat, bottom_right_lon = 45.1282045, 7.7467373
    top_left = (top_left_lat, top_left_lon)

    # Build rectangular polygon from top-left and bottom-right
    aoi_points = [
        (top_left_lon, top_left_lat),
        (bottom_right_lon, top_left_lat),
        (bottom_right_lon, bottom_right_lat),
        (top_left_lon, bottom_right_lat),
        (top_left_lon, top_left_lat)
    ]
    aoi_polygon = Polygon(aoi_points)

    # Ground dimensions
    avg_lat = (top_left_lat + bottom_right_lat) / 2
    height_km = geodesic((top_left_lat, top_left_lon), (bottom_right_lat, top_left_lon)).km
    width_km = geodesic((avg_lat, top_left_lon), (avg_lat, bottom_right_lon)).km
    print(f"height_km = {height_km:.3f}, width_km = {width_km:.3f}")

    # Grid size
    rows = 10
    cols = 10
    cell_h = height_km / rows
    cell_w = width_km / cols

    # BuildingsManager
    print("\n## Buildings Manager")
    FM = BuildingsManager(polygon=aoi_polygon)

    # --- Aggregates ---
    total_buildings = 0
    total_height_weighted = 0.0
    total_buildings_for_height = 0
    total_building_area_km2 = 0.0
    total_cell_area_km2 = 0.0

    # Collect simple JSON (one object per cell)
    cells_json = []

    # Emit per-cell stats
    for i in range(rows):
        north_edge = geodesic(kilometers=i * cell_h).destination(top_left, 180)
        south_edge = geodesic(kilometers=(i + 1) * cell_h).destination(top_left, 180)

        for j in range(cols):
            nw = geodesic(kilometers=j * cell_w).destination((north_edge.latitude, north_edge.longitude), 90)
            ne = geodesic(kilometers=(j + 1) * cell_w).destination((north_edge.latitude, north_edge.longitude), 90)
            sw = geodesic(kilometers=j * cell_w).destination((south_edge.latitude, south_edge.longitude), 90)
            se = geodesic(kilometers=(j + 1) * cell_w).destination((south_edge.latitude, south_edge.longitude), 90)

            cell_polygon = Polygon([
                (nw.longitude, nw.latitude),
                (ne.longitude, ne.latitude),
                (se.longitude, se.latitude),
                (sw.longitude, sw.latitude),
                (nw.longitude, nw.latitude),
            ])

            num_buildings = FM.get_number_of_buildings(cell_polygon)
            avg_height = FM.get_average_height_of_buildings(cell_polygon)
            area_b_km2, area_cell_km2, coverage = FM.get_building_coverage_ratio(cell_polygon)

            print(
                f"cell({i},{j}): buildings={num_buildings}, "
                f"avg_height={avg_height}, "
                f"area_buildings_km2={area_b_km2:.6f}, "
                f"area_cell_km2={area_cell_km2:.6f}, "
                f"coverage={coverage:.4f}"
            )

            # Format polygon coordinates as [lat, lon]
            def latlon(pt):
                return [round(pt.latitude, 6), round(pt.longitude, 6)]

            cells_json.append({
                "row": i,
                "col": j,
                "width_km": round(cell_w, 4),
                "height_km": round(cell_h, 4),
                "num_buildings": int(num_buildings),
                "avg_height_buildings_m": (None if avg_height is None else round(float(avg_height), 2)),
                "area_buildings_km2": float(round(area_b_km2, 6)),
                "area_cell_km2": float(round(area_cell_km2, 6)),
                "coverage": float(round(coverage, 4)),
                "polygon_coordinates": [latlon(nw), latlon(ne), latlon(se), latlon(sw)]
            })

            total_buildings += num_buildings
            if avg_height is not None and num_buildings > 0:
                total_height_weighted += avg_height * num_buildings
                total_buildings_for_height += num_buildings

            total_building_area_km2 += area_b_km2
            total_cell_area_km2 += area_cell_km2

    # Write the JSON file (single array)
    with open("grid_cells.json", "w", encoding="utf-8") as f:
        json.dump(cells_json, f, ensure_ascii=False, indent=2)

    # --- Global stats ---
    global_avg_buildings_per_cell = total_buildings / (rows * cols)
    global_avg_height = (
        total_height_weighted / total_buildings_for_height if total_buildings_for_height > 0 else None
    )
    global_coverage = (total_building_area_km2 / total_cell_area_km2) if total_cell_area_km2 > 0 else 0.0

    print("\n## Global Summary")
    print(f"Total buildings: {total_buildings}")
    print(f"Average buildings per cell: {global_avg_buildings_per_cell:.2f}")
    if global_avg_height is not None:
        print(f"Average building height (global): {global_avg_height:.2f} m")
    else:
        print("Average building height (global): None")
    print(f"Total building area: {total_building_area_km2:.6f} km^2")
    print(f"Total cell area: {total_cell_area_km2:.6f} km^2")
    print(f"Global coverage (buildings / area): {global_coverage:.4f}")

    FM.plot_buildings_grid("map_buildings.html", rows, cols)
