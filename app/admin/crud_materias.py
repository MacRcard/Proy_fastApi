import uuid
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from .schemas_admin import (MateriaCreate, MateriaOut, MateriaUpdate, DocenteResumen, AuxiliarResumen, ParcialResumen)


router = APIRouter(prefix="/admin/materias", tags=["Admin - Materias"])

def _build_out(m: models.Materia) -> MateriaOut:
    return MateriaOut(
        id_materia  = m.id_materia,
        sigla       = m.sigla,
        nombre_materia=m.nombre_materia,
        horario     = m.horario,
        anio        = m.anio,
        docente     = DocenteResumen(
            id_usuario = m.docente.id_usuario,
            nombre     = m.docente.nombre_docente,
            apellido   = m.docente.apellido_docente,
            titulo     = m.docente.titulo,
        ) if m.docente else None,
        auxiliar    = AuxiliarResumen(
            id_usuario = m.auxiliar.id_usuario,
            nombre     = m.auxiliar.nombre,
            email      = m.auxiliar.email,
        ) if m.auxiliar else None,
        parciales   = [
            ParcialResumen(
                id_parcial     = p.id_parcial,
                nombre_parcial = p.nombre_parcial,
                fecha          = p.fecha,
                valoracion     = p.valoracion,
                tipo           = p.tipo,
            )
            for p in m.parciales
        ],
    )


