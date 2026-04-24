from typing import Annotated
from fastapi import APIRouter, Form, HTTPException, Depends
from sqlalchemy.orm import Session

from .database import get_db
from . import models

router = APIRouter(prefix="/estudiantes", tags=["estudiantes"])

# ── Utilidad ──────────────────────────────────────────────────────────────────

def autenticar_estudiante(ci: int, matricula: int, db: Session) -> models.Estudiante:
    estudiante = db.query(models.Estudiante).filter(
        models.Estudiante.ci_estudiante == ci,
        models.Estudiante.matricula     == matricula,
    ).first()

    if estudiante is None:
        raise HTTPException(
            status_code=404,
            detail="No se encontró ningún estudiante con ese CI y matrícula.",
        )
    return estudiante

# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/consulta/notas")
def get_notas_estudiante(
    ci:        Annotated[int, Form()],
    matricula: Annotated[int, Form()],
    db: Session = Depends(get_db),
):
    """
    Recibe el CI y la matrícula del estudiante y devuelve
    todas sus materias con todos sus parciales y notas.
    """
    estudiante = autenticar_estudiante(ci, matricula, db)

    materias_data = []

    for ins in estudiante.inscripciones:
        materia = ins.materia
        if not materia:
            continue

        parciales_data = []
        for parcial in materia.parciales:
            nota_obj = db.query(models.Nota).filter(
                models.Nota.id_parcial    == parcial.id_parcial,
                models.Nota.id_estudiante == estudiante.id_estudiante,
            ).first()

            parciales_data.append({
                "id_parcial":          str(parcial.id_parcial),
                "nombre_parcial":      parcial.nombre_parcial,
                "fecha":               parcial.fecha,
                "valoracion":          parcial.valoracion,
                "nota":                float(nota_obj.nota) if nota_obj and nota_obj.nota is not None else None,
                "observacion":         nota_obj.observacion if nota_obj else None,
                "ultima_modificacion": nota_obj.ultima_modificacion if nota_obj else None,
            })

        materias_data.append({
            "id_materia": str(materia.id_materia),
            "sigla":      materia.sigla,
            "horario":    materia.horario,
            "anio":       materia.anio,
            "parciales":  parciales_data,
        })

    return {
        "ci":        estudiante.ci_estudiante,
        "nombre":    estudiante.nombre,
        "apellido":  estudiante.apellido,
        "matricula": estudiante.matricula,
        "materias":  materias_data,
    }