from datetime import datetime, timedelta, timezone
from typing import Annotated
import uuid
import bcrypt
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from fastapi import FastAPI, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .auth import (get_user_by_username,authenticate_password,create_token,get_current_user,require_admin,SECRET_KEY,ALGORITHM,TOKEN_SECONDS_EXP)

from .parciales import router as parciales_router
from .practicas import router as practicas_router
from .admin.bulk_notas import router as bulk_notas_router
from .notas_docente import router as notas_docentes_router
from .notas_estudiantes import router as notas_estudiantes_router
from .inscritos import router as inscritos_router
from .admin.crud_admin import router as admin_router
from .admin.crud_materias import router as materias_router
from .admin.crud_estudiantes import router as estudiantes_router
from .admin.parciales_notas import router as notas_router
# excel

from .database import engine, get_db
from . import models

SECRET_KEY = "7e19d6b108943e9602f19a86d2c08f5533dc13abe9c95bf4f628eb7cb79a4b45"
ALGORITHM = "HS256"
TOKEN_SECONDS_EXP = 60*60*24*10

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

models.Base.metadata.create_all(bind=engine)
# excel
app.include_router(bulk_notas_router)

app.include_router(parciales_router)
app.include_router(practicas_router)
app.include_router(notas_docentes_router)
app.include_router(notas_estudiantes_router)
app.include_router(inscritos_router)
app.include_router(admin_router)
app.include_router(materias_router)
app.include_router(estudiantes_router)
app.include_router(notas_router)

# nuevo admin
class AdminCreate(BaseModel):
    username: str
    password: str

# ── Helpers de autenticación ──────────────────────────────────────────────────

@app.post("/users/login", tags=["Auth"])
def login_general(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    """Autentica cualquier usuario (docente, auxiliar, admin) y devuelve un token JWT."""
    user = get_user_by_username(username, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    if not authenticate_password(user.password, password):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    
    token = create_token({
        "sub": str(user.id_usuario),
        "username": user.username,
        "rol": user.rol,
    })
    return JSONResponse(status_code=200, content={
        "access_token": token,
        "token_type": "bearer",
        "expires_in": TOKEN_SECONDS_EXP,
        "rol": user.rol,  # útil para el frontend
    })

@app.post("/users/logout", tags=["Auth"])
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response

@app.post("/usuarios/admin", status_code=201, tags=["Usuarios"])
def create_admin(
    body:         AdminCreate,
    db:           Session         = Depends(get_db),
    _:            models.Usuario  = Depends(require_admin),
):
    """Crea un nuevo usuario con rol='admin'. Solo admins pueden hacerlo."""
    existe = db.query(models.Usuario).filter(
        models.Usuario.username == body.username
    ).first()
    if existe:
        raise HTTPException(status_code=409, detail="El username ya está en uso")

    nuevo = models.Usuario(
        id_usuario = uuid.uuid4(),
        username   = body.username,
        password   = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
        rol        = "admin",
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    return {
        "message":    "Admin creado exitosamente",
        "id_usuario": str(nuevo.id_usuario),
        "username":   nuevo.username,
    }