from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from globals import gtfs_time_to_seconds
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import models

TORONTO_TZ = ZoneInfo("America/Toronto")

app = FastAPI()

def toronto_service_weekday_for_sec(sec: int) -> str:
    now = datetime.now(TORONTO_TZ)
    service_date = now.date()
    if sec >= 24 * 3600:
        service_date = (now - timedelta(days=1)).date()
    return datetime.combine(service_date, datetime.min.time(), tzinfo=TORONTO_TZ).strftime("%A").lower()

# test case: 07:29:47
# returns the next 2 mins of departing trains
@app.get("/departing/{time_str}")
def get_departing_trains(time_str: str, db: Session = Depends(get_db)):
    sec = gtfs_time_to_seconds(time_str)
    day = toronto_service_weekday_for_sec(sec)

    day_col = getattr(models.ServiceDay, day)  # safe if your columns match weekday strings

    results = (
    db.query(models.SubwayStopTime)
        .join(models.ServiceDay, models.ServiceDay.service_id == models.SubwayStopTime.service_id)
        .filter(day_col == 1)
        .filter(models.SubwayStopTime.departing_time_sec.between(sec, sec + 120))
        .order_by(models.SubwayStopTime.departure_time)
        .all()
    )

    if not results:
        raise HTTPException(status_code=404, detail="No trains at this time")

    return results

@app.get("/number_of_stops")
def get_station_number(db: Session = Depends(get_db)):
    results = (
        db.query(models.SubwayStopTime.stop_id)
        .distinct()
        .all()
    )
    return len(results)

@app.get("/servicing/{service_id}")
def get_service(service_id: int, db:Session = Depends(get_db)):
    results = db.query(models.ServiceDay).filter(
        models.ServiceDay.service_id == service_id   
    ).all()

    if not results:
        raise HTTPException(status_code=404, detail="No data for this id")
    return results

@app.get("/service")
def get_service_info(db:Session = Depends(get_db)):
    results = db.query(models.ServiceDay).all()

    if not results:
        raise HTTPException(status_code=404, detail="No data for this id")
    return results

@app.get("/trip")
def get_trip_id(trip_id: int, db: Session = Depends(get_db)):
    results = db.query(models.SubwayStopTime).filter(
        models.SubwayStopTime.trip_id == trip_id
    ).all()
    return results

@app.get("/number_of_trips")
def get_trip_id_number(db: Session = Depends(get_db)):
    results = (
        db.query(models.SubwayStopTime.trip_id)
        .distinct()
        .all()
    )
    return len(results)

@app.get("/hello_world")
async def root():
    return {"message": "Hello World"}