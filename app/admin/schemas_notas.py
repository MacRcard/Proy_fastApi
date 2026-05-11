from datetime import date
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator

# gestion de parciales y notas, DOCENTE
class ParcialCreate(BaseModel):
    nombre_parcial: str
    fecha:          Optional[date] = None
    valoracion:     Optional[int]  = None
    id_materia:     UUID

    @field_validator("nombre_parcial")
    @classmethod
    def no_vacio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El nombre del parcial no puede estar vacío")
        return v.strip()

    @field_validator("valoracion")
    @classmethod
    def valoracion_positiva(cls, v):
        if v is not None and v <= 0:
            raise ValueError("La valoración debe ser positiva")
        return v


class ParcialUpdate(BaseModel):
    nombre_parcial: Optional[str]  = None
    fecha:          Optional[date] = None
    valoracion:     Optional[int]  = None

    @field_validator("nombre_parcial")
    @classmethod
    def no_vacio(cls, v):
        if v is not None and not v.strip():
            raise ValueError("El nombre no puede estar vacío")
        return v.strip() if v else v

    @field_validator("valoracion")
    @classmethod
    def valoracion_positiva(cls, v):
        if v is not None and v <= 0:
            raise ValueError("La valoración debe ser positiva")
        return v


class NotaUpdate(BaseModel):
    nota:        Optional[float] = None
    observacion: Optional[str]  = None

    @field_validator("nota")
    @classmethod
    def nota_valida(cls, v):
        if v is not None and v < 0:
            raise ValueError("La nota no puede ser negativa")
        return v
    
# schemas estudiante_Notas 
class NotaDetalleOut(BaseModel):
    nota: Optional[float] = None
    observacion: Optional[str] = None

class ParcialConNotaOut(BaseModel):
    id_parcial: UUID
    nombre_parcial: Optional[str]
    fecha: Optional[date]
    tipo: Optional[str]
    valoracion: Optional[int]
    # Aquí anidamos la nota específica del estudiante para este parcial
    nota_detalle: Optional[NotaDetalleOut] = None

class MateriaConEvaluacionesOut(BaseModel):
    id_materia: UUID
    sigla: str
    nombre_materia: str
    parciales: List[ParcialConNotaOut]

class PerfilEstudianteCompletoOut(BaseModel):
    id_estudiante: UUID
    nombre: str
    apellido: str
    matricula: int
    mencion: Optional[UUID]
    materias: List[MateriaConEvaluacionesOut]

    class Config:
        from_attributes = True