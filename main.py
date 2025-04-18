from connectivity_manager import ConnectivityManager
from elevation_extractor import ElevationExtractor
from image_extractor import ImageExtractor

if __name__ == "__main__":
    EE = ElevationExtractor()

    lat, lon = 43.062655, 12.547571
    img_path = "satellite_image.png"
    map_path = "map.html"

    elevation = EE.get_elevation(lat, lon)

    if elevation is not None:
        print(f"Elevation at ({lat}, {lon}): {elevation:.2f} meters")
    else:
        print("Failed to extract elevation.")


    IE = ImageExtractor()

    image = IE.get_image(lat, lon, bbox_size_m=100, resolution_m_per_pixel=0.2)
    if image:
        # image.show()
        image.save(img_path)
        print(f"Image saved to {img_path}")
    else:
        print("No image returned.")


    CM = ConnectivityManager()
    map = CM.generate_map(map_path)
