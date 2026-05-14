from typing import Optional
from uuid import UUID
from datetime import date
 
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
import jwt
from jwt.exceptions import DecodeError, ExpiredSignatureError
InvalidTokenError = DecodeError
 
from .database import get_db
from . import models
 
SECRET_KEY = "7e19d6b108943e9602f19a86d2c08f5533dc13abe9c95bf4f628eb7cb79a4b45"


def _nombre_mencion(mencion_uuid, db) -> str | None:
    if not mencion_uuid:
        return None
    try:
        from uuid import UUID as _UUID
        uid = _UUID(str(mencion_uuid))
    except ValueError:
        return str(mencion_uuid)
    obj = db.query(models.Mencion).filter(models.Mencion.id_mencion == uid).first()
    return obj.nombre if obj else str(mencion_uuid)
ALGORITHM  = "HS256"
 
router  = APIRouter(prefix="/practicas", tags=["Practicas"])
bearer  = HTTPBearer()
 
 
##### schemas ###
 
class ParcialCreate(BaseModel):
    nombre_parcial: Optional[str]  = None
    fecha:          Optional[date] = None
    valoracion:     Optional[int]  = None

class ParcialUpdate(BaseModel):
    nombre_parcial: Optional[str]  = None
    fecha:          Optional[date] = None
    valoracion:     Optional[int]  = None
 
class ParcialOut(BaseModel):
    id_parcial:     UUID
    nombre_parcial: Optional[str]
    fecha:          Optional[date]
    valoracion:     Optional[int]
    id_materia:     Optional[UUID]
 
    class Config:
        from_attributes = True
 
 
# ── Dependencia: extraer docente del token ────────────────────────────────────
 
