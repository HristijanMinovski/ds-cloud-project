from fastapi import FastAPI, Form, HTTPException, Depends, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
from datetime import datetime
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os
from tasks import send_email_async

from authentication import get_current_worker, get_current_admin
from models_2 import Worker, Job, Admin, LevelEnum, Statistics
from database_1 import SessionLocal, init_db
from auth_utils_1 import hash_password, verify_password, create_access_token

load_dotenv()

# klasa i site endpoint 

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class WorkerRegisterRequest(BaseModel):
    name: str
    surname: str
    department: str
    level: LevelEnum
    email: str
    password: str

class WorkerLoginRequest(BaseModel):
    name: str
    surname: str

class JobClaimRequest(BaseModel):
    job_id: int
    expected_completion: datetime

class JobResponse(BaseModel):
    id: int
    task: str
    payload: str
    department: str
    required_level: LevelEnum
    status: str
    assigned_to: int | None
    expected_completion: datetime | None

    class Config:
        orm_mode = True

LEVEL_PRECEDENCE = {
    "junior": 1,
    "medior": 2,
    "senior": 3
}

class LoginForm:
    def __init__(
        self,
        email: str = Form(...),
        password: str = Form(...)
    ):
        self.email = email
        self.password = password

class LevelUpgradeRequest(BaseModel):
    worker_id: int
    new_level: LevelEnum

class AdminRegisterRequest(BaseModel):
    name: str
    surname: str
    email: str
    password: str

@app.post("/register_admin")
def register_admin(request: AdminRegisterRequest, db: Session = Depends(get_db)):
    try:
        existing_admin = db.query(Admin).filter(Admin.email == request.email).first()
        if existing_admin:
            raise HTTPException(status_code=400, detail="Email already registered")

        new_admin = Admin(
            name=request.name,
            surname=request.surname,
            email=request.email,
            password_hash=hash_password(request.password)
        )

        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)

        return {"message": "Admin registered successfully", "admin_id": new_admin.id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/register")
def register_worker(request: WorkerRegisterRequest, db: Session = Depends(get_db)):
    exists = db.query(Worker).filter(Worker.email == request.email).first()
    if exists:
        raise HTTPException(status_code=400, detail="Email already registered")

    worker = Worker(
        name=request.name,
        surname=request.surname,
        department=request.department,
        level=request.level,
        email=request.email,
        password_hash=hash_password(request.password)
    )
    db.add(worker)
    db.commit()
    db.refresh(worker)

    statistics = Statistics(workerId=worker.id, numberCompletedJobs=0)
    db.add(statistics)
    db.commit()
    return {"message": "Worker registered", "worker_id": worker.id}

@app.post("/login")
def login_worker(form_data: LoginForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(Worker).filter(Worker.email == form_data.email).first()
    role = "worker"

    if not user:
        user = db.query(Admin).filter(Admin.email == form_data.email).first()
        role = "admin"
        if not user or not verify_password(form_data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
    elif not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
   
    token = create_access_token(data={"sub": str(user.id), "role": role})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/available_jobs", response_model=List[JobResponse])
def get_available_jobs(current_worker: Worker = Depends(get_current_worker), db: Session = Depends(get_db), token: str = Header(...)):
    worker = current_worker
    worker_level_val = LEVEL_PRECEDENCE[worker.level.value]

    allowed_levels = [
        level for level, val in LEVEL_PRECEDENCE.items()
        if val <= worker_level_val
    ]

    jobs = db.query(Job).filter(
        Job.department == worker.department,
        Job.required_level.in_(allowed_levels),
        Job.status == "queued"
    ).all()

    if not jobs:
        return JSONResponse(content={"message": "No available jobs at the moment"}, status_code=200)
    
    return jobs

@app.post("/claim_job")
def claim_job(
    request: JobClaimRequest,
    current_worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
    token: str = Header(...)
):
    worker = current_worker
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    job = db.query(Job).filter(Job.id == request.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "queued":
        raise HTTPException(status_code=400, detail=f"Job status is '{job.status}', cannot claim")

    if job.department != worker.department:
        raise HTTPException(status_code=403, detail="Job department does not match worker department")

    if LEVEL_PRECEDENCE[job.required_level.value] > LEVEL_PRECEDENCE[worker.level.value]:
        raise HTTPException(status_code=403, detail="Worker level too low for this job")

    job.status = "in_progress"
    job.assigned_to = worker.id
    job.expected_completion = request.expected_completion
    db.commit()

    return {"message": "Job claimed", "job_id": job.id, "assigned_to": worker.id}

@app.post("/unclaim_job")
def unclaim_job(
    job_id: int,
    current_worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
    token: str = Header(...)
):
    worker = current_worker
    job = db.query(Job).get(job_id)
    
    if not job or not worker:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    if job.assigned_to != worker.id:
        raise HTTPException(status_code=403, detail="Not assigned to this worker")
    
    job.status = "queued"
    job.assigned_to = None
    job.expected_completion = None
    db.commit()
    return {"message": "Job unclaimed"}

@app.post("/complete_job")
def complete_job(
    job_id: int,
    current_worker: Worker = Depends(get_current_worker),
    db: Session = Depends(get_db),
    token: str = Header(...)
):
    worker = current_worker
    job = db.query(Job).get(job_id)
    if not job or not worker:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    if job.assigned_to != worker.id or job.status != "in_progress":
        raise HTTPException(status_code=400, detail="Invalid job state")
    
    job.status = "completed"
    statistics = db.query(Statistics).filter(Statistics.workerId == worker.id).first()
    if statistics:
        statistics.numberCompletedJobs += 1

    db.commit()

    boss_email = os.getenv("BOSS_EMAIL", "bucevaj@gmail.com") 
    subject = f"Job: {job.task}, is done."
    body = f"{worker.name} {worker.surname} has done the job for the department {job.department} : '{job.task}'."
    send_email_async.delay(boss_email, subject, body)
    return {
        "message": "Job completed",
        "new_level": worker.level.value
    }

@app.get("/get_statistics")
def get_statistics(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
    token: str = Header(...)
):
    results = (
        db.query(
            Worker.id,
            Worker.name,
            Worker.surname,
            Statistics.numberCompletedJobs
        )
        .join(Statistics, Worker.id == Statistics.workerId)
        .order_by(Statistics.numberCompletedJobs.desc())
        .all()
    )

    return [
        {
            "worker_id": row.id,
            "name": row.name,
            "surname": row.surname,
            "completed_jobs": row.numberCompletedJobs
        }
        for row in results
    ]

@app.post("/upgrade_level")
def upgrade_level(
    request: LevelUpgradeRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    worker = db.query(Worker).filter(Worker.id == request.worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    worker.level = request.new_level
    db.commit()

    return {
        "message": f"Worker {worker.name} {worker.surname} promoted to {worker.level.value}",
        "worker_id": worker.id,
        "new_level": worker.level.value
    }

@app.get("/workerHistory")
def get_worker_history(
    worker_id: int = Query(...),
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    worker = db.query(Worker).get(worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    completed_jobs = db.query(Job).filter(
        Job.assigned_to == worker_id,
        Job.status == "completed"
    ).all()

    if not completed_jobs:
        return {"message": f"No completed jobs found for {worker.name} {worker.surname}"}

    job_list = [
        {
            "job_id": job.id,
            "task": job.task,
            "department": job.department
        }
        for job in completed_jobs
    ]

    return {
        "worker": {
            "name": worker.name,
            "surname": worker.surname,
            "level": worker.level.value
        },
        "completed_jobs": job_list
    }

