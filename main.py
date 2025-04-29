from connectivity_manager import ConnectivityManager
from elevation_manager import ElevationManager
from image_manager import ImageManager
from fabricate_manager import FabricateManager
if __name__ == "__main__":
    # the following variable is the area of interest: a polygon of points [lat, lon].
    # the current points are an approximation of Umbria's boundaries
    aoi = {
    "coordinates": [
        [
            [12.215515524800082, 43.50076630453859],
            [12.135955328704057, 43.38009577938479],
            [12.233195568376885, 43.305519444724496],
            [12.109435263339435, 43.22441032758451],
            [11.996282984447646, 43.13416235152718],
            [12.019267041097748, 43.02827365937026],
            [12.310987760115125, 42.981728136658916],
            [12.641604575001622, 43.03344320710761],
            [12.71939676673989, 43.19734994119651],
            [12.547900344044393, 43.35439015033279],
            [12.360491882129907, 43.489223162350044]
        ]
    ],
    "type": "Polygon",
    }
    FM = FabricateManager(aoi)


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
