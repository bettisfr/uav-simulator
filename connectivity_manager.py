import glob
import csv
import folium
import os
from scipy.spatial import ConvexHull
import numpy as np

band_frequencies_numeric = {
    1: 2100,      # MHz
    3: 1800,      # MHz
    7: 2600,      # MHz
    8: 900,       # MHz
    20: 800,      # MHz
    28: 700,      # MHz
    32: 1500,     # MHz
    38: 2600,     # MHz
    78: 3700,     # MHz
    257: 28000,   # GHz converted to MHz (28 * 1000)
    258: 26000    # GHz converted to MHz (26 * 1000)
}

class ConnectivityManager:
    def __init__(self, dataset_dirs=None, tower_files=None):
        self.dataset_dirs = dataset_dirs or [
            'connectivity/dataset',
            'connectivity/dataset-old/bike',
            'connectivity/dataset-old/car',
            'connectivity/dataset-old/train',
            'connectivity/dataset-old/walk'
        ]
        self.tower_files = tower_files or [
            'connectivity/towers/tim_lteitaly.clf',
            'connectivity/towers/vodafone_lteitaly.clf'
        ]
        self.observations = []
        self.observed_cell_ids = set()
        self.towers = []

    def _parse_datasets(self, map_obj):
        for folder in self.dataset_dirs:
            for file_path in glob.glob(f'{folder}/*.csv'):
                file_name = os.path.basename(file_path)

                if 'ocid' in file_name and 'dataset' in folder:
                    continue

                formatted_date = file_name.split('.')[0]
                trail_coordinates = []

                with open(file_path, 'r') as file:
                    reader = csv.reader(file) if 'dataset-old' in folder else csv.DictReader(file)

                    for row in reader:
                        try:
                            if 'dataset-old' in folder:
                                lat = float(row[0])
                                lon = float(row[1])
                                alt = int(row[2])
                                cell_id = int(row[6])
                                signal = int(row[7])
                            else:
                                lat = float(row["lat"])
                                lon = float(row["lon"])
                                alt = int(float(row["altitude"]))
                                cell_id = int(row["cell_id"])
                                signal = int(row["rsrp"]) if row["net_type"] == "LTE" else int(row["rssi"])

                            self.observations.append({
                                "lat": lat,
                                "lon": lon,
                                "alt": alt,
                                "cell_id": cell_id,
                                "signal": signal
                            })

                            self.observed_cell_ids.add(cell_id)
                            trail_coordinates.append((lat, lon))

                        except (ValueError, IndexError, KeyError):
                            continue

                if trail_coordinates:
                    folium.PolyLine(trail_coordinates, color='blue', tooltip=formatted_date).add_to(map_obj)

    def _parse_towers(self, map_obj):
        for tower_file in self.tower_files:
            with open(tower_file, 'r') as file:
                for line in file:
                    parts = line.strip().split(';')
                    if len(parts) < 6:
                        continue

                    try:
                        cell_id = int(parts[1])
                        lat = float(parts[4])
                        lon = float(parts[5])
                        raw_type = parts[7]
                        band_str = raw_type.split(' ')[0]
                        if band_str[0] != "B":
                            band_str = "B1"
                        band = band_frequencies_numeric[int(band_str[1:])]
                        five_g = '5G' in raw_type
                    except ValueError:
                        continue

                    if cell_id in self.observed_cell_ids:
                        matching_obs = [obs for obs in self.observations if obs["cell_id"] == cell_id]
                        coverage = []

                        if len(matching_obs) >= 3:
                            points = [(obs["lat"], obs["lon"]) for obs in matching_obs]
                            points.append((lat, lon))  # include the tower location

                            np_points = np.array(points)
                            try:
                                hull = ConvexHull(np_points)
                                coverage = [tuple(np_points[i]) for i in hull.vertices]

                                # # Draw convex hull on map
                                # folium.Polygon(
                                #     locations=coverage,
                                #     color='black',
                                #     weight=1,
                                #     fill=True,
                                #     fill_opacity=0.1
                                # ).add_to(map_obj)
                            except Exception as e:
                                print(f"[WARN] Failed to compute convex hull for cell_id {cell_id}: {e}")

                        tower = {
                            "lat": lat,
                            "lon": lon,
                            "cell_id": cell_id,
                            "band": band,
                            "five_g": five_g,
                            "coverage": coverage
                        }
                        self.towers.append(tower)

                        folium.CircleMarker(
                            location=(lat, lon),
                            radius=4,
                            color='red',
                            fill=True,
                            fill_opacity=0.8,
                            popup=f"Cell ID: {cell_id} {band_str} {'5G' if five_g else ''}"
                        ).add_to(map_obj)

    def generate_map(self, save_path):
        m = folium.Map(location=(43.041169, 12.560277), zoom_start=12)

        self._parse_datasets(m)
        self._parse_towers(m)

        # random print
        azz = 875
        print(f"Sample observation: {self.observations[azz]}")
        print(f"Sample tower: {self.towers[azz]}")

        # Draw convex hull on map
        folium.Polygon(
            locations=self.towers[azz]["coverage"],
            color='black',
            weight=1,
            fill=True,
            fill_opacity=0.1
        ).add_to(m)

        m.save(save_path)
        print(f"Map saved to {save_path}")
        print(f"Total observations: {len(self.observations)}")
        print(f"Total towers: {len(self.towers)}")
