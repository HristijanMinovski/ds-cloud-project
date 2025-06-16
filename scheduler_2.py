from fastapi import FastAPI, Depends, HTTPException,BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database_1 import SessionLocal, init_db
from models_2 import Job, LevelEnum, Worker
from tasks import send_email_async
import json

# scheduler dodava rabota pri sendEmail

app = FastAPI()
init_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class JobRequest(BaseModel):
    task: str
    payload: dict
    department: str
    required_level: LevelEnum

@app.post("/submit_job")
def submit_job(job: JobRequest, db: Session = Depends(get_db)):
    job_obj = Job(
        task=job.task,
        payload=json.dumps(job.payload),
        department=job.department,
        required_level=job.required_level
    )
    db.add(job_obj); db.commit(); db.refresh(job_obj)

    level_values = {"junior":1, "medior":2, "senior":3}
    required_val = level_values[job.required_level.value]
    eligible = db.query(Worker).filter(
        Worker.department==job.department,
        Worker.level.in_(
            [lvl for lvl,val in level_values.items() if val>=required_val]
        )
    ).all()
    subject = f"New job: {job.task}"
    body = f"Description: {job.payload}"
    for w in eligible:
        send_email_async.delay(w.email, subject, body)

    return {"message":"Job submitted", "job_id":job_obj.id}
