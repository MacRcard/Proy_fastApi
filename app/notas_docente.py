import uuid
from typing import Optional

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .database import get_db
from . import models

router = APIRouter(prefix="/materias", tags=["notas"])
bearer = HTTPBearer()

SECRET_KEY = "7e19d6b108943e9602f19a86d2c08f5533dc13abe9c95bf4f628eb7cb79a4b45"
ALGORITHM  = "HS256"

def get_current_docente(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> models.Usuario:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="El token ha expirado.")
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")

    if payload.get("rol") != "docente":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso restringido a docentes.")

    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sin identificador de usuario.")

    usuario = db.query(models.Usuario).filter(
        models.Usuario.id_usuario == uuid.UUID(user_id)
    ).first()

    if not usuario:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado.")

    return usuario

###### schemas #####

class NotaInput(BaseModel):
    ci_estudiante: int
    nota: float = Field(..., ge=0)
    observacion: Optional[str] = None
class FilaResultado(BaseModel):
    ci_estudiante: int
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    estado: str   # "insertada" | "actualizada" | "omitido" | "error"
    detalle: str

class BulkNotasRequest(BaseModel):
    notas: list[NotaInput] = Field(..., min_length=1)

class BulkNotasResponse(BaseModel):
    id_materia: str
    id_parcial: str
    sigla_materia: str
    nombre_parcial: Optional[str]
    total_recibidos: int
    insertadas: int
    actualizadas: int
    omitidos: int
    errores: int
    resultados: list[FilaResultado]

# ── POST /materias/{id_materia}/parciales/{id_parcial}/notas/bulk ─────────────

@router.post(
    "/{id_materia}/parciales/{id_parcial}/notas/bulk",
    response_model=BulkNotasResponse,
    status_code=status.HTTP_200_OK,
    summary="Carga masiva de notas desde JSON",
)
def bulk_notas(
    id_materia: uuid.UUID,
    id_parcial: uuid.UUID,
    body: BulkNotasRequest,
    db: Session = Depends(get_db),
    docente_actual: models.Usuario = Depends(get_current_docente),
):
    """
    Recibe una lista de notas en JSON y las asigna a los estudiantes inscritos
    en la materia y parcial indicados.

    - Solo acepta estudiantes **inscritos** en la materia.
    - Si ya tiene nota en ese parcial → se **actualiza**.
    - Si no tiene nota → se **inserta**.
    - Si el ci_estudiante no existe o no está inscrito → **omitido**.
    - Si la nota supera la valoración máxima → **error**.

    Todo en una sola transacción. Si falla → rollback completo.
    """

    materia: models.Materia | None = db.query(models.Materia).filter(
        models.Materia.id_materia == id_materia,
        models.Materia.id_docente == docente_actual.id_usuario,
    ).first()

    if not materia:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Materia no encontrada o no tienes permiso sobre ella.",
        )

    parcial: models.Parcial | None = db.query(models.Parcial).filter(
        models.Parcial.id_parcial == id_parcial,
        models.Parcial.id_materia == id_materia,
    ).first()

    if not parcial:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parcial no encontrado para esta materia.",
        )

    cis_payload = [n.ci_estudiante for n in body.notas]

    estudiantes_bd: list[models.Estudiante] = db.query(models.Estudiante).filter(
        models.Estudiante.ci_estudiante.in_(cis_payload)
    ).all()

    por_ci: dict[int, models.Estudiante] = {e.ci_estudiante: e for e in estudiantes_bd}

    inscritos_ids: set[uuid.UUID] = {
        row.id_estudiante
        for row in db.query(models.Inscrito.id_estudiante).filter(
            models.Inscrito.id_materia == id_materia
        ).all()
    }

    notas_existentes: set[uuid.UUID] = {
        n.id_estudiante
        for n in db.query(models.Nota.id_estudiante).filter(
            models.Nota.id_parcial == id_parcial
        ).all()
    }

    a_insertar:   list[dict] = []
    a_actualizar: list[dict] = []
    resultados:   list[FilaResultado] = []

    insertadas = actualizadas = omitidos = errores = 0

    for item in body.notas:
        estudiante = por_ci.get(item.ci_estudiante)

        if not estudiante:
            resultados.append(FilaResultado(
                ci_estudiante=item.ci_estudiante,
                estado="omitido",
                detalle="Estudiante no encontrado en la base de datos.",
            ))
            omitidos += 1
            continue

        if estudiante.id_estudiante not in inscritos_ids:
            resultados.append(FilaResultado(
                ci_estudiante=item.ci_estudiante,
                nombre=estudiante.nombre,
                apellido=estudiante.apellido,
                estado="omitido",
                detalle=f"El estudiante no está inscrito en '{materia.sigla}'.",
            ))
            omitidos += 1
            continue

        if parcial.valoracion is not None and item.nota > parcial.valoracion:
            resultados.append(FilaResultado(
                ci_estudiante=item.ci_estudiante,
                nombre=estudiante.nombre,
                apellido=estudiante.apellido,
                estado="error",
                detalle=f"Nota {item.nota} supera la valoración máxima del parcial ({parcial.valoracion}).",
            ))
            errores += 1
            continue

        fila = {
            "id_estudiante": estudiante.id_estudiante,
            "id_parcial":    id_parcial,
            "nota":          item.nota,
            "observacion":   item.observacion,
        }

        if estudiante.id_estudiante in notas_existentes:
            a_actualizar.append(fila)
            actualizadas += 1
            resultados.append(FilaResultado(
                ci_estudiante=item.ci_estudiante,
                nombre=estudiante.nombre,
                apellido=estudiante.apellido,
                estado="actualizada",
                detalle="Nota actualizada correctamente.",
            ))
        else:
            a_insertar.append(fila)
            notas_existentes.add(estudiante.id_estudiante)
            insertadas += 1
            resultados.append(FilaResultado(
                ci_estudiante=item.ci_estudiante,
                nombre=estudiante.nombre,
                apellido=estudiante.apellido,
                estado="insertada",
                detalle="Nota registrada correctamente.",
            ))

    try:
        if a_insertar:
            db.execute(pg_insert(models.Nota).values(a_insertar))

        if a_actualizar:
            stmt = (
                pg_insert(models.Nota)
                .values(a_actualizar)
                .on_conflict_do_update(
                    index_elements=["id_estudiante", "id_parcial"],
                    set_={
                        "nota":        pg_insert(models.Nota).excluded.nota,
                        "observacion": pg_insert(models.Nota).excluded.observacion,
                    },
                )
            )
            db.execute(stmt)

        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar en la base de datos: {str(e)}",
        )

    return BulkNotasResponse(
        id_materia=str(id_materia),
        id_parcial=str(id_parcial),
        sigla_materia=materia.sigla,
        nombre_parcial=parcial.nombre_parcial,
        total_recibidos=len(body.notas),
        insertadas=insertadas,
        actualizadas=actualizadas,
        omitidos=omitidos,
        errores=errores,
        resultados=resultados,
    )