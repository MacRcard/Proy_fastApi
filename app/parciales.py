from typing import Optional, List
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
ALGORITHM  = "HS256"

router = APIRouter(prefix="/parciales", tags=["Parciales"])
bearer = HTTPBearer()

# ── Schemas ───────────────────────────────────────────────────────────────────

class ParcialCreate(BaseModel):
    nombre_parcial: Optional[str]  = None
    fecha:          Optional[date] = None
    valoracion:     Optional[int]  = None
    # tipo solo acepta 'parcial' o 'grupal'; 'grupal' crea el contenedor padre
    tipo:           Optional[str]  = "parcial"

class ParcialHijoCreate(BaseModel):
    """Cuerpo para crear un parcial individual DENTRO de un parcial grupal."""
    nombre_parcial:    Optional[str]        = None
    fecha:             Optional[date]       = None
    valoracion:        Optional[int]        = None
    grupo_estudiantes: List[UUID]           # requerido: al menos un estudiante


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
    tipo:           Optional[str]
    parcial_grupal: Optional[UUID] = None   # UUID del padre si es hijo

    class Config:
        from_attributes = True

class ParcialGrupalOut(ParcialOut):
    """Parcial grupal padre con la lista de sus hijos."""
    hijos: List[ParcialOut] = []


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_docente_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> UUID:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

    if payload.get("rol") != "docente":
        raise HTTPException(status_code=403, detail="Acceso solo para docentes")

    return UUID(payload["sub"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_materia_del_docente(id_materia: UUID, docente_id: UUID, db: Session) -> models.Materia:
    materia = db.query(models.Materia).filter(
        models.Materia.id_materia == id_materia
    ).first()
    if materia is None:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
    if materia.id_docente != docente_id:
        raise HTTPException(status_code=403, detail="No tienes permiso sobre esta materia")
    return materia


def _validar_estudiantes_inscritos(
    id_materia: UUID,
    grupo: List[UUID],
    db: Session,
) -> None:
    """Lanza 422 si algún UUID del grupo no está inscrito en la materia."""
    ids_inscritos = {
        str(r.id_estudiante)
        for r in db.query(models.Inscrito.id_estudiante)
        .filter(models.Inscrito.id_materia == id_materia)
        .all()
    }
    for eid in grupo:
        if str(eid) not in ids_inscritos:
            raise HTTPException(
                status_code=422,
                detail=f"El estudiante {eid} no está inscrito en esta materia.",
            )


def _precrear_notas(parcial_id: UUID, grupo: List[UUID], db: Session) -> None:
    """Inserta filas vacías en `notas` para los estudiantes del grupo."""
    for eid in grupo:
        db.add(models.Nota(
            id_estudiante=eid,
            id_parcial=parcial_id,
            nota=None,
            observacion=None,
        ))


def _fmt_parcial(p: models.Parcial) -> dict:
    return {
        "id_parcial":     p.id_parcial,
        "nombre_parcial": p.nombre_parcial,
        "fecha":          p.fecha,
        "valoracion":     p.valoracion,
        "id_materia":     p.id_materia,
        "tipo":           p.tipo,
        "parcial_grupal": p.parcial_grupal,
    }


# ── GET /mis-materias ─────────────────────────────────────────────────────────

@router.get("/mis-materias")
def listar_mis_materias(
    docente_id: UUID    = Depends(get_docente_id),
    db:         Session = Depends(get_db),
):
    materias = db.query(models.Materia).filter(
        models.Materia.id_docente == docente_id
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

# ── GET /{id_materia}/estudiantes ─────────────────────────────────────────────

@router.get("/{id_materia}/estudiantes")
def listar_estudiantes_inscritos(
    id_materia: UUID,
    docente_id: UUID    = Depends(get_docente_id),
    db:         Session = Depends(get_db),
):
    """Todos los estudiantes inscritos en la materia."""
    get_materia_del_docente(id_materia, docente_id, db)

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
            "nombre_completo": e.nombre_completo,
            "anio":          e.anio,
            "mencion":       e.mencion,
        }
        for e in inscritos
    ]

# ── GET /{id_materia}/notas-resumen ───────────────────────────────────────────

@router.get("/{id_materia}/notas-resumen")
def notas_resumen_parciales(
    id_materia: UUID,
    docente_id: UUID    = Depends(get_docente_id),
    db:         Session = Depends(get_db),
):
    get_materia_del_docente(id_materia, docente_id, db)
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

# ── GET /{id_materia} — lista parciales (normales + cabeceras grupales) ────────

@router.get("/{id_materia}", response_model=list[ParcialGrupalOut])
def listar_parciales(
    id_materia: UUID,
    docente_id: UUID    = Depends(get_docente_id),
    db:         Session = Depends(get_db),
):
    """
    Devuelve:
    - Parciales normales (tipo='parcial') con parcial_grupal=NULL
    - Parciales grupales padre (tipo='grupal') con su lista de hijos embebida
    No devuelve los hijos sueltos (parcial_grupal IS NOT NULL) en el nivel raíz.
    """
    get_materia_del_docente(id_materia, docente_id, db)

    # Solo raíces: tipo 'parcial' o 'grupal' SIN padre
    raices = (
        db.query(models.Parcial)
        .filter(
            models.Parcial.id_materia     == id_materia,
            models.Parcial.tipo.in_(["parcial", "grupal"]),
            models.Parcial.parcial_grupal == None,          # noqa: E711
        )
        .all()
    )

    resultado = []
    for p in raices:
        item = _fmt_parcial(p)
        # Si es grupal, adjuntar sus hijos
        if p.tipo == "grupal":
            item["hijos"] = [_fmt_parcial(h) for h in p.hijos]
        else:
            item["hijos"] = []
        resultado.append(item)

    return resultado

# ── POST /{id_materia} — crear parcial normal O parcial grupal (padre) ─────────

@router.post("/{id_materia}", response_model=ParcialOut, status_code=status.HTTP_201_CREATED)
def crear_parcial(
    id_materia: UUID,
    body:       ParcialCreate,
    docente_id: UUID    = Depends(get_docente_id),
    db:         Session = Depends(get_db),
):
    """
    Crea un parcial normal (tipo='parcial') o un parcial grupal PADRE (tipo='grupal').

    - tipo='parcial' → comportamiento original, sin notas pre-creadas.
    - tipo='grupal'  → crea solo el contenedor padre; los hijos se crean
                       con POST /{id_materia}/grupal/{id_parcial_grupal}.
    """
    get_materia_del_docente(id_materia, docente_id, db)

    tipo = body.tipo if body.tipo in ("parcial", "grupal") else "parcial"

    nuevo = models.Parcial(
        nombre_parcial = body.nombre_parcial,
        fecha          = body.fecha,
        valoracion     = body.valoracion,
        id_materia     = id_materia,
        tipo           = tipo,
        parcial_grupal = None,   # siempre NULL: este endpoint crea raíces
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

# ── POST /{id_materia}/grupal/{id_parcial_grupal} — crear hijo dentro de grupal

@router.post(
    "/{id_materia}/grupal/{id_parcial_grupal}",
    response_model=ParcialOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_parcial_hijo(
    id_materia:        UUID,
    id_parcial_grupal: UUID,
    body:              ParcialHijoCreate,
    docente_id:        UUID    = Depends(get_docente_id),
    db:                Session = Depends(get_db),
):
    """
    Crea un parcial individual DENTRO de un parcial grupal.

    - Verifica que `id_parcial_grupal` exista, pertenezca a `id_materia`
      y sea de tipo 'grupal'.
    - Valida que todos los estudiantes en `grupo_estudiantes` estén inscritos
      en la materia.
    - Pre-crea filas en `notas` (nota=NULL) solo para los estudiantes elegidos.
      DocenteNotas detectará el campo `parcial_grupal` y cargará únicamente
      esas filas en vez de todos los inscritos.
    """
    get_materia_del_docente(id_materia, docente_id, db)

    # Verificar que el padre existe y es del tipo correcto
    padre = db.query(models.Parcial).filter(
        models.Parcial.id_parcial == id_parcial_grupal,
        models.Parcial.id_materia == id_materia,
        models.Parcial.tipo       == "grupal",
    ).first()
    if padre is None:
        raise HTTPException(
            status_code=404,
            detail="Parcial grupal padre no encontrado en esta materia.",
        )

    if not body.grupo_estudiantes:
        raise HTTPException(
            status_code=422,
            detail="Debes seleccionar al menos un estudiante para el parcial.",
        )

    _validar_estudiantes_inscritos(id_materia, body.grupo_estudiantes, db)

    hijo = models.Parcial(
        nombre_parcial = body.nombre_parcial,
        fecha          = body.fecha,
        valoracion     = body.valoracion,
        id_materia     = id_materia,
        tipo           = "parcial",        # los hijos son siempre tipo 'parcial'
        parcial_grupal = id_parcial_grupal,
    )
    db.add(hijo)
    db.flush()  # necesitamos el id antes del commit para las notas

    _precrear_notas(hijo.id_parcial, body.grupo_estudiantes, db)

    db.commit()
    db.refresh(hijo)
    return hijo


# ── GET /{id_materia}/grupal/{id_parcial_grupal} — hijos de un grupal ──────────

@router.get(
    "/{id_materia}/grupal/{id_parcial_grupal}",
    response_model=list[ParcialOut],
)
def listar_hijos_grupal(
    id_materia:        UUID,
    id_parcial_grupal: UUID,
    docente_id:        UUID    = Depends(get_docente_id),
    db:                Session = Depends(get_db),
):
    """Lista todos los parciales individuales que pertenecen a un grupal padre."""
    get_materia_del_docente(id_materia, docente_id, db)

    padre = db.query(models.Parcial).filter(
        models.Parcial.id_parcial == id_parcial_grupal,
        models.Parcial.id_materia == id_materia,
        models.Parcial.tipo       == "grupal",
    ).first()
    if padre is None:
        raise HTTPException(status_code=404, detail="Parcial grupal no encontrado.")

    return padre.hijos


# ── PUT /{id_materia}/{id_parcial} — editar (normal o hijo) ───────────────────

@router.put("/{id_materia}/{id_parcial}", response_model=ParcialOut)
def editar_parcial(
    id_materia: UUID,
    id_parcial: UUID,
    body:       ParcialUpdate,
    docente_id: UUID    = Depends(get_docente_id),
    db:         Session = Depends(get_db),
):
    """
    Edita nombre, fecha y valoración.
    Aplica tanto a parciales normales como a hijos de un grupal.
    No cambia tipo ni parcial_grupal.
    """
    get_materia_del_docente(id_materia, docente_id, db)

    parcial = db.query(models.Parcial).filter(
        models.Parcial.id_parcial == id_parcial,
        models.Parcial.id_materia == id_materia,
    ).first()
    if parcial is None:
        raise HTTPException(status_code=404, detail="Parcial no encontrado")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(parcial, field, value)

    db.commit()
    db.refresh(parcial)
    return parcial


# ── DELETE /{id_materia}/{id_parcial} ─────────────────────────────────────────

@router.delete("/{id_materia}/{id_parcial}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_parcial(
    id_materia: UUID,
    id_parcial: UUID,
    docente_id: UUID    = Depends(get_docente_id),
    db:         Session = Depends(get_db),
):
    """
    Elimina un parcial y todas sus notas en cascada.
    Si el parcial es de tipo 'grupal', el cascade del modelo también
    elimina todos sus hijos (y las notas de cada hijo).
    """
    get_materia_del_docente(id_materia, docente_id, db)

    parcial = db.query(models.Parcial).filter(
        models.Parcial.id_parcial == id_parcial,
        models.Parcial.id_materia == id_materia,
    ).first()
    if parcial is None:
        raise HTTPException(status_code=404, detail="Parcial no encontrado")

    db.delete(parcial)
    db.commit()