from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr

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

# Schema asigna materia -------------------------

class AsignarAuxiliarBody(BaseModel):
    id_auxiliar: UUID