def _get_materia_or_404(id_materia: UUID, db: Session) -> models.Materia:
    obj = db.query(models.Materia).filter(
        models.Materia.id_materia == id_materia
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
    return obj

def _validar_docente(id_docente: UUID, db: Session) -> None:
    existe = db.query(models.Docente).filter(
        models.Docente.id_usuario == id_docente
    ).first()
    if not existe:
        raise HTTPException(status_code=404, detail="Docente no encontrado")

def _validar_auxiliar(id_auxiliar: UUID, db: Session) -> None:
    obj = db.query(models.Auxiliar).filter(
        models.Auxiliar.id_usuario == id_auxiliar
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Auxiliar no encontrado")
    if not obj.activo:
        raise HTTPException(status_code=403, detail="El auxiliar esta inactivo")

# def _validar_gestion(id_gestion: UUID, db: Session) -> None:
#     """Valida que la gestion exista. Ajusta el modelo si tu Gestion tiene otro nombre."""
#     if not hasattr(models, "Gestion"):
#         return  # si aun no esta en models.py, se omite la validacion
#     existe = db.query(models.Gestion).filter(
#         models.Gestion.id_gestion == id_gestion
#     ).first()
#     if not existe:
#         raise HTTPException(status_code=404, detail="Gestion no encontrada")
# ----Crud materias------------------
@router.get("/", response_model=List[MateriaOut])
def list_materias(
    # id_gestion:  Optional[UUID] = None,
    id_docente:  Optional[UUID] = None,
    id_auxiliar: Optional[UUID] = None,
    db: Session = Depends(get_db),
):
    """Lista todas las materias.
    Filtros opcionales por query param: ?id_gestion=... &id_docente=... &id_auxiliar=..."""
    q = db.query(models.Materia)
    # if id_gestion:
    #     q = q.filter(models.Materia.id_gestion == id_gestion)
    if id_docente:
        q = q.filter(models.Materia.id_docente == id_docente)
    if id_auxiliar:
        q = q.filter(models.Materia.id_auxiliar == id_auxiliar)
    return [_build_out(m) for m in q.all()]

@router.get("/{id_materia}", response_model=MateriaOut)
def get_materia(id_materia: UUID, db: Session = Depends(get_db)):
    """Obtiene una materia por su id."""
    return _build_out(_get_materia_or_404(id_materia, db))
# CREA MATERIA----------------------------------------------------------
@router.post("/", response_model=MateriaOut, status_code=status.HTTP_201_CREATED)
def create_materia(body: MateriaCreate, db: Session = Depends(get_db)):
    """Crea una materia. Valida que docente, auxiliar.
    docente y auxiliar son opcionales — se pueden asignar despues."""
    if body.id_docente:
        _validar_docente(body.id_docente, db)
    if body.id_auxiliar:
        _validar_auxiliar(body.id_auxiliar, db)
    # if body.id_gestion:
    #     _validar_gestion(body.id_gestion, db)
    nueva = models.Materia(
        id_materia  = uuid.uuid4(),
        sigla       = body.sigla,
        horario     = body.horario,
        anio        = body.anio,
        id_docente  = body.id_docente,
        id_auxiliar = body.id_auxiliar,
        nombre_materia = body.nombre_materia,
    )
    # id_gestion solo si el modelo ya lo tiene
    # if hasattr(nueva, "id_gestion"):
    #     nueva.id_gestion = body.id_gestion
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return _build_out(nueva)

# ACTUALIZA MATERIA----------------------------------------------
@router.patch("/{id_materia}", response_model=MateriaOut)
def update_materia(
    id_materia: UUID,
    body:       MateriaUpdate,
    db:         Session = Depends(get_db),
):
    """Actualiza parcialmente una materia."""
    materia = _get_materia_or_404(id_materia, db)

    if body.id_docente is not None:
        _validar_docente(body.id_docente, db)
        materia.id_docente = body.id_docente
    if body.id_auxiliar is not None:
        _validar_auxiliar(body.id_auxiliar, db)
        materia.id_auxiliar = body.id_auxiliar
    # if body.id_gestion is not None:
    #     _validar_gestion(body.id_gestion, db)
    #     if hasattr(materia, "id_gestion"):
    #         materia.id_gestion = body.id_gestion
    if body.sigla is not None:
        materia.sigla = body.sigla
    if body.nombre_materia is not None:
        materia.nombre_materia = body.nombre_materia
    if body.horario is not None:
        materia.horario = body.horario
    if body.anio is not None:
        materia.anio = body.anio
    db.commit()
    db.refresh(materia)
    return _build_out(materia)

@router.patch("/{id_materia}/docente", response_model=MateriaOut)
def asignar_docente(
    id_materia: UUID,
    id_docente: UUID,
    db:         Session = Depends(get_db),
):
    """ASIGNA un docente a una materia."""
    materia = _get_materia_or_404(id_materia, db)
    _validar_docente(id_docente, db)
    materia.id_docente = id_docente
    db.commit()
    db.refresh(materia)
    return _build_out(materia)
@router.delete("/{id_materia}/docente", response_model=MateriaOut)
def desasignar_docente(id_materia: UUID, db: Session = Depends(get_db)):
    """QUITA el docente asignado a una materia."""
    materia = _get_materia_or_404(id_materia, db)
    materia.id_docente = None
    db.commit()
    db.refresh(materia)
    return _build_out(materia)


@router.patch("/{id_materia}/auxiliar", response_model=MateriaOut)
def asignar_auxiliar(
    id_materia:  UUID,
    id_auxiliar: UUID,
    db:          Session = Depends(get_db),
):
    """ASIGNA un auxiliar activo a una materia."""
    materia = _get_materia_or_404(id_materia, db)
    _validar_auxiliar(id_auxiliar, db)
    materia.id_auxiliar = id_auxiliar
    db.commit()
    db.refresh(materia)
    return _build_out(materia)
@router.delete("/{id_materia}/auxiliar", status_code=status.HTTP_204_NO_CONTENT)
def desasignar_auxiliar(id_materia: UUID, db: Session = Depends(get_db)):
    """QUITA el auxiliar asignado a una materia."""
    materia = _get_materia_or_404(id_materia, db)
    materia.id_auxiliar = None
    db.commit()


@router.delete("/{id_materia}", status_code=status.HTTP_204_NO_CONTENT)
def delete_materia(id_materia: UUID, db: Session = Depends(get_db)):
    """
    Elimina una materia.
    En cascada elimina: inscripciones, parciales y notas asociadas.
    """
    materia = _get_materia_or_404(id_materia, db)
    db.delete(materia)
    db.commit()