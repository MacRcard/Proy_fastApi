from datetime import date
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator

# ── Docente ───────────────────────────────────────────────────────────────────

class DocenteCreate(BaseModel):
    username: str
    password: str
    titulo:   Optional[str] = None   # 'licenciado' | 'doctor' | 'magister'
    nombre:   str
    apellido: str


class DocenteUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    titulo:   Optional[str] = None
    nombre:   Optional[str] = None
    apellido: Optional[str] = None


class DocenteOut(BaseModel):
    id_usuario: UUID
    username:   str
    titulo:     Optional[str]
    nombre:     str
    apellido:   str

    class Config:
        from_attributes = True


# ── Auxiliar ──────────────────────────────────────────────────────────────────

class AuxiliarCreate(BaseModel):
    username: str
    password: str
    nombre:   str
    email:    EmailStr
    activo:   bool = True


class AuxiliarUpdate(BaseModel):
    username: Optional[str]      = None
    password: Optional[str]      = None
    nombre:   Optional[str]      = None
    email:    Optional[EmailStr] = None
    activo:   Optional[bool]     = None


class AuxiliarOut(BaseModel):
    id_usuario: UUID
    username:   str
    nombre:     str
    email:      str
    activo:     bool

    class Config:
        from_attributes = True

class AuxiliarBase(BaseModel):
    nombre: str
    email: EmailStr
    activo: bool = True


class AuxiliarCreate(AuxiliarBase):
    """
    Para crear un auxiliar se necesita también crear su usuario.
    El id_usuario debe corresponder a un usuario existente con rol='auxiliar'.
    """
    username: str
    password: str          # se hashea antes de guardar


class AuxiliarUpdate(BaseModel):
    """Todos los campos son opcionales (PATCH parcial)."""
    nombre:   Optional[str]   = None
    email:    Optional[EmailStr] = None
    activo:   Optional[bool]  = None
    password: Optional[str]   = None   # si se envía, se re-hashea


class AuxiliarOut(AuxiliarBase):
    id_usuario: UUID
    username:   str

    class Config:
        from_attributes = True

# Schema asigna materia -------------------------

class AsignarAuxiliarBody(BaseModel):
    id_auxiliar: UUID

# MATERIAS
class MateriaCreate(BaseModel):
    sigla:       str
    horario:     Optional[str]  = None
    anio:        Optional[int]  = None
    id_docente:  Optional[UUID] = None
    id_auxiliar: Optional[UUID] = None
    nombre_materia: str
    mencion:        Optional[str]  = None


class MateriaUpdate(BaseModel):
    sigla:       Optional[str]  = None
    horario:     Optional[str]  = None
    anio:        Optional[int]  = None
    id_docente:  Optional[UUID] = None
    id_auxiliar: Optional[UUID] = None
    nombre_materia:Optional[str]= None
    mencion:        Optional[str]  = None

# para asignar docente y auxiliar
class DocenteResumen(BaseModel):
    id_usuario: UUID
    nombre:     str
    apellido:   str
    titulo:     Optional[str]
class AuxiliarResumen(BaseModel):
    id_usuario: UUID
    nombre:     str
    email:      str

class MateriaOut(BaseModel):
    id_materia:  UUID
    sigla:       str
    nombre_materia: str
    horario:     Optional[str]
    anio:        Optional[int]
    mencion:        Optional[str]
    docente:     Optional[DocenteResumen]
    auxiliar:    Optional[AuxiliarResumen]
    parciales:   List[ParcialResumen]

    class Config:
        from_attributes = True

class ParcialResumen(BaseModel):
    id_parcial:     UUID
    nombre_parcial: Optional[str]
    fecha:          Optional[date]
    valoracion:     Optional[int]
    tipo:           Optional[str]
    parcial_grupal: Optional[UUID] = None
    hijos:          List["ParcialResumen"] = []

    class Config:
        from_attributes = True

ParcialResumen.model_rebuild() 

# schemas ESTUDIANTE --------------------------
class EstudianteBase(BaseModel):
    ci_estudiante:  Optional[int]
    matricula:      Optional[int]
    nombre_completo: str
    anio:           int
    mencion:        str

class EstudianteCreate(BaseModel):
    ci_estudiante: int
    matricula:     int
    nombre_completo: str
    anio:          Optional[int] = None
    mencion:       Optional[str] = None

    @field_validator("nombre_completo")
    @classmethod
    def no_vacio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("No puede estar vacío")
        return v.strip()

    @field_validator("ci_estudiante", "matricula")
    @classmethod
    def positivo(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Debe ser un número positivo")
        return v


class EstudianteUpdate(BaseModel):
    ci_estudiante: Optional[int]  = None
    matricula:     Optional[int]  = None
    nombre_completo: Optional[str]  = None
    anio:          Optional[int]  = None
    mencion:       Optional[str]  = None

    @field_validator("nombre_completo", mode="before")
    @classmethod
    def no_vacio(cls, v):
        if v is not None and not str(v).strip():
            raise ValueError("No puede estar vacío")
        return v.strip() if v else v

    @field_validator("ci_estudiante", "matricula", mode="before")
    @classmethod
    def positivo(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Debe ser un número positivo")
        return v


class EstudianteOut(BaseModel):
    id_estudiante: UUID
    ci_estudiante: int
    matricula:     int
    nombre_completo: str
    anio:          Optional[int]
    mencion:       Optional[str]

    model_config = {"from_attributes": True}