from sqlalchemy import Column, Integer, String, Enum, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()
#Tables in the SQL

# Enum for worker and job levels
class LevelEnum(str, enum.Enum):
    junior = "junior"
    medior = "medior"
    senior = "senior"

class Worker(Base):
    __tablename__ = "workers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    surname = Column(String, nullable=False)
    department = Column(String, nullable=False)
    level = Column(Enum(LevelEnum, name="levelenum"), nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String)

    jobs = relationship("Job", back_populates="assigned_worker")
    statistics = relationship("Statistics", uselist=False, back_populates="worker")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    task = Column(String, nullable=False)
    payload = Column(Text, nullable=False)
    department = Column(String, nullable=False)
    required_level = Column(Enum(LevelEnum, name="levelenum"), nullable=False)
    status = Column(String, default="queued")
    assigned_to = Column(Integer, ForeignKey("workers.id"), nullable=True)
    expected_completion = Column(DateTime, nullable=True)

    assigned_worker = relationship("Worker", back_populates="jobs")


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    surname = Column(String, nullable=False)
    email = Column(String, unique=True)
    password_hash = Column(String)


class Statistics(Base):
    __tablename__ = "statistics"

    id = Column(Integer, primary_key=True, index=True)
    workerId = Column(Integer, ForeignKey("workers.id"), index=True, unique=True)
    numberCompletedJobs = Column(Integer, nullable=False)

    worker = relationship("Worker", back_populates="statistics")
