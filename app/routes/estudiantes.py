"""
Rutas exclusivas del estudiante.
(Listo para extender con: mis materias, mis notas, etc.)
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

import models
from database import get_db
from routes.auth import decode_token

router    = APIRouter(prefix="/estudiante", tags=["estudiantes"])
templates = Jinja2Templates(directory="templates")


def _get_estudiante(request: Request, db: Session):
    """Valida cookie y devuelve el Estudiante; (None, None) si falla."""
    token = request.cookies.get("access_token")
    if not token:
        return None, None
    try:
        payload = decode_token(token)
    except HTTPException:
        return None, None

    if payload.get("rol") != "estudiante":
        return None, None

    usuario = db.query(models.Usuario).filter(
        models.Usuario.ci == payload["sub"]
    ).first()

    if not usuario or not usuario.estudiante:
        return None, None

    return payload, usuario.estudiante


@router.get("/materias", response_class=HTMLResponse)
def mis_materias(request: Request, db: Session = Depends(get_db)):
    """Lista las materias en las que el estudiante está inscrito."""
    payload, estudiante = _get_estudiante(request, db)
    if not estudiante:
        return RedirectResponse("/login", status_code=302)

    # Materias distintas en las que tiene filas en inscrito
    materias = (
        db.query(models.Materia)
        .join(models.Inscrito, models.Inscrito.sigla_materia == models.Materia.sigla)
        .filter(models.Inscrito.id_estudiante == estudiante.id_usuario)
        .distinct()
        .all()
    )

    return templates.TemplateResponse("estudiante/materias.html", {
        "request":    request,
        "nombre":     estudiante.usuario.nombre,
        "apellido":   estudiante.usuario.apellido,
        "materias":   materias,
    })