def get_auxiliar_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> UUID:
    """Devuelve el id_usuario (UUID) del docente autenticado.
    Lanza 401 si el token es inválido, expirado o el rol no es 'auxiliar'.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
 
    if payload.get("rol") != "auxiliar":
        raise HTTPException(status_code=403, detail="Acceso solo para auxiliares")
 
    return UUID(payload["sub"])
 
 
# ── Helper: verificar que la materia pertenece al docente ─────────────────────
 
def get_materia_del_auxiliar(
    id_materia: UUID,
    auxiliar_id: UUID,
    db: Session,
) -> models.Materia:
    """
    Retorna la materia si existe y le pertenece al docente.
    Lanza 404 o 403 según corresponda.
    """
    materia = db.query(models.Materia).filter(
        models.Materia.id_materia == id_materia
    ).first()
 
    if materia is None:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
 
    if materia.id_auxiliar != auxiliar_id:
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso sobre esta materia",
        )
 
    return materia
 
###### Materias por auxiliar #####
 
@router.get("/mis-materias")
def listar_mis_materias(
    auxiliar_id: UUID = Depends(get_auxiliar_id),
    db: Session     = Depends(get_db),
):
    materias = db.query(models.Materia).filter(
        models.Materia.id_auxiliar == auxiliar_id
    ).all()
    return [
        {
            "id_materia": m.id_materia,
            "sigla":      m.sigla,
            "horario":    m.horario,
            "anio":       m.anio,
        }
        for m in materias
    ]

@router.get("/{id_materia}/notas-resumen")
def notas_resumen_practicas(
    id_materia: UUID,
    docente_id: UUID = Depends(get_auxiliar_id),
    db: Session      = Depends(get_db),
):
    get_materia_del_auxiliar(id_materia, docente_id, db)
    # { id_estudiante: { id_parcial: nota } }
    notas = (
        db.query(models.Nota)
        .join(models.Parcial, models.Parcial.id_parcial == models.Nota.id_parcial)
        .filter(models.Parcial.id_materia == id_materia)
        .all()
    )
    resultado = {}
    for n in notas:
        eid = str(n.id_estudiante)
        if eid not in resultado:
            resultado[eid] = {}
        resultado[eid][str(n.id_parcial)] = float(n.nota) if n.nota is not None else None
    return resultado
# ── GET /parciales/{id_materia}/estudiantes 

@router.get("/{id_materia}/estudiantes")
def listar_estudiantes_inscritos(
    id_materia: UUID,
    auxiliar_id: UUID = Depends(get_auxiliar_id),
    db: Session      = Depends(get_db),
):
    """Devuelve todos los estudiantes inscritos en una materia del docente."""
    get_materia_del_auxiliar(id_materia, auxiliar_id, db)

    inscritos = (
        db.query(models.Estudiante)
        .join(models.Inscrito, models.Inscrito.id_estudiante == models.Estudiante.id_estudiante)
        .filter(models.Inscrito.id_materia == id_materia)
        .all()
    )
    return [
        {
            "id_estudiante": e.id_estudiante,
            "ci_estudiante": e.ci_estudiante,
            "matricula":     e.matricula,
            "nombre":        e.nombre,
            "apellido":      e.apellido,
            "anio":          e.anio,
            "mencion":       _nombre_mencion(e.mencion, db),
        }
        for e in inscritos
    ]

@router.get("/{id_materia}/notas-resumen")
def notas_resumen(
    id_materia:  UUID,
    auxiliar_id: UUID    = Depends(get_auxiliar_id),
    db:          Session = Depends(get_db),
):
    """Mapa { id_estudiante: { id_parcial: nota } } para prácticas de la materia."""
    get_materia_del_auxiliar(id_materia, auxiliar_id, db)
    notas = (
        db.query(models.Nota)
        .join(models.Parcial, models.Parcial.id_parcial == models.Nota.id_parcial)
        .filter(
            models.Parcial.id_materia == id_materia,
            models.Parcial.tipo       == "practica",
        )
        .all()
    )
    resultado = {}
    for n in notas:
        eid = str(n.id_estudiante)
        if eid not in resultado:
            resultado[eid] = {}
        resultado[eid][str(n.id_parcial)] = float(n.nota) if n.nota is not None else None
    return resultado


# ── GET /parciales/{id_materia} ───────────────────────────────────────────────
 
@router.get("/{id_materia}", response_model=list[ParcialOut])
def listar_parciales(
    id_materia: UUID,
    auxiliar_id: UUID    = Depends(get_auxiliar_id),
    db: Session         = Depends(get_db),
):
    """Lista todos los parciales de una materia que pertenece al docente."""
    get_materia_del_auxiliar(id_materia, auxiliar_id, db)
 
    parciales = db.query(models.Parcial).filter(
        models.Parcial.id_materia == id_materia,
        models.Parcial.tipo       == "practica",
    ).all()
    return parciales
 
# ── POST /parciales/{id_materia} ──────────────────────────────────────────────
 
@router.post("/{id_materia}", response_model=ParcialOut, status_code=status.HTTP_201_CREATED)
def crear_parcial(
    id_materia: UUID,
    body:       ParcialCreate,
    auxiliar_id: UUID    = Depends(get_auxiliar_id),
    db: Session         = Depends(get_db),
):
    """Crea un nuevo parcial en una materia del docente."""
    get_materia_del_auxiliar(id_materia, auxiliar_id, db)
 
    nuevo = models.Parcial(
        nombre_parcial = body.nombre_parcial,
        fecha          = body.fecha,
        valoracion     = body.valoracion,
        id_materia     = id_materia,
        tipo           = "practica",   # auxiliares solo crean prácticas
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo
 
# ── PUT /parciales/{id_materia}/{id_parcial} ──────────────────────────────────
 
@router.put("/{id_materia}/{id_parcial}", response_model=ParcialOut)
def editar_parcial(
    id_materia: UUID,
    id_parcial: UUID,
    body:       ParcialUpdate,
    auxiliar_id: UUID    = Depends(get_auxiliar_id),
    db: Session         = Depends(get_db),
):
    """Edita un parcial existente. Solo actualiza los campos enviados."""
    get_materia_del_auxiliar(id_materia, auxiliar_id, db)
 
    parcial = db.query(models.Parcial).filter(
        models.Parcial.id_parcial  == id_parcial,
        models.Parcial.id_materia  == id_materia,
    ).first()

    if parcial is None:
        raise HTTPException(status_code=404, detail="Práctica no encontrada")

    # Restricción 10 días para auxiliares
    if parcial.fecha:
        from datetime import date as _date
        dias = (_date.today() - parcial.fecha).days
        if dias > 10:
            raise HTTPException(
                status_code=403,
                detail=f"Solo se pueden editar prácticas dentro de los 10 días siguientes. Han pasado {dias} días.",
            )

    # Actualiza solo los campos que vienen en el body (partial update)
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(parcial, field, value)
 
    db.commit()
    db.refresh(parcial)
    return parcial
 
 
# ── DELETE /parciales/{id_materia}/{id_parcial} ───────────────────────────────
 
@router.delete("/{id_materia}/{id_parcial}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_parcial(
    id_materia: UUID,
    id_parcial: UUID,
    auxiliar_id: UUID    = Depends(get_auxiliar_id),
    db: Session         = Depends(get_db),
):
    """Elimina un parcial (y sus notas en cascada) de una materia del docente."""
    get_materia_del_auxiliar(id_materia, auxiliar_id, db)
 
    parcial = db.query(models.Parcial).filter(
        models.Parcial.id_parcial == id_parcial,
        models.Parcial.id_materia == id_materia,
    ).first()
 
    if parcial is None:
        raise HTTPException(status_code=404, detail="Parcial no encontrado")
 
    db.delete(parcial)
    db.commit()