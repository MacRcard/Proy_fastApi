from typing import Annotated
from datetime import date
from fastapi import APIRouter, Form, HTTPException, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

from .database import get_db
from . import models

SECRET_KEY = "7e19d6b108943e9602f19a86d2c08f5533dc13abe9c95bf4f628eb7cb79a4b45"

router = APIRouter(prefix="/parciales", tags=["parciales"])
jinja2_template = Jinja2Templates(directory="templates")


# ── Utilidad: verificar que el request viene de un docente autenticado ────────

def get_docente_from_cookie(request: Request, db: Session) -> models.Docente:
    """
    Extrae y valida el JWT de la cookie. Lanza 401/403 si no es docente.
    Devuelve la instancia Docente del usuario autenticado.
    """
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        payload = jwt.decode(access_token, key=SECRET_KEY, algorithms=["HS256"])
    except (InvalidTokenError, ExpiredSignatureError):
        raise HTTPException(status_code=401, detail="Sesión expirada o inválida")

    if payload.get("rol") != "docente":
        raise HTTPException(status_code=403, detail="Solo los docentes pueden realizar esta acción")

    ci = payload.get("sub")
    usuario = db.query(models.Usuario).filter(models.Usuario.ci == ci).first()
    if usuario is None or usuario.docente is None:
        raise HTTPException(status_code=401, detail="Docente no encontrado")

    return usuario.docente


def get_materia_del_docente(sigla: str, docente: models.Docente, db: Session) -> models.Materia:
    """Verifica que la materia exista y pertenezca al docente autenticado."""
    materia = db.query(models.Materia).filter(models.Materia.sigla == sigla).first()
    if materia is None:
        raise HTTPException(status_code=404, detail=f"Materia '{sigla}' no encontrada")
    if materia.id_docente != docente.id_usuario:
        raise HTTPException(status_code=403, detail="No tienes permiso sobre esta materia")
    return materia


# ── Páginas HTML ──────────────────────────────────────────────────────────────

@router.get("/nuevo", response_class=HTMLResponse)
def form_nuevo_parcial(request: Request, db: Session = Depends(get_db)):
    docente = get_docente_from_cookie(request, db)
    return jinja2_template.TemplateResponse(
        "parcial_nuevo.html",
        {
            "request": request,
            "materias": docente.materias,
        },
    )


@router.get("/{id_parcial}/editar", response_class=HTMLResponse)
def form_editar_parcial(id_parcial: int, request: Request, db: Session = Depends(get_db)):
    docente = get_docente_from_cookie(request, db)
    parcial = db.query(models.Parcial).filter(models.Parcial.id_parcial == id_parcial).first()
    if parcial is None:
        raise HTTPException(status_code=404, detail="Parcial no encontrado")
    # Verificar que la materia del parcial pertenece a este docente
    get_materia_del_docente(parcial.sigla_materia, docente, db)
    return jinja2_template.TemplateResponse(
        "parcial_editar.html",
        {
            "request": request,
            "parcial": parcial,
            "materias": docente.materias,
        },
    )


# ── Endpoints POST ────────────────────────────────────────────────────────────

@router.post("/nuevo")
def crear_parcial(
    request: Request,
    nombre_parcial: Annotated[str, Form()],
    fecha:          Annotated[date, Form()],
    valoracion:     Annotated[int, Form()],
    sigla_materia:  Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    docente = get_docente_from_cookie(request, db)
    get_materia_del_docente(sigla_materia, docente, db)

    nuevo_parcial = models.Parcial(
        nombre_parcial=nombre_parcial,
        fecha=fecha,
        valoracion=valoracion,
        sigla_materia=sigla_materia,
    )
    db.add(nuevo_parcial)
    db.commit()
    db.refresh(nuevo_parcial)
    return RedirectResponse("/users/dashboard", status_code=302)


@router.post("/{id_parcial}/editar")
def editar_parcial(
    id_parcial: int,
    request: Request,
    nombre_parcial: Annotated[str, Form()],
    fecha:          Annotated[date, Form()],
    valoracion:     Annotated[int, Form()],
    sigla_materia:  Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    docente = get_docente_from_cookie(request, db)

    parcial = db.query(models.Parcial).filter(models.Parcial.id_parcial == id_parcial).first()
    if parcial is None:
        raise HTTPException(status_code=404, detail="Parcial no encontrado")

    # Verificar que la materia actual del parcial pertenece al docente
    get_materia_del_docente(parcial.sigla_materia, docente, db)

    # Si cambió la materia, verificar que la nueva también es suya
    if sigla_materia != parcial.sigla_materia:
        get_materia_del_docente(sigla_materia, docente, db)

    parcial.nombre_parcial = nombre_parcial
    parcial.fecha          = fecha
    parcial.valoracion     = valoracion
    parcial.sigla_materia  = sigla_materia

    db.commit()
    db.refresh(parcial)
    return RedirectResponse("/users/dashboard", status_code=302)


# ── Endpoints JSON (consulta) ─────────────────────────────────────────────────

@router.get("/materia/{sigla}")
def listar_parciales_materia(sigla: str, request: Request, db: Session = Depends(get_db)):
    """Lista todos los parciales de una materia. Solo el docente dueño puede consultarlos."""
    docente = get_docente_from_cookie(request, db)
    materia = get_materia_del_docente(sigla, docente, db)
    return {
        "sigla":     materia.sigla,
        "horario":   materia.horario,
        "parciales": [
            {
                "id_parcial":     p.id_parcial,
                "nombre_parcial": p.nombre_parcial,
                "fecha":          p.fecha,
                "valoracion":     p.valoracion,
            }
            for p in materia.parciales
        ],
    }