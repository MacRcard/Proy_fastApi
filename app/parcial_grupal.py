"""
parciales_grupal.py
-------------------
Endpoints para gestionar PARCIALES GRUPALES.
Un parcial grupal permite asignar notas solo a un subconjunto
de estudiantes elegido por el administrador al momento de crearlo.

Rutas:
  POST   /notas/usuarios/{id_usuario}/parciales-grupales
  GET    /notas/usuarios/{id_usuario}/parciales-grupales
  PATCH  /notas/usuarios/{id_usuario}/parciales-grupales/{id_parcial}
  DELETE /notas/usuarios/{id_usuario}/parciales-grupales/{id_parcial}

  GET    /notas/usuarios/{id_usuario}/parciales-grupales/{id_parcial}/notas
  PATCH  /notas/usuarios/{id_usuario}/parciales-grupales/{id_parcial}/notas/{id_estudiante}
"""

from uuid import UUID
from typing import List, Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from .database import get_db
from . import models

router = APIRouter(prefix="/notas", tags=["Parciales Grupales"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ParcialGrupalCreate(BaseModel):
    nombre_parcial:    str
    fecha:             Optional[date] = None
    valoracion:        Optional[int]  = None
    id_materia:        UUID
    estudiantes_ids:   List[UUID]      # ← solo estos reciben nota


class ParcialGrupalUpdate(BaseModel):
    nombre_parcial:  Optional[str]      = None
    fecha:           Optional[date]     = None
    valoracion:      Optional[int]      = None
    estudiantes_ids: Optional[List[UUID]] = None   # reemplaza la lista completa si se envía


class NotaUpdate(BaseModel):
    nota:       Optional[float] = None
    observacion: Optional[str]  = None


# ── Helpers internos ──────────────────────────────────────────────────────────

def _resolver_usuario(id_usuario: UUID, db: Session) -> tuple[str, str]:
    """Devuelve (rol, tipo_parcial). Admin puede actuar como docente."""
    usuario = db.query(models.Usuario).filter(models.Usuario.id_usuario == id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if usuario.rol == "admin":
        return "admin", "grupal"
    if usuario.rol == "docente":
        return "docente", "grupal"
    if usuario.rol == "auxiliar":
        return "auxiliar", "grupal"
    raise HTTPException(status_code=403, detail="Rol no autorizado para gestionar parciales grupales")


def _verificar_acceso_materia(id_usuario: UUID, rol: str, materia: models.Materia) -> None:
    """Admin tiene acceso irrestricto; docente/auxiliar solo a sus materias."""
    if rol == "admin":
        return
    if rol == "docente" and materia.id_docente != id_usuario:
        raise HTTPException(status_code=403, detail="No tienes permiso sobre esta materia")
    if rol == "auxiliar" and materia.id_auxiliar != id_usuario:
        raise HTTPException(status_code=403, detail="No tienes permiso sobre esta materia")


def _get_parcial_or_404(id_parcial: UUID, db: Session) -> models.Parcial:
    p = db.query(models.Parcial).filter(
        models.Parcial.id_parcial == id_parcial,
        models.Parcial.tipo       == "grupal",
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Parcial grupal no encontrado")
    return p


def _fmt_parcial(p: models.Parcial, db: Session) -> dict:
    """Serializa un parcial grupal incluyendo la lista de estudiantes asignados."""
    # Los estudiantes que tienen nota en este parcial (o solo los inscritos en el grupo)
    notas = db.query(models.Nota).filter(models.Nota.id_parcial == p.id_parcial).all()
    estudiantes = []
    for n in notas:
        e = n.estudiante
        estudiantes.append({
            "id_estudiante": str(e.id_estudiante),
            "nombre":        e.nombre,
            "apellido":      e.apellido,
            "ci":            e.ci_estudiante,
            "nota":          float(n.nota) if n.nota is not None else None,
            "observacion":   n.observacion,
        })
    return {
        "id_parcial":     str(p.id_parcial),
        "nombre_parcial": p.nombre_parcial,
        "tipo":           p.tipo,
        "fecha":          str(p.fecha) if p.fecha else None,
        "valoracion":     p.valoracion,
        "id_materia":     str(p.id_materia),
        "estudiantes":    estudiantes,
    }


# ── POST — Crear parcial grupal ───────────────────────────────────────────────

@router.post(
    "/usuarios/{id_usuario}/parciales-grupales",
    status_code=status.HTTP_201_CREATED,
)
def crear_parcial_grupal(
    id_usuario: UUID,
    body:       ParcialGrupalCreate,
    db:         Session = Depends(get_db),
):
    """
    Crea un parcial grupal y genera un registro de nota (vacío) para cada
    estudiante seleccionado.  Solo los estudiantes en 'estudiantes_ids' serán
    evaluados; el resto queda fuera.
    """
    rol, tipo = _resolver_usuario(id_usuario, db)

    materia = db.query(models.Materia).filter(
        models.Materia.id_materia == body.id_materia
    ).first()
    if not materia:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
    _verificar_acceso_materia(id_usuario, rol, materia)

    # Verificar que todos los estudiantes estén inscritos en la materia
    inscritos_ids = {
        str(i.id_estudiante)
        for i in db.query(models.Inscrito).filter(
            models.Inscrito.id_materia == body.id_materia
        ).all()
    }
    for eid in body.estudiantes_ids:
        if str(eid) not in inscritos_ids:
            raise HTTPException(
                status_code=422,
                detail=f"El estudiante {eid} no está inscrito en esta materia",
            )

    if not body.estudiantes_ids:
        raise HTTPException(
            status_code=422,
            detail="Debes seleccionar al menos un estudiante para el parcial grupal",
        )

    # Crear el parcial
    parcial = models.Parcial(
        nombre_parcial = body.nombre_parcial,
        fecha          = body.fecha,
        valoracion     = body.valoracion,
        id_materia     = body.id_materia,
        tipo           = "grupal",
    )
    db.add(parcial)
    db.flush()  # obtener el id_parcial antes del commit

    # Crear notas vacías (marcador de grupo)
    for eid in body.estudiantes_ids:
        nota = models.Nota(
            id_estudiante = eid,
            id_parcial    = parcial.id_parcial,
            nota          = None,
            observacion   = None,
        )
        db.add(nota)

    db.commit()
    db.refresh(parcial)
    return _fmt_parcial(parcial, db)


# ── GET — Listar parciales grupales del usuario ───────────────────────────────

@router.get("/usuarios/{id_usuario}/parciales-grupales")
def listar_parciales_grupales(
    id_usuario: UUID,
    db:         Session = Depends(get_db),
):
    rol, _ = _resolver_usuario(id_usuario, db)

    if rol == "admin":
        parciales = db.query(models.Parcial).filter(
            models.Parcial.tipo == "grupal"
        ).all()
    elif rol == "docente":
        parciales = (
            db.query(models.Parcial)
            .join(models.Materia, models.Parcial.id_materia == models.Materia.id_materia)
            .filter(
                models.Materia.id_docente == id_usuario,
                models.Parcial.tipo       == "grupal",
            )
            .all()
        )
    else:  # auxiliar
        parciales = (
            db.query(models.Parcial)
            .join(models.Materia, models.Parcial.id_materia == models.Materia.id_materia)
            .filter(
                models.Materia.id_auxiliar == id_usuario,
                models.Parcial.tipo        == "grupal",
            )
            .all()
        )

    return [_fmt_parcial(p, db) for p in parciales]


# ── PATCH — Editar parcial grupal ─────────────────────────────────────────────

@router.patch("/usuarios/{id_usuario}/parciales-grupales/{id_parcial}")
def editar_parcial_grupal(
    id_usuario: UUID,
    id_parcial: UUID,
    body:       ParcialGrupalUpdate,
    db:         Session = Depends(get_db),
):
    """
    Edita metadatos del parcial grupal.
    Si se envía 'estudiantes_ids', reemplaza la lista de estudiantes:
      - Elimina notas de los que ya no están en el grupo.
      - Agrega notas vacías para los nuevos.
    """
    rol, _ = _resolver_usuario(id_usuario, db)
    parcial = _get_parcial_or_404(id_parcial, db)
    _verificar_acceso_materia(id_usuario, rol, parcial.materia)

    if body.nombre_parcial is not None:
        parcial.nombre_parcial = body.nombre_parcial
    if body.fecha is not None:
        parcial.fecha = body.fecha
    if body.valoracion is not None:
        parcial.valoracion = body.valoracion

    if body.estudiantes_ids is not None:
        if not body.estudiantes_ids:
            raise HTTPException(
                status_code=422,
                detail="La lista de estudiantes no puede quedar vacía",
            )
        nuevos = {str(e) for e in body.estudiantes_ids}

        # Verificar inscripciones
        inscritos_ids = {
            str(i.id_estudiante)
            for i in db.query(models.Inscrito).filter(
                models.Inscrito.id_materia == parcial.id_materia
            ).all()
        }
        for eid in body.estudiantes_ids:
            if str(eid) not in inscritos_ids:
                raise HTTPException(
                    status_code=422,
                    detail=f"El estudiante {eid} no está inscrito en esta materia",
                )

        actuales = {
            str(n.id_estudiante): n
            for n in db.query(models.Nota).filter(
                models.Nota.id_parcial == id_parcial
            ).all()
        }

        # Eliminar los que ya no están
        for eid_str, nota in actuales.items():
            if eid_str not in nuevos:
                db.delete(nota)

        # Agregar los nuevos
        for eid_str in nuevos:
            if eid_str not in actuales:
                db.add(models.Nota(
                    id_estudiante = UUID(eid_str),
                    id_parcial    = id_parcial,
                    nota          = None,
                    observacion   = None,
                ))

    db.commit()
    db.refresh(parcial)
    return _fmt_parcial(parcial, db)


# ── DELETE — Eliminar parcial grupal ──────────────────────────────────────────

@router.delete(
    "/usuarios/{id_usuario}/parciales-grupales/{id_parcial}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def eliminar_parcial_grupal(
    id_usuario: UUID,
    id_parcial: UUID,
    db:         Session = Depends(get_db),
):
    rol, _ = _resolver_usuario(id_usuario, db)
    parcial = _get_parcial_or_404(id_parcial, db)
    _verificar_acceso_materia(id_usuario, rol, parcial.materia)
    db.delete(parcial)
    db.commit()


# ── GET — Listar notas del parcial grupal ─────────────────────────────────────

@router.get("/usuarios/{id_usuario}/parciales-grupales/{id_parcial}/notas")
def listar_notas_grupal(
    id_usuario: UUID,
    id_parcial: UUID,
    db:         Session = Depends(get_db),
):
    rol, _ = _resolver_usuario(id_usuario, db)
    parcial = _get_parcial_or_404(id_parcial, db)
    _verificar_acceso_materia(id_usuario, rol, parcial.materia)

    notas = db.query(models.Nota).filter(models.Nota.id_parcial == id_parcial).all()
    return [
        {
            "id_estudiante":       str(n.id_estudiante),
            "nombre":              n.estudiante.nombre,
            "apellido":            n.estudiante.apellido,
            "nota":                float(n.nota) if n.nota is not None else None,
            "observacion":         n.observacion,
            "ultima_modificacion": str(n.ultima_modificacion),
        }
        for n in notas
    ]


# ── PATCH — Editar nota individual del parcial grupal ─────────────────────────

@router.patch(
    "/usuarios/{id_usuario}/parciales-grupales/{id_parcial}/notas/{id_estudiante}"
)
def editar_nota_grupal(
    id_usuario:    UUID,
    id_parcial:    UUID,
    id_estudiante: UUID,
    body:          NotaUpdate,
    db:            Session = Depends(get_db),
):
    """Edita la nota de un estudiante en el parcial grupal."""
    rol, _ = _resolver_usuario(id_usuario, db)
    parcial = _get_parcial_or_404(id_parcial, db)
    _verificar_acceso_materia(id_usuario, rol, parcial.materia)

    nota = db.query(models.Nota).filter(
        models.Nota.id_parcial    == id_parcial,
        models.Nota.id_estudiante == id_estudiante,
    ).first()

    if not nota:
        raise HTTPException(
            status_code=404,
            detail="Este estudiante no pertenece al grupo del parcial",
        )

    if body.nota is not None:
        if parcial.valoracion and body.nota > parcial.valoracion:
            raise HTTPException(
                status_code=422,
                detail=f"La nota ({body.nota}) supera la valoración máxima ({parcial.valoracion})",
            )
        nota.nota = body.nota

    if body.observacion is not None:
        nota.observacion = body.observacion

    db.commit()
    db.refresh(nota)

    return {
        "id_estudiante":       str(nota.id_estudiante),
        "id_parcial":          str(nota.id_parcial),
        "nota":                float(nota.nota) if nota.nota is not None else None,
        "observacion":         nota.observacion,
        "ultima_modificacion": str(nota.ultima_modificacion),
    }