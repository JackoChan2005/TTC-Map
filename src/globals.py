from pathlib import Path

home_dir = Path(__file__).parent.parent
data_dir = home_dir / "data"
db_dir = home_dir / "db"

# db connection
conn = db_dir / "SubwaySystem.db"