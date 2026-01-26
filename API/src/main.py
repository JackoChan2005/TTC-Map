from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models

app = FastAPI()

@app.get("/departing/{time}")
def get_arriving_trains(time: str, db: Session = Depends(get_db)):
    results = db.query(models.SubwayStopTime).filter(
        models.SubwayStopTime.arrival_time == time   
    ).order_by(models.SubwayStopTime.arrival_time).all()

    if not results:
        raise HTTPException(status_code=404, detail="No data for this stop")
    return results

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


# test code
@app.get("/arrivals/{stop_id}")
def get_upcoming_trains(stop_id: str, db: Session = Depends(get_db)):
    # Query the table created by your transformer
    results = db.query(models.SubwayStopTime).filter(
        models.SubwayStopTime.stop_id == stop_id
    ).order_by(models.SubwayStopTime.arrival_time).all()
    
    if not results:
        raise HTTPException(status_code=404, detail="No data for this stop")
    return results


@app.get("/hello_world")
async def root():
    return {"message": "Hello World"}