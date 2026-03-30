"""
Rutas generales de usuarios:
  GET  /login                  → página de login (elige rol)
  GET  /register/docente       → formulario registro docente
  GET  /register/estudiante    → formulario registro estudiante
  POST /users/register/docente
  POST /users/register/estudiante
  POST /users/login/docente    → CI + contraseña
  POST /users/login/estudiante → CI + correo
  POST /users/logout
  GET  /users/dashboard
  GET  /usuarios/              → lista todos los usuarios (JSON)
"""
from typing import Annotated

import bcrypt
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import models
from database import get_db
from routes.auth import (
    TOKEN_SECONDS_EXP, create_token, decode_token,
    get_token_from_cookie, set_auth_cookie,
)
from schemas import (
    DocenteOut, EstudianteOut, UsuarioOut,
)

router    = APIRouter(tags=["usuarios"])
templates = Jinja2Templates(directory="templates")


# ── helpers ────────────────────────────────────────────────────────────────

def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def _check(hashed: str, plain: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def _get_by_ci(ci: str, db: Session) -> models.Usuario | None:
    return db.query(models.Usuario).filter(models.Usuario.ci == ci).first()


# ── páginas HTML ────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/register/docente", response_class=HTMLResponse)
def register_docente_page(request: Request):
    return templates.TemplateResponse("register_docente.html", {"request": request})

@router.get("/register/estudiante", response_class=HTMLResponse)
def register_estudiante_page(request: Request):
    return templates.TemplateResponse("register_estudiante.html", {"request": request})


# ── registro ────────────────────────────────────────────────────────────────

@router.post("/users/register/docente")
def register_docente(
    ci:       Annotated[str, Form()],
    nombre:   Annotated[str, Form()],
    apellido: Annotated[str, Form()],
    password: Annotated[str, Form()],
    titulo:   Annotated[str, Form()],   # licenciado | doctor | magister
    db: Session = Depends(get_db),
):
    if _get_by_ci(ci, db):
        raise HTTPException(400, f"El CI '{ci}' ya está registrado")

    usuario = models.Usuario(ci=ci, nombre=nombre, apellido=apellido, rol="docente")
    db.add(usuario)
    db.flush()

    db.add(models.Docente(
        id_usuario=usuario.id_usuario,
        titulo=titulo,
        contrasenia=_hash(password),
    ))
    db.commit()
    return RedirectResponse("/login", status_code=302)


@router.post("/users/register/estudiante")
def register_estudiante(
    ci:        Annotated[str, Form()],
    nombre:    Annotated[str, Form()],
    apellido:  Annotated[str, Form()],
    matricula: Annotated[str, Form()],
    correo:    Annotated[str, Form()],
    anio:      Annotated[int | None, Form()] = None,
    mencion:   Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
):
    if _get_by_ci(ci, db):
        raise HTTPException(400, f"El CI '{ci}' ya está registrado")

    usuario = models.Usuario(ci=ci, nombre=nombre, apellido=apellido, rol="estudiante")
    db.add(usuario)
    db.flush()

    db.add(models.Estudiante(
        id_usuario=usuario.id_usuario,
        matricula=matricula,
        correo=correo,
        anio=anio,
        mencion=mencion,
    ))
    db.commit()
    return RedirectResponse("/login", status_code=302)


# ── login ───────────────────────────────────────────────────────────────────

@router.post("/users/login/docente")
def login_docente(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    user = _get_by_ci(username, db)
    if not user or user.rol != "docente" or not user.docente:
        raise HTTPException(401, "CI o contraseña incorrectos")
    if not _check(user.docente.contrasenia, password):
        raise HTTPException(401, "CI o contraseña incorrectos")

    token = create_token({
        "sub": str(user.ci), "nombre": user.nombre,
        "apellido": user.apellido, "rol": user.rol,
    })
    return set_auth_cookie(RedirectResponse("/users/dashboard", status_code=302), token)


@router.post("/users/login/estudiante")
def login_estudiante(
    ci:     Annotated[str, Form()],
    correo: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    user = _get_by_ci(ci, db)
    if not user or user.rol != "estudiante" or not user.estudiante:
        raise HTTPException(401, "CI o correo incorrectos")
    if user.estudiante.correo != correo:
        raise HTTPException(401, "CI o correo incorrectos")

    token = create_token({
        "sub": str(user.ci), "nombre": user.nombre,
        "apellido": user.apellido, "rol": user.rol,
    })
    return set_auth_cookie(RedirectResponse("/users/dashboard", status_code=302), token)


# ── dashboard / logout ──────────────────────────────────────────────────────

@router.get("/users/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/login", status_code=302)
    try:
        data = decode_token(token)
    except HTTPException:
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse("dashboard.html", {
        "request":  request,
        "nombre":   data["nombre"],
        "apellido": data["apellido"],
        "rol":      data["rol"],
    })


@router.post("/users/logout")
def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie("access_token")
    return resp


# ── listado de usuarios (JSON) ──────────────────────────────────────────────

@router.get("/usuarios/")
def listar_usuarios(db: Session = Depends(get_db)):
    """Devuelve todos los usuarios con sus datos específicos según rol."""
    result = []
    for u in db.query(models.Usuario).all():
        base = {
            "id_usuario": u.id_usuario,
            "ci":         u.ci,
            "nombre":     u.nombre,
            "apellido":   u.apellido,
            "rol":        u.rol,
        }
        if u.rol == "docente" and u.docente:
            base["titulo"] = u.docente.titulo
        elif u.rol == "estudiante" and u.estudiante:
            base |= {
                "matricula": u.estudiante.matricula,
                "correo":    u.estudiante.correo,
                "anio":      u.estudiante.anio,
                "mencion":   u.estudiante.mencion,
            }
        result.append(base)
    return result