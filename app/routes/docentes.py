"""
Rutas exclusivas del docente:
  GET  /docente/materias                          → lista materias asignadas
  GET  /docente/materias/{sigla}/parciales        → parciales de una materia
  GET  /docente/materias/{sigla}/parcial/nuevo    → formulario nuevo parcial
  POST /docente/materias/{sigla}/parcial/nuevo    → guarda el parcial
"""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

import models
from database import get_db
from routes.auth import create_token, decode_token, set_auth_cookie
from schemas import MateriaOut, ParcialOut

router    = APIRouter(prefix="/docente", tags=["docentes"])
templates = Jinja2Templates(directory="templates")


# ── helper: valida cookie y devuelve (payload, models.Docente) ──────────────

def _get_docente(request: Request, db: Session):
    """
    Lee el JWT de la cookie y devuelve (payload, Docente).
    Si algo falla devuelve (None, None) para que la ruta redirija.
    """
    token = request.cookies.get("access_token")
    if not token:
        return None, None
    try:
        payload = decode_token(token)
    except HTTPException:
        return None, None

    if payload.get("rol") != "docente":
        return None, None

    usuario = db.query(models.Usuario).filter(
        models.Usuario.ci == payload["sub"]
    ).first()

    if not usuario or not usuario.docente:
        return None, None

    return payload, usuario.docente


# ── GET /docente/materias ───────────────────────────────────────────────────

@router.get("/materias", response_class=HTMLResponse)
def mis_materias(request: Request, db: Session = Depends(get_db)):
    """Muestra todas las materias asignadas al docente logueado."""
    payload, docente = _get_docente(request, db)
    if not docente:
        return RedirectResponse("/login", status_code=302)

    materias = (
        db.query(models.Materia)
        .filter(models.Materia.id_docente == docente.id_usuario)
        .all()
    )

    return templates.TemplateResponse("docente/materias.html", {
        "request":  request,
        "nombre":   docente.usuario.nombre,
        "apellido": docente.usuario.apellido,
        "materias": materias,          # lista de Materia
    })


# ── GET /docente/materias/{sigla}/parciales ─────────────────────────────────

@router.get("/materias/{sigla}/parciales", response_class=HTMLResponse)
def ver_parciales(sigla: str, request: Request, db: Session = Depends(get_db)):
    """Lista los parciales ya creados para una materia."""
    payload, docente = _get_docente(request, db)
    if not docente:
        return RedirectResponse("/login", status_code=302)

    materia = _get_materia_docente(sigla, docente.id_usuario, db)

    # Parciales vinculados a esta materia a través de inscrito
    parciales = (
        db.query(models.Parcial)
        .join(models.Inscrito, models.Inscrito.id_parcial == models.Parcial.id_parcial)
        .filter(models.Inscrito.sigla_materia == sigla)
        .distinct()
        .all()
    )

    return templates.TemplateResponse("docente/parciales.html", {
        "request":  request,
        "materia":  materia,
        "parciales": parciales,
    })


# ── GET /docente/materias/{sigla}/parcial/nuevo ─────────────────────────────

@router.get("/materias/{sigla}/parcial/nuevo", response_class=HTMLResponse)
def nuevo_parcial_form(sigla: str, request: Request, db: Session = Depends(get_db)):
    """Formulario para registrar un nuevo parcial."""
    payload, docente = _get_docente(request, db)
    if not docente:
        return RedirectResponse("/login", status_code=302)

    materia = _get_materia_docente(sigla, docente.id_usuario, db)

    return templates.TemplateResponse("docente/nuevo_parcial.html", {
        "request": request,
        "materia": materia,
    })


# ── POST /docente/materias/{sigla}/parcial/nuevo ────────────────────────────

@router.post("/materias/{sigla}/parcial/nuevo")
def crear_parcial(
    sigla:          str,
    request:        Request,
    nombre_parcial: Annotated[str,  Form()],
    fecha:          Annotated[date, Form()],
    valoracion:     Annotated[int,  Form()],
    db: Session = Depends(get_db),
):
    """
    Guarda el nuevo parcial y crea una fila en `inscrito` por cada
    estudiante ya inscrito en la materia (nota = NULL, lista para calificar).
    """
    payload, docente = _get_docente(request, db)
    if not docente:
        return RedirectResponse("/login", status_code=302)

    materia = _get_materia_docente(sigla, docente.id_usuario, db)

    if not (1 <= valoracion <= 100):
        raise HTTPException(400, "La valoración debe estar entre 1 y 100")

    # 1. Crear el parcial
    parcial = models.Parcial(
        nombre_parcial=nombre_parcial,
        fecha=fecha,
        valoracion=valoracion,
    )
    db.add(parcial)
    db.flush()   # obtiene id_parcial antes del commit

    # 2. Pre-inscribir a cada estudiante de la materia en este parcial
    estudiantes = (
        db.query(models.Inscrito.id_estudiante)
        .filter(models.Inscrito.sigla_materia == sigla)
        .distinct()
        .all()
    )

    for (id_est,) in estudiantes:
        db.add(models.Inscrito(
            id_estudiante=id_est,
            sigla_materia=sigla,
            id_parcial=parcial.id_parcial,
            nota=None,
        ))

    db.commit()

    # Redirige a la lista de parciales de esa materia
    return RedirectResponse(f"/docente/materias/{sigla}/parciales", status_code=302)


# ── helper interno ──────────────────────────────────────────────────────────

def _get_materia_docente(sigla: str, id_docente: int, db: Session) -> models.Materia:
    """Devuelve la materia solo si pertenece al docente; lanza 404 si no."""
    materia = (
        db.query(models.Materia)
        .filter(
            models.Materia.sigla == sigla,
            models.Materia.id_docente == id_docente,
        )
        .first()
    )
    if not materia:
        raise HTTPException(404, "Materia no encontrada o no asignada a este docente")
    return materia