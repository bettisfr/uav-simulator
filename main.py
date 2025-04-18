from connectivity_manager import ConnectivityManager
from elevation_manager import ElevationManager
from image_manager import ImageManager

if __name__ == "__main__":
    EM = ElevationManager()

    lat, lon = 43.02713549563807, 12.587749251951715
    img_path = "satellite_image.png"
    map_path = "map.html"

    file_elev = EM.get_elevation_tiff(lat, lon)
    print(f"Elevation: {file_elev:.2f} m" if file_elev is not None else "Elevation:  N/A")

    IM = ImageManager()

    image = IM.get_image(lat, lon, bbox_size_m=100, resolution_m_per_pixel=0.2)
    if image:
        # image.show()
        image.save(img_path)
        print(f"Image saved to {img_path}")
    else:
        print("No image returned.")


    CM = ConnectivityManager()
    map = CM.generate_map(map_path)
