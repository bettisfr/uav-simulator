import glob
import csv
import folium
import os
from scipy.spatial import ConvexHull
import numpy as np
import matplotlib.pyplot as plt

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

                # Skip OCID files in main dataset only
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
                        band = raw_type.split(' ')[0]
                        # check if raw_type contains '5G'
                        five_g = '5G' in raw_type
                    except ValueError:
                        continue

                    if cell_id in self.observed_cell_ids:
                        tower = {
                            "lat": lat,
                            "lon": lon,
                            "cell_id": cell_id,
                            "band": band,
                            "five_g": five_g
                        }
                        self.towers.append(tower)

                        folium.CircleMarker(
                            location=(lat, lon),
                            radius=4,
                            color='red',
                            fill=True,
                            fill_opacity=0.8,
                            popup=f"Cell ID: {cell_id} {band} {'5G' if five_g else ''}"
                        ).add_to(map_obj)

    def generate_map(self, save_path):
        m = folium.Map(location=(43.041169, 12.560277), zoom_start=12)

        self._parse_datasets(m)
        self._parse_towers(m)

        m.save(save_path)
        print(f"Map saved to {save_path}")
        print(f"Total observations: {len(self.observations)}")
        print(f"Total towers: {len(self.towers)}")
        if self.observations:
            print(f"Sample observation: {self.observations[0]}")
        if self.towers:
            print(f"Sample tower: {self.towers[0]}")
