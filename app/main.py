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

from .parciales import router as parciales_router
from .practicas import router as practicas_router
from .notas_docente import router as notas_docentes_router
from .notas_estudiantes import router as notas_estudiantes_router
from .inscritos import router as inscritos_router
from .admin.crud_admin import router as admin_router
from .admin.crud_materias import router as materias_router
from .admin.crud_estudiantes import router as estudiantes_router
from .admin.pacriales_notas import router as notas_router

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

def get_user_by_username(username: str, db: Session) -> models.Usuario | None:
    return db.query(models.Usuario).filter(models.Usuario.username == username).first()

def authenticate_password(hashed_password: str, plain_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(seconds=TOKEN_SECONDS_EXP)
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: Session = Depends(get_db)
) -> models.Usuario:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token inválido")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

    user = db.query(models.Usuario).filter(models.Usuario.id_usuario == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user

def require_admin(current_user: models.Usuario = Depends(get_current_user)) -> models.Usuario:
    """Dependencia que lanza 403 si el usuario autenticado no es admin."""
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="Acceso solo para administradores")
    return current_user

# ── Login ─────────────────────────────────────────────────────────────────────

# @app.post("/users/login/docente", tags=["Auth"])
# def login_docente(
#     username: Annotated[str, Form()],
#     password: Annotated[str, Form()],
#     db: Session = Depends(get_db),
# ):
#     """Autentica un docente y devuelve un token JWT."""
#     user = get_user_by_username(username, db)

#     if user is None or user.rol != "docente":
#         raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
#     if not authenticate_password(user.password, password):
#         raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

#     token = create_token({
#         "sub":      str(user.id_usuario),
#         "username": user.username,
#         "rol":      user.rol,
#     })

#     return JSONResponse(status_code=200, content={
#         "access_token": token,
#         "token_type":   "bearer",
#         "expires_in":   TOKEN_SECONDS_EXP,
#     })

# @app.post("/users/login/auxiliar", tags=["Auth"])
# def login_auxiliar(
#     username: Annotated[str, Form()],
#     password: Annotated[str, Form()],
#     db: Session = Depends(get_db),
# ):
#     """Autentica un auxiliar y devuelve un token JWT."""
#     user = get_user_by_username(username, db)

#     if user is None or user.rol != "auxiliar":
#         raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
#     if not authenticate_password(user.password, password):
#         raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

#     token = create_token({
#         "sub":      str(user.id_usuario),
#         "username": user.username,
#         "rol":      user.rol,
#     })
#     return JSONResponse(status_code=200, content={
#         "access_token": token,
#         "token_type":   "bearer",
#         "expires_in":   TOKEN_SECONDS_EXP,
#     })

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
        id_usuario = uuid.uuid4(),   # ← corregido: instancia, no la clase
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

# ── Consultas ─────────────────────────────────────────────────────────────────

# @app.get("/docentes/", tags=["Usuarios"])
# def get_docentes(db: Session = Depends(get_db)):
#     """Lista todos los docentes con sus datos."""
#     docentes = db.query(models.Docente).all()
#     return [
#         {
#             "id_usuario": d.id_usuario,
#             "username":   d.usuario.username if d.usuario else None,
#             "titulo":     d.titulo,
#             "nombre":     d.nombre_docente,
#             "apellido":   d.apellido_docente,
#         }
#         for d in docentes
#     ]

# @app.get("/auxiliares/", tags=["Usuarios"])
# def get_auxiliares(db: Session = Depends(get_db)):
#     """Lista todos los auxiliares."""
#     auxiliares = db.query(models.Auxiliar).all()
#     return [
#         {
#             "id_usuario": a.id_usuario,
#             "username":   a.usuario.username if a.usuario else None,
#             "nombre":     a.nombre,
#             "email":      a.email,
#             "activo":     a.activo,
#         }
#         for a in auxiliares
#     ]

#listar matrias en admin/crud_materias.py con distintos filtros