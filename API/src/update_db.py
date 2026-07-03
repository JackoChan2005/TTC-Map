from load import loader
from transform import transformer

# Full static-GTFS rebuild (load + transform). The Node server decides when
# to run this: it checks the CKAN feed's metadata_modified and only spawns
# this script when the feed actually changed (or the db is missing).
# Realtime data lives separately in node-api/data/realtime.db.

class update_db:
    def __init__(self) -> None:
        self.load = loader()
        self.transform = transformer()

    def update_tables(self) -> None:
        self.load.load_data()
        self.transform.transform()


if __name__ == "__main__":
    u = update_db()
    u.update_tables()