from datetime import datetime, timedelta, timezone
from typing import Annotated
import bcrypt
import jwt
from fastapi import FastAPI, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from .parciales import router as parciales_router
from .practicas import router as practicas_router
from .notas_docente import router as notas_docentes_router
from .notas_estudiantes import router as notas_estudiantes_router
from .inscritos import router as inscritos_router
from .admin.crud_admin import router as admin_router

from .database import engine, get_db
from . import models

SECRET_KEY = "7e19d6b108943e9602f19a86d2c08f5533dc13abe9c95bf4f628eb7cb79a4b45"
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

app.include_router(parciales_router)
app.include_router(practicas_router)
app.include_router(notas_docentes_router)
app.include_router(notas_estudiantes_router)
app.include_router(inscritos_router)
app.include_router(admin_router)


# ── Helpers de autenticación ──────────────────────────────────────────────────

def get_user_by_username(username: str, db: Session) -> models.Usuario | None:
    return db.query(models.Usuario).filter(models.Usuario.username == username).first()


def authenticate_password(hashed_password: str, plain_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(seconds=TOKEN_SECONDS_EXP)
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


# ── Login ─────────────────────────────────────────────────────────────────────

@app.post("/users/login/docente", tags=["Auth"])
def login_docente(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    """Autentica un docente y devuelve un token JWT."""
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

    return JSONResponse(status_code=200, content={
        "access_token": token,
        "token_type":   "bearer",
        "expires_in":   TOKEN_SECONDS_EXP,
    })

@app.post("/users/login/auxiliar", tags=["Auth"])
def login_auxiliar(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    """Autentica un auxiliar y devuelve un token JWT."""
    user = get_user_by_username(username, db)

    if user is None or user.rol != "auxiliar":
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    if not authenticate_password(user.password, password):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    token = create_token({
        "sub":      str(user.id_usuario),
        "username": user.username,
        "rol":      user.rol,
    })
    return JSONResponse(status_code=200, content={
        "access_token": token,
        "token_type":   "bearer",
        "expires_in":   TOKEN_SECONDS_EXP,
    })


@app.post("/users/logout", tags=["Auth"])
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response
    


# ── Consultas ─────────────────────────────────────────────────────────────────

@app.get("/docentes/", tags=["Docentes"])
def get_docentes(db: Session = Depends(get_db)):
    """Lista todos los docentes con sus datos."""
    docentes = db.query(models.Docente).all()
    return [
        {
            "id_usuario": d.id_usuario,
            "username":   d.usuario.username if d.usuario else None,
            "titulo":     d.titulo,
            "nombre":     d.nombre_docente,
            "apellido":   d.apellido_docente,
        }
        for d in docentes
    ]


@app.get("/estudiantes/", tags=["Estudiantes"])
def get_estudiantes(db: Session = Depends(get_db)):
    """Lista todos los estudiantes."""
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


@app.get("/auxiliares/", tags=["Auxiliares"])
def get_auxiliares(db: Session = Depends(get_db)):
    """Lista todos los auxiliares."""
    auxiliares = db.query(models.Auxiliar).all()
    return [
        {
            "id_usuario": a.id_usuario,
            "username":   a.usuario.username if a.usuario else None,
            "nombre":     a.nombre,
            "email":      a.email,
            "activo":     a.activo,
        }
        for a in auxiliares
    ]


@app.get("/materias/", tags=["Materias"])
def get_materias(db: Session = Depends(get_db)):
    """Lista todas las materias con docente y auxiliar asignados."""
    materias = db.query(models.Materia).all()
    return [
        {
            "id_materia":  m.id_materia,
            "sigla":       m.sigla,
            "horario":     m.horario,
            "anio":        m.anio,
            "docente": {
                "id_usuario": m.docente.id_usuario,
                "nombre":     m.docente.nombre_docente,
                "apellido":   m.docente.apellido_docente,
                "titulo":     m.docente.titulo,
            } if m.docente else None,
            "auxiliar": {
                "id_usuario": m.auxiliar.id_usuario,
                "nombre":     m.auxiliar.nombre,
                "email":      m.auxiliar.email,
            } if m.auxiliar else None,
        }
        for m in materias
    ]