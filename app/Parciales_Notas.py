from uuid import UUID
from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator

from .database import get_db
from . import models

from .admin.schemas_notas import (ParcialCreate, ParcialUpdate, NotaUpdate)

router = APIRouter(prefix="/notas", tags=["Parciales y Notas"])


def _get_parcial_or_404(id_parcial: UUID, db: Session) -> models.Parcial:
    p = db.query(models.Parcial).filter(models.Parcial.id_parcial == id_parcial).first()
    if not p:
        raise HTTPException(status_code=404, detail="Parcial no encontrado")
    return p


def _get_materia_or_404(id_materia: UUID, db: Session) -> models.Materia:
    m = db.query(models.Materia).filter(models.Materia.id_materia == id_materia).first()
    if not m:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
    return m


def _resolver_usuario(id_usuario: UUID, db: Session) -> tuple[str, str]:
    """
    Recibe un id_usuario y devuelve (rol, tipo_parcial).
    - docente  → tipo 'parcial'
    - auxiliar → tipo 'practica'
    - otro / no existe → 403
    """
    usuario = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if usuario.rol == "docente":
        return "docente", "parcial"
    elif usuario.rol == "auxiliar":
        return "auxiliar", "practica"
    else:
        raise HTTPException(
            status_code=403,
            detail="Solo docentes y auxiliares pueden gestionar parciales"
        )


def _verificar_acceso_materia(id_usuario: UUID, rol: str, materia: models.Materia) -> None:
    """Verifica que el usuario tenga acceso a la materia según su rol."""
    if rol == "docente" and materia.id_docente != id_usuario:
        raise HTTPException(status_code=403, detail="El docente no tiene permiso sobre esta materia")
    if rol == "auxiliar" and materia.id_auxiliar != id_usuario:
        raise HTTPException(status_code=403, detail="El auxiliar no tiene permiso sobre esta materia")


