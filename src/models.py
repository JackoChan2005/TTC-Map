from sqlalchemy import Column, Integer, String, Float
from database import Base

class SubwayStopTime(Base):
    __tablename__ = "SUBWAY_STOP_TIMES"  # Must match your .to_sql name

    trip_id = Column(String, primary_key=True)
    stop_sequence = Column(Integer, primary_key=True)
    
    route_id = Column(String)
    service_id = Column(String)
    stop_id = Column(String)
    stop_name = Column(String)
    arrival_time = Column(String)
    departure_time = Column(String)
    direction_id = Column(Integer)

class ServiceDay(Base):
    __tablename__ = "SERVICE_DAYS"
    
    service_id = Column(String, primary_key=True)
    monday = Column(Integer)
    tuesday = Column(Integer)
    wednesday = Column(Integer)
    thursday = Column(Integer)
    friday = Column(Integer)
    saturday = Column(Integer)
    sunday = Column(Integer)
    start_date = Column(Integer)
    end_date = Column(Integer)