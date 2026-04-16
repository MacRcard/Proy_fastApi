from typing import Annotated
from fastapi import APIRouter, Form, HTTPException, Depends
from sqlalchemy.orm import Session

from .database import get_db
from . import models

router = APIRouter(prefix="/estudiantes", tags=["estudiantes"])


# ── Utilidad ──────────────────────────────────────────────────────────────────

def autenticar_estudiante(ci: str, db: Session) -> models.Estudiante:
    """Verifica que el CI pertenezca a un estudiante registrado."""
    usuario = db.query(models.Usuario).filter(
        models.Usuario.ci  == ci,
        models.Usuario.rol == "estudiante",
    ).first()
    if usuario is None or usuario.estudiante is None:
        raise HTTPException(status_code=404, detail="No se encontró ningún estudiante con ese CI")
    return usuario.estudiante


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/consulta/materias")
def get_materias_por_ci(
    ci: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    """
    Recibe un CI, verifica que sea estudiante
    y devuelve las materias en las que está inscrito.
    """
    estudiante = autenticar_estudiante(ci, db)

    materias = [
        {
            "sigla":   ins.materia.sigla,
            "horario": ins.materia.horario,
            "anio":    ins.materia.anio,
        }
        for ins in estudiante.inscrito
        if ins.materia
    ]

    return {
        "ci":        str(estudiante.usuario.ci),
        "nombre":    estudiante.usuario.nombre,
        "apellido":  estudiante.usuario.apellido,
        "matricula": estudiante.matricula,
        "materias":  materias,
    }


@router.post("/consulta/materia/{sigla}")
def get_parciales_materia(
    sigla: str,
    ci:    Annotated[str, Form()],
    db:    Session = Depends(get_db),
):
    """
    Recibe el CI y la sigla de la materia. Verifica que el CI sea de un
    estudiante inscrito en esa materia y devuelve sus parciales con notas.
    """
    estudiante = autenticar_estudiante(ci, db)

    inscrito = db.query(models.Inscrito).filter(
        models.Inscrito.id_estudiante == estudiante.id_usuario,
        models.Inscrito.sigla_materia == sigla,
    ).first()
    if inscrito is None:
        raise HTTPException(status_code=403, detail="No estás inscrito en esta materia")

    materia = inscrito.materia

    parciales_data = []
    for parcial in materia.parciales:
        nota_obj = db.query(models.Notas).filter(
            models.Notas.id_parcial    == parcial.id_parcial,
            models.Notas.id_estudiante == estudiante.id_usuario,
        ).first()
        parciales_data.append({
            "id_parcial":          parcial.id_parcial,
            "nombre_parcial":      parcial.nombre_parcial,
            "fecha":               parcial.fecha,
            "valoracion":          parcial.valoracion,
            "nota":                float(nota_obj.nota) if nota_obj and nota_obj.nota is not None else None,
            "observacion":         nota_obj.observacion if nota_obj else None,
            "ultima_modificacion": nota_obj.ultima_modificacion if nota_obj else None,
        })

    return {
        "ci":        str(estudiante.usuario.ci),
        "nombre":    estudiante.usuario.nombre,
        "apellido":  estudiante.usuario.apellido,
        "sigla":     materia.sigla,
        "horario":   materia.horario,
        "anio":      materia.anio,
        "parciales": parciales_data,
    }