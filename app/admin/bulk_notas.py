import uuid
from uuid import UUID
from typing import Optional
import pandas as pd
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..database import get_db
from .. import models

router = APIRouter(prefix="/admin", tags=["Admin - Bulk"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _parse_excel(contents: bytes) -> list[dict]:
    """
    Lee el Excel esperando:
      - Columnas: NRO, CI, RU, NOMBRE_COMPLETO, NOTA, OBSERVACION
      - Los datos empiezan en la fila A7 (header en fila 6, índice 5)
    Devuelve lista de dicts con ci, matricula, nombre_completo.
    """
    df = pd.read_excel(
        BytesIO(contents),
        header=6,          # fila 6 (0-indexed → 5) como encabezado
        dtype=str,         # todo como str para evitar conversiones raras
    )

    # Normalizar nombres de columnas (quitar espacios y pasar a mayúsculas)
    df.columns = [str(c).strip().upper() for c in df.columns]

    required = {"CI", "RU", "NOMBRE_COMPLETO"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"El Excel no tiene las columnas requeridas: {missing}",
        )

    df = df[["CI", "RU", "NOMBRE_COMPLETO"]].dropna(how="all")
    df = df.dropna(subset=["CI", "RU"])           # al menos CI y RU deben existir

    result = []
    for _, row in df.iterrows():
        try:
            ci  = int(float(str(row["CI"]).strip()))
            ru  = int(float(str(row["RU"]).strip()))
        except (ValueError, TypeError):
            continue                               # fila con datos inválidos → saltar

        nombre = str(row["NOMBRE_COMPLETO"]).strip() if pd.notna(row["NOMBRE_COMPLETO"]) else ""
        result.append({"ci": ci, "matricula": ru, "nombre": nombre})

    if not result:
        raise HTTPException(status_code=422, detail="El Excel no contiene filas válidas.")

    return result


# ---------------------------------------------------------------------------
# POST /admin/estudiantes/bulk-inscripcion
# ---------------------------------------------------------------------------

@router.post("/bulk-inscripcion", status_code=200)
def bulk_inscripcion(
    id_materia: UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Flujo:
    1. Lee el Excel (pandas) → extrae CI, RU (matricula), NOMBRE_COMPLETO.
    2. Busca en BD qué estudiantes ya existen (por CI) en una sola query.
    3. Crea los que faltan en un bulk insert.
    4. Inscribe a TODOS en la materia dada (upsert: si ya existe, sobreescribe).
    Devuelve un resumen del resultado.
    """

    # ── 0. Validar que la materia existe ────────────────────────────────────
    materia = db.query(models.Materia).filter(
        models.Materia.id_materia == id_materia
    ).first()
    if not materia:
        raise HTTPException(status_code=404, detail="Materia no encontrada")

    # ── 1. Parsear Excel ────────────────────────────────────────────────────
    contents = file.file.read()
    filas = _parse_excel(contents)

    cis_excel    = [f["ci"]        for f in filas]
    ru_por_ci    = {f["ci"]: f["matricula"]    for f in filas}
    nombre_por_ci = {f["ci"]: f["nombre"]       for f in filas}

    # ── 2. Buscar existentes en una sola query ──────────────────────────────
    existentes = (
        db.query(models.Estudiante)
        .filter(models.Estudiante.ci_estudiante.in_(cis_excel))
        .all()
    )
    ci_existentes = {e.ci_estudiante for e in existentes}

    # ── 3. Crear los que faltan en bulk ─────────────────────────────────────
    nuevos_creados = 0
    nuevos_objetos: list[models.Estudiante] = []

    for f in filas:
        if f["ci"] not in ci_existentes:
            nuevo = models.Estudiante(
                id_estudiante  = uuid.uuid4(),
                ci_estudiante  = f["ci"],
                matricula      = f["matricula"],
                nombre_completo= f["nombre"],
                anio           = None,
                mencion        = materia.mencion,  # hereda la mención de la materia
            )
            nuevos_objetos.append(nuevo)
            nuevos_creados += 1

    if nuevos_objetos:
        db.bulk_save_objects(nuevos_objetos)
        db.flush()                           # necesario para obtener los UUIDs

    # ── 4. Obtener todos los UUIDs (existentes + recién creados) ────────────
    todos = (
        db.query(models.Estudiante)
        .filter(models.Estudiante.ci_estudiante.in_(cis_excel))
        .all()
    )
    uuid_list = [e.id_estudiante for e in todos]

    # ── 5. Inscribir en bulk con upsert (ON CONFLICT DO NOTHING sobreescribe
    #       si queremos; aquí usamos DO NOTHING porque la PK ya garantiza
    #       unicidad y "sobreescribir" en una tabla sin datos extra = ignorar) ─
    #
    # La tabla inscrito(id_estudiante, id_materia) no tiene columnas extra,
    # así que "sobreescribir" equivale a asegurarse de que la fila existe.
    # Usamos INSERT … ON CONFLICT DO NOTHING que es idempotente y eficiente.

    inscripcion_values = [
        {"id_estudiante": uid, "id_materia": id_materia}
        for uid in uuid_list
    ]

    stmt = pg_insert(models.Inscrito).values(inscripcion_values)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["id_estudiante", "id_materia"]
    )
    db.execute(stmt)
    db.commit()

    return {
        "mensaje":            "Bulk completado exitosamente",
        "materia":            materia.nombre_materia,
        "total_excel":        len(filas),
        "estudiantes_nuevos": nuevos_creados,
        "estudiantes_previos": len(ci_existentes),
        "total_inscritos":    len(uuid_list),
    }