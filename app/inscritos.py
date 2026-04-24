import uuid
from typing import Optional, Annotated

from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .database import get_db
from . import models

router = APIRouter(prefix="/materias", tags=["inscritos"])

SECRET_KEY = "7e19d6b108943e9602f19a86d2c08f5533dc13abe9c95bf4f628eb7cb79a4b45"

# ── Schemas ───────────────────────────────────────────────────────────────────

class EstudianteInput(BaseModel):
    ci_estudiante: int
    matricula: int
    nombre: str = Field(..., min_length=1)
    apellido: str = Field(..., min_length=1)
    anio: Optional[int] = None
    mencion: Optional[str] = None


class FilaResultado(BaseModel):
    ci_estudiante: int
    matricula: int
    nombre: str
    apellido: str
    estado: str   # "creado_e_inscrito" | "inscrito" | "ya_inscrito"
    detalle: str


class BulkInscritosRequest(BaseModel):
    estudiantes: list[EstudianteInput] = Field(..., min_length=1)


class BulkInscritosResponse(BaseModel):
    id_materia: str
    sigla_materia: str
    total_recibidos: int
    estudiantes_creados: int
    estudiantes_existentes: int
    inscripciones_nuevas: int
    ya_inscritos: int
    resultados: list[FilaResultado]

# ── POST /materias/{id_materia}/inscritos/bulk ────────────────────────────────

@router.post(
    "/{id_materia}/inscritos/bulk",
    response_model=BulkInscritosResponse,
    status_code=status.HTTP_200_OK,
    summary="Inscripción masiva de estudiantes desde JSON",
)
def bulk_inscritos(
    id_materia: uuid.UUID,
    body: BulkInscritosRequest,
    db: Session = Depends(get_db),
):
    """
    Recibe una lista de estudiantes en JSON e inscribe a todos en la materia indicada.

    - Si el estudiante **no existe** en `estudiante` → se crea y se inscribe.
    - Si el estudiante **ya existe** (por `ci_estudiante` o `matricula`) → se inscribe sin tocar sus datos.
    - Si el estudiante **ya estaba inscrito** en esa materia → se omite sin error.

    Todo ocurre en una sola transacción. Si algo falla → rollback completo.
    """

    materia: models.Materia | None = db.query(models.Materia).filter(
        models.Materia.id_materia == id_materia,
        # models.Materia.id_docente == docente_actual.id_usuario,
    ).first()

    if not materia:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Materia no encontrada o no tienes permiso sobre ella.",
        )

    cis        = [e.ci_estudiante for e in body.estudiantes]
    matriculas = [e.matricula     for e in body.estudiantes]

    existentes_bd: list[models.Estudiante] = db.query(models.Estudiante).filter(
        (models.Estudiante.ci_estudiante.in_(cis)) |
        (models.Estudiante.matricula.in_(matriculas))
    ).all()

    por_ci:  dict[int, models.Estudiante] = {e.ci_estudiante: e for e in existentes_bd}
    por_mat: dict[int, models.Estudiante] = {e.matricula:     e for e in existentes_bd}

    inscritos_actuales: set[uuid.UUID] = {
        row.id_estudiante
        for row in db.query(models.Inscrito.id_estudiante).filter(
            models.Inscrito.id_materia == id_materia
        ).all()
    }

    a_crear:     list[dict] = []
    a_inscribir: list[dict] = []
    resultados:  list[FilaResultado] = []

    creados = existentes_count = inscripciones_nuevas = ya_inscritos_count = 0

    nuevos_uuid: dict[int, uuid.UUID] = {}  # ci_estudiante → uuid

    for est in body.estudiantes:
        estudiante_bd = por_ci.get(est.ci_estudiante) or por_mat.get(est.matricula)

        if estudiante_bd:
            est_id   = estudiante_bd.id_estudiante
            es_nuevo = False
            existentes_count += 1

        elif est.ci_estudiante in nuevos_uuid:
            est_id   = nuevos_uuid[est.ci_estudiante]
            es_nuevo = False
            existentes_count += 1

        else:
            est_id = uuid.uuid4()
            nuevos_uuid[est.ci_estudiante] = est_id
            a_crear.append({
                "id_estudiante": est_id,
                "ci_estudiante": est.ci_estudiante,
                "matricula":     est.matricula,
                "nombre":        est.nombre,
                "apellido":      est.apellido,
                "anio":          est.anio,
                "mencion":       est.mencion,
            })
            es_nuevo = True
            creados += 1

        if est_id in inscritos_actuales:
            ya_inscritos_count += 1
            resultados.append(FilaResultado(
                ci_estudiante=est.ci_estudiante,
                matricula=est.matricula,
                nombre=est.nombre,
                apellido=est.apellido,
                estado="ya_inscrito",
                detalle=f"Ya estaba inscrito en '{materia.sigla}'.",
            ))
            continue

        a_inscribir.append({"id_estudiante": est_id, "id_materia": id_materia})
        inscritos_actuales.add(est_id)
        inscripciones_nuevas += 1

        resultados.append(FilaResultado(
            ci_estudiante=est.ci_estudiante,
            matricula=est.matricula,
            nombre=est.nombre,
            apellido=est.apellido,
            estado="creado_e_inscrito" if es_nuevo else "inscrito",
            detalle="Estudiante creado e inscrito." if es_nuevo else "Estudiante inscrito.",
        ))

    try:
        if a_crear:
            db.execute(pg_insert(models.Estudiante).values(a_crear))

        if a_inscribir:
            db.execute(
                pg_insert(models.Inscrito)
                .values(a_inscribir)
                .on_conflict_do_nothing()  # idempotente: ignora duplicados de PK
            )

        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar en la base de datos: {str(e)}",
        )

    return BulkInscritosResponse(
        id_materia=str(id_materia),
        sigla_materia=materia.sigla,
        total_recibidos=len(body.estudiantes),
        estudiantes_creados=creados,
        estudiantes_existentes=existentes_count,
        inscripciones_nuevas=inscripciones_nuevas,
        ya_inscritos=ya_inscritos_count,
        resultados=resultados,
    )