from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models

app = FastAPI()

@app.get("/arrivals/{stop_id}")
def get_upcoming_trains(stop_id: str, db: Session = Depends(get_db)):
    # Query the table created by your transformer
    results = db.query(models.SubwayStopTime).filter(
        models.SubwayStopTime.stop_id == stop_id
    ).order_by(models.SubwayStopTime.arrival_time).all()
    
    if not results:
        raise HTTPException(status_code=404, detail="No data for this stop")
    return results

@app.get("/")
async def root():
    return {"message": "Hello World"}