def _fmt_parcial(p: models.Parcial) -> dict:
    return {
        "id_parcial":     p.id_parcial,
        "nombre_parcial": p.nombre_parcial,
        "tipo":           p.tipo,
        "fecha":          str(p.fecha) if p.fecha else None,
        "valoracion":     p.valoracion,
        "id_materia":     p.id_materia,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PARCIALES  —  /usuarios/{id_usuario}/parciales
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/usuarios/{id_usuario}/parciales")
def listar_parciales(id_usuario: UUID, db: Session = Depends(get_db)):
    """
    Lista todos los parciales de las materias del usuario.
    - docente  → tipo 'parcial'
    - auxiliar → tipo 'practica'
    """
    rol, tipo = _resolver_usuario(id_usuario, db)

    if rol == "docente":
        filtro_materia = models.Materia.id_docente == id_usuario
    else:
        filtro_materia = models.Materia.id_auxiliar == id_usuario

    parciales = (
        db.query(models.Parcial)
        .join(models.Materia, models.Parcial.id_materia == models.Materia.id_materia)
        .filter(filtro_materia, models.Parcial.tipo == tipo)
        .all()
    )
    return [_fmt_parcial(p) for p in parciales]


@router.post("/usuarios/{id_usuario}/parciales", status_code=status.HTTP_201_CREATED)
def crear_parcial(
    id_usuario: UUID,
    body:       ParcialCreate,
    db:         Session = Depends(get_db),
):
    """
    Crea un parcial en una materia del usuario.
    El tipo se asigna automáticamente:
    - docente  → 'parcial'
    - auxiliar → 'practica'
    """
    rol, tipo = _resolver_usuario(id_usuario, db)
    materia = _get_materia_or_404(body.id_materia, db)
    _verificar_acceso_materia(id_usuario, rol, materia)

    parcial = models.Parcial(
        nombre_parcial = body.nombre_parcial,
        fecha          = body.fecha,
        valoracion     = body.valoracion,
        id_materia     = body.id_materia,
        tipo           = tipo,              # forzado según rol
    )
    db.add(parcial)
    db.commit()
    db.refresh(parcial)
    return _fmt_parcial(parcial)


@router.patch("/usuarios/{id_usuario}/parciales/{id_parcial}")
def editar_parcial(
    id_usuario: UUID,
    id_parcial: UUID,
    body:       ParcialUpdate,
    db:         Session = Depends(get_db),
):
    """Edita un parcial siempre que pertenezca a una materia del usuario."""
    rol, tipo = _resolver_usuario(id_usuario, db)
    parcial = _get_parcial_or_404(id_parcial, db)

    if parcial.tipo != tipo:
        raise HTTPException(
            status_code=400,
            detail=f"Este registro no es de tipo '{tipo}'"
        )

    _verificar_acceso_materia(id_usuario, rol, parcial.materia)

    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(parcial, key, value)

    db.commit()
    db.refresh(parcial)
    return _fmt_parcial(parcial)


@router.delete("/usuarios/{id_usuario}/parciales/{id_parcial}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_parcial(
    id_usuario: UUID,
    id_parcial: UUID,
    db:         Session = Depends(get_db),
):
    """Elimina un parcial de una materia del usuario. Elimina notas en cascada."""
    rol, tipo = _resolver_usuario(id_usuario, db)
    parcial = _get_parcial_or_404(id_parcial, db)

    if parcial.tipo != tipo:
        raise HTTPException(
            status_code=400,
            detail=f"Este registro no es de tipo '{tipo}'"
        )

    _verificar_acceso_materia(id_usuario, rol, parcial.materia)

    db.delete(parcial)
    db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# NOTAS  —  /usuarios/{id_usuario}/parciales/{id_parcial}/notas
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/usuarios/{id_usuario}/parciales/{id_parcial}/notas")
def listar_notas_parcial(
    id_usuario: UUID,
    id_parcial: UUID,
    db:         Session = Depends(get_db),
):
    """Lista las notas de todos los estudiantes en un parcial del usuario."""
    rol, _ = _resolver_usuario(id_usuario, db)
    parcial = _get_parcial_or_404(id_parcial, db)
    _verificar_acceso_materia(id_usuario, rol, parcial.materia)

    notas = db.query(models.Nota).filter(models.Nota.id_parcial == id_parcial).all()
    return [
        {
            "id_estudiante":       n.id_estudiante,
            "nombre":              n.estudiante.nombre,
            "apellido":            n.estudiante.apellido,
            "nota":                float(n.nota) if n.nota is not None else None,
            "observacion":         n.observacion,
            "ultima_modificacion": n.ultima_modificacion,
        }
        for n in notas
    ]


@router.patch("/usuarios/{id_usuario}/parciales/{id_parcial}/notas/{id_estudiante}")
def editar_nota(
    id_usuario:    UUID,
    id_parcial:    UUID,
    id_estudiante: UUID,
    body:          NotaUpdate,
    db:            Session = Depends(get_db),
):
    """Edita (o crea) la nota de un estudiante en un parcial del usuario."""
    rol, _ = _resolver_usuario(id_usuario, db)
    parcial = _get_parcial_or_404(id_parcial, db)
    _verificar_acceso_materia(id_usuario, rol, parcial.materia)

    # Restricción de 10 días: solo docentes y auxiliares la tienen
    if rol in ("docente", "auxiliar") and parcial.fecha:
        from datetime import date as _date
        dias = (_date.today() - parcial.fecha).days
        if dias > 10:
            raise HTTPException(
                status_code=403,
                detail=f"Solo se pueden editar notas dentro de los 10 días siguientes a la fecha del parcial. Han pasado {dias} días.",
            )

    nota = (
        db.query(models.Nota)
        .filter(
            models.Nota.id_parcial    == id_parcial,
            models.Nota.id_estudiante == id_estudiante,
        )
        .first()
    )

    if not nota:
        nota = models.Nota(id_estudiante=id_estudiante, id_parcial=id_parcial)
        db.add(nota)

    if body.nota is not None:
        if parcial.valoracion and body.nota > parcial.valoracion:
            raise HTTPException(
                status_code=422,
                detail=f"La nota ({body.nota}) supera la valoración máxima del parcial ({parcial.valoracion})"
            )
        nota.nota = body.nota

    if body.observacion is not None:
        nota.observacion = body.observacion

    db.commit()
    db.refresh(nota)

    return {
        "id_estudiante":       nota.id_estudiante,
        "id_parcial":          nota.id_parcial,
        "nota":                float(nota.nota) if nota.nota is not None else None,
        "observacion":         nota.observacion,
        "ultima_modificacion": nota.ultima_modificacion,
    }