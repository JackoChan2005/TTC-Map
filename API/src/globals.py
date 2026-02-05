from pathlib import Path

home_dir = Path(__file__).parent.parent
data_dir = home_dir / "data"
db_dir = home_dir / "db"

# db connection
conn = db_dir / "SubwaySystem.db"

def gtfs_time_to_seconds(t: str) -> int:
    h, m, s = map(int, t.split(":"))
    return h * 3600 + m * 60 + s