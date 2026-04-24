from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import APIRouter, FastAPI, Form, HTTPException, Depends
from fastapi.security import HTTPBearer
from fastapi.templating import Jinja2Templates
from fastapi.responses import  RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from .parciales import router as parciales_router
from .notas_docente import router as notas_docentes_router
from .notas_estudiantes import router as notas_estudiantes_router
from .inscritos import router as inscritos_router
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
import bcrypt

from .database import engine, get_db
from . import models

SECRET_KEY = "7e19d6b108943e9602f19a86d2c08f5533dc13abe9c95bf4f628eb7cb79a4b45"
TOKEN_SECONDS_EXP = 60*60*24*10

app = FastAPI()

models.Base.metadata.create_all(bind=engine)
app.include_router(parciales_router)
app.include_router(notas_docentes_router)
app.include_router(notas_estudiantes_router)
app.include_router(inscritos_router)

# para la autenticacion

def get_user_by_username(username: str, db: Session) -> models.Usuario | None:
    """Busca un usuario por su username (campo username en tabla usuario)."""
    return db.query(models.Usuario).filter(models.Usuario.username == username).first()

def hash_password(plain_password: str) -> str:
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")

def authenticate_password(hashed_password: str, plain_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )

def create_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(seconds=TOKEN_SECONDS_EXP)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")

###### login #####

@app.post("/users/login/docente")
def login_docente(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    """Autentica docente [username y password]
    Devuelve token JWT"""
    user = get_user_by_username(username, db)

    if user is None or user.rol != "docente":
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    if not authenticate_password(user.password, password):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    token = create_token({
        "sub":      str(user.id_usuario),
        "username": user.username,
        "rol":      user.rol,
    })

    return JSONResponse(
        status_code=200,
        content={
            "access_token": token,
            "token_type":   "bearer",
            "expires_in":   TOKEN_SECONDS_EXP,
        },
    )

@app.get("/usuarios/")
def read_users(db: Session = Depends(get_db)):
    """Lista todos los usuarios con sus datos extendidos según rol."""
    usuarios = db.query(models.Usuario).all()
    resultado = []
    for u in usuarios:
        base = {
            "id_usuario": u.id_usuario,
            "username":   u.username,
            "rol":        u.rol,
        }
        if u.rol == "docente" and u.docente:
            base["nombre"]   = u.docente.nombre_docente
            base["apellido"] = u.docente.apellido_docente
            base["titulo"]   = u.docente.titulo
        resultado.append(base)
    return resultado


###### Estudiantes #####

@app.get("/estudiantes/")
def read_estudiantes(db: Session = Depends(get_db)):
    """Todos los estudiantes"""
    estudiantes = db.query(models.Estudiante).all()
    return [
        {
            "id_estudiante": e.id_estudiante,
            "ci_estudiante": e.ci_estudiante,
            "matricula":     e.matricula,
            "nombre":        e.nombre,
            "apellido":      e.apellido,
            "anio":          e.anio,
            "mencion":       e.mencion,
        }
        for e in estudiantes
    ]
####### Logout ######

@app.post("/users/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response