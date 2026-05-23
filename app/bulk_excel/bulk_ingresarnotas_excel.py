from uuid import UUID
from typing import Optional
import pandas as pd
from io import BytesIO

import jwt
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..database import get_db
from .. import models

router = APIRouter(prefix="/docente", tags=["Docente - Bulk Notas"])

# ── Auth (mismo SECRET_KEY y ALGORITHM que main.py) ──────────────────────────

SECRET_KEY = "7e19d6b108943e9602f19a86d2c08f5533dc13abe9c95bf4f628eb7cb79a4b45"
ALGORITHM  = "HS256"


def _get_docente_actual(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: Session = Depends(get_db),
) -> models.Docente:
    """
    Decodifica el JWT, verifica que el usuario exista y tenga rol='docente'.
    Devuelve el objeto Docente o lanza 401/403.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token inválido")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

    usuario = db.query(models.Usuario).filter(
        models.Usuario.id_usuario == user_id
    ).first()
    if usuario is None:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    if usuario.rol != "docente":
        raise HTTPException(
            status_code=403,
            detail="Acceso solo para docentes",
        )

    docente = db.query(models.Docente).filter(
        models.Docente.id_usuario == usuario.id_usuario
    ).first()
    if docente is None:
        raise HTTPException(status_code=404, detail="Perfil de docente no encontrado")

    return docente


# ── Parser Excel ──────────────────────────────────────────────────────────────

def _parse_excel_notas(contents: bytes) -> list[dict]:
    """
    Lee el Excel con formato plantilla pa-105:
      - Header en fila 7 del Excel (índice 6 base-0).
      - Columnas esperadas: NRO, RU, CI, NOMBRE_COMPLETO, NOTA, OBSERVACION.
      - NRO se ignora.
    Devuelve lista de dicts: ci, matricula, nombre_completo, nota, observacion.
    """
    df = pd.read_excel(BytesIO(contents), header=6, dtype=str)
    df.columns = [str(c).strip().upper() for c in df.columns]

    required = {"CI", "RU", "NOMBRE_COMPLETO"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"El Excel no tiene las columnas requeridas: {missing}",
        )

    if "NOTA" not in df.columns:
        df["NOTA"] = None
    if "OBSERVACION" not in df.columns:
        df["OBSERVACION"] = None

    df = df[["CI", "RU", "NOMBRE_COMPLETO", "NOTA", "OBSERVACION"]]
    df = df.dropna(subset=["CI", "RU"], how="any")
    df = df[df["CI"].str.strip() != ""]

    result = []
    for _, row in df.iterrows():
        try:
            ci = int(float(str(row["CI"]).strip()))
            ru = int(float(str(row["RU"]).strip()))
        except (ValueError, TypeError):
            continue

        nota: Optional[float] = None
        raw_nota = str(row["NOTA"]).strip() if pd.notna(row["NOTA"]) else ""
        if raw_nota and raw_nota.lower() not in ("none", "nan", ""):
            try:
                nota = float(raw_nota)
            except ValueError:
                nota = None

        observacion: Optional[str] = None
        raw_obs = str(row["OBSERVACION"]).strip() if pd.notna(row["OBSERVACION"]) else ""
        if raw_obs and raw_obs.lower() not in ("none", "nan", ""):
            observacion = raw_obs

        nombre = (
            str(row["NOMBRE_COMPLETO"]).strip()
            if pd.notna(row["NOMBRE_COMPLETO"])
            else ""
        )

        result.append({
            "ci":              ci,
            "matricula":       ru,
            "nombre_completo": nombre,
            "nota":            nota,
            "observacion":     observacion,
        })

    if not result:
        raise HTTPException(
            status_code=422, detail="El Excel no contiene filas válidas."
        )

    return result


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/bulk-notas", status_code=200)
def bulk_notas_docente(
    id_parcial: UUID    = Form(...),
    file:       UploadFile = File(...),
    db:         Session    = Depends(get_db),
    docente:    models.Docente = Depends(_get_docente_actual),
):
    """
    Carga masiva de notas desde un Excel (formato plantilla pa-105).
    Solo accesible con token de rol='docente'.

    Flujo:
    1. Verifica que el parcial exista y pertenezca a una materia del docente.
    2. Parsea el Excel → RU, CI, NOMBRE_COMPLETO, NOTA, OBSERVACION.
    3. Busca cada estudiante por CI.
    4. Verifica inscripción en la materia; si no está inscrito → advertencia y omite.
    5. Valida que la nota no supere la valoración del parcial.
    6. Upsert masivo en tabla `notas`.
    7. Devuelve resumen + lista de advertencias.
    """

    # ── 1. Validar parcial y propiedad del docente ───────────────────────────
    parcial = db.query(models.Parcial).filter(
        models.Parcial.id_parcial == id_parcial
    ).first()
    if not parcial:
        raise HTTPException(status_code=404, detail="Parcial no encontrado")

    materia = db.query(models.Materia).filter(
        models.Materia.id_materia == parcial.id_materia
    ).first()
    if not materia:
        raise HTTPException(status_code=404, detail="Materia del parcial no encontrada")

    if materia.id_docente != docente.id_usuario:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso sobre este parcial: no es de tu materia",
        )

    id_materia = materia.id_materia

    # ── 2. Parsear Excel ─────────────────────────────────────────────────────
    filas = _parse_excel_notas(file.file.read())
    cis_excel = [f["ci"] for f in filas]

    # ── 3. Buscar estudiantes por CI (una sola query) ────────────────────────
    estudiantes_bd = (
        db.query(models.Estudiante)
        .filter(models.Estudiante.ci_estudiante.in_(cis_excel))
        .all()
    )
    est_por_ci: dict[int, models.Estudiante] = {
        e.ci_estudiante: e for e in estudiantes_bd
    }

    # ── 4. Obtener IDs inscritos en la materia (una sola query) ─────────────
    ids_inscritos: set[UUID] = {
        row.id_estudiante
        for row in db.query(models.Inscrito.id_estudiante).filter(
            models.Inscrito.id_materia == id_materia
        ).all()
    }

    # ── 5. Clasificar filas ──────────────────────────────────────────────────
    no_encontrados: list[str] = []
    no_inscritos:   list[str] = []
    nota_invalida:  list[str] = []
    sin_nota:       int       = 0
    valores_upsert: list[dict] = []

    for fila in filas:
        ci     = fila["ci"]
        nombre = fila["nombre_completo"] or f"CI {ci}"
        nota   = fila["nota"]
        obs    = fila["observacion"]

        # Estudiante no existe en el sistema
        estudiante = est_por_ci.get(ci)
        if estudiante is None:
            no_encontrados.append(f"{nombre} (CI: {ci})")
            continue

        # Existe pero no está inscrito en esta materia
        if estudiante.id_estudiante not in ids_inscritos:
            no_inscritos.append(f"{nombre} (CI: {ci})")
            continue

        # Nota supera la valoración máxima del parcial
        if nota is not None and parcial.valoracion is not None:
            if nota > parcial.valoracion:
                nota_invalida.append(
                    f"{nombre} (CI: {ci}) — nota {nota} supera "
                    f"la valoración máxima {parcial.valoracion}"
                )
                continue

        # Fila sin nota ni observación → nada que persistir
        if nota is None and obs is None:
            sin_nota += 1
            continue

        valores_upsert.append({
            "id_estudiante": estudiante.id_estudiante,
            "id_parcial":    id_parcial,
            "nota":          nota,
            "observacion":   obs,
        })

    # ── 6. Upsert masivo ─────────────────────────────────────────────────────
    registradas = 0
    if valores_upsert:
        stmt = pg_insert(models.Nota).values(valores_upsert)
        stmt = stmt.on_conflict_do_update(
            index_elements=["id_estudiante", "id_parcial"],
            set_={
                "nota":                stmt.excluded.nota,
                "observacion":         stmt.excluded.observacion,
                "ultima_modificacion": sa_func.current_timestamp(),
            },
        )
        db.execute(stmt)
        db.commit()
        registradas = len(valores_upsert)

    # ── 7. Respuesta ─────────────────────────────────────────────────────────
    advertencias: list[str] = []
    for msg in no_encontrados:
        advertencias.append(f"No existe en el sistema: {msg}")
    for msg in no_inscritos:
        advertencias.append(f"No está inscrito en la materia: {msg}")
    for msg in nota_invalida:
        advertencias.append(f"Nota inválida (omitido): {msg}")

    return {
        "mensaje":           "Bulk de notas completado",
        "docente":           f"{docente.nombre_docente} {docente.apellido_docente}",
        "materia":           materia.nombre_materia,
        "parcial":           parcial.nombre_parcial,
        "total_excel":       len(filas),
        "notas_registradas": registradas,
        "sin_nota_en_excel": sin_nota,
        "omitidos":          len(no_encontrados) + len(no_inscritos) + len(nota_invalida),
        "advertencias":      advertencias,
    }