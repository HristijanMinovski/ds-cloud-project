from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database_1 import SessionLocal
from models_2 import Admin, Worker  
from jose import JWTError, jwt
from fastapi import Header
# for Authentication for every end-point

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_admin(token: str = Header(...), db: Session = Depends(get_db)) -> Admin:
    print(" Received token:", token)

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate admin credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print("Decoded payload:", payload)

        user_id = payload.get("sub")
        role = payload.get("role")

        print("sub:", user_id, "| role:", role)

        if user_id is None or role != "admin":
            print("Invalid role or missing sub")
            raise credentials_exception

        admin = db.query(Admin).filter(Admin.id == int(user_id)).first()
        if not admin:
            print(" Admin not found in DB")
            raise credentials_exception

        print("Admin verified:", admin.email)
        return admin

    except JWTError as e:
        print(" JWT Error:", e)
        raise credentials_exception

    except Exception as e:
        print(" Unhandled exception:", e)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


def get_current_worker(token: str = Header(...), db: Session = Depends(get_db)) -> Worker:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Invalid or missing token"
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        worker_id: str = payload.get("sub")
        role: str = payload.get("role")

        if worker_id is None or role != "worker":
            raise credentials_exception

        worker = db.query(Worker).filter(Worker.id == int(worker_id)).first()
        if worker is None:
            raise credentials_exception

        return worker

    except JWTError:
        raise credentials_exception


