from sqlalchemy import Column, Integer, String, Float
from database import Base

"""
Subway Info:
Index(['trip_id', 'stop_id', 'route_id', 'service_id', 'direction_id',
       'arrival_time', 'departure_time', 'stop_sequence', 'stop_headsign',
       'pickup_type', 'drop_off_type', 'shape_dist_traveled', 'timepoint',
       'trip_short_name', 'stop_code', 'stop_name'],
      dtype='object')
"""

class SubwayStopTime(Base):
    __tablename__ = "SUBWAY_STOP_TIMES"  # Must match your .to_sql name

    trip_id = Column(Integer, primary_key=True)
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
    
    service_id = Column(Integer, primary_key=True)
    monday = Column(Integer)
    tuesday = Column(Integer)
    wednesday = Column(Integer)
    thursday = Column(Integer)
    friday = Column(Integer)
    saturday = Column(Integer)
    sunday = Column(Integer)
    start_date = Column(Integer)
    end_date = Column(Integer)