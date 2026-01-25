from contextlib import contextmanager
from zipfile import ZipFile

import globals
import requests

class loader:
    def __init__(self) -> None:
        # For Opendata
        self.base_url = base_url = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
        self.url = base_url + "/api/3/action/package_show"
        self.params = { "id": "merged-gtfs-ttc-routes-and-schedules"}

        # Data directory
        self.data_dir = globals.home_dir / "data"

    def download_Data(self) -> None:
        package = requests.get(self.url, params = self.params).json()
        # To get resource data:
        for idx, resource in enumerate(package["result"]["resources"]):
            # To get metadata for non datastore_active resources:
            if not resource["datastore_active"]:
                download_url = resource["url"]

                filename = resource["name"] + ".zip"
                file_path = self.data_dir / filename

                print(f"Downloading: {filename}...")

                r = requests.get(download_url, stream=True)
                if r.status_code == 200:
                    with open(file_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                        print(f"Success! File saved as {filename}")
                else:
                    print("Download failed.")

    def extract_data(self) -> None:
        # Look in the current directory for any file ending in .zip
        data_dir = self.data_dir
        zip_files = list(data_dir.glob("*.zip"))

        if zip_files:
            zip_path = zip_files[0]
            with ZipFile(zip_path, 'r') as myzip:
                # Loop through every file inside the zip
                for file_info in myzip.infolist():
                    # Only extract if it's a .txt file
                    if file_info.filename.endswith('.txt'):
                        myzip.extract(file_info, data_dir)
                        print(f"Saved: {file_info.filename} to {data_dir}")
        else:
            print("No zip files found!")

    def load_data(self) -> None:
        return

if __name__ == "__main__":
    l = loader()
    l.download_Data()
    l.extract_data()
