from connectivity_manager import ConnectivityManager
from elevation_manager import ElevationManager
from image_manager import ImageManager
from buildings_manager import BuildingsManager

if __name__ == "__main__":
    # Parameters
    lat, lon = 43.065502633260664, 12.54686465354475
    img_path = "satellite_image.png"
    connectivity_map_path = "map_connectivity.html"
    building_map_path = "map_building.html"

    print("## Parameters")
    print(f"lat: {lat}, lon: {lon}")

    # BuildingsManager
    print("\n## Buildings Manager")
    FM = BuildingsManager()
    result = FM.get_height_building(lat, lon)
    print(f"Building height: {result[2]:.2f} m" if result != -1 else "Building height: N/A")
    FM.plot_buildings(lat, lon, 3000, building_map_path)

    # ElevationManager
    print("\n## Elevation Manager")
    EM = ElevationManager()

    file_elev = EM.get_elevation_tiff(lat, lon)
    print(f"Elevation: {file_elev:.2f} m" if file_elev is not None else "Elevation:  N/A")

    # ImageManager
    print("\n## Image Manager")
    IM = ImageManager()

    image = IM.get_image(lat, lon, bbox_size_m=100, resolution_m_per_pixel=0.2)
    if image:
        # image.show()
        image.save(img_path)
        print(f"Image saved to {img_path}")
    else:
        print("No image returned.")

    # ConnectivityManager
    print("\n## Connectivity Manager")
    CM = ConnectivityManager()
    map = CM.generate_map(connectivity_map_path)
