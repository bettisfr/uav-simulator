from connectivity_manager import ConnectivityManager
from elevation_extractor import ElevationExtractor
from image_extractor import ImageExtractor

if __name__ == "__main__":
    EE = ElevationExtractor()

    lat, lon = 43.13934990668016, 11.930978649132863
    img_path = "satellite_image.png"
    map_path = "map.html"

    wcs_elev = EE.get_elevation(lat, lon)
    file_elev = EE.get_elevation_from_files(lat, lon, )
    print(f"WCS Elevation:   {wcs_elev:.2f} m" if wcs_elev is not None else "WCS Elevation:   N/A")
    print(f"File Elevation:  {file_elev:.2f} m" if file_elev is not None else "File Elevation:  N/A")



    # IE = ImageExtractor()
    #
    # image = IE.get_image(lat, lon, bbox_size_m=100, resolution_m_per_pixel=0.2)
    # if image:
    #     # image.show()
    #     image.save(img_path)
    #     print(f"Image saved to {img_path}")
    # else:
    #     print("No image returned.")
    #
    #
    # CM = ConnectivityManager()
    # map = CM.generate_map(map_path)
