from pydantic import BaseModel
from datetime import date, datetime
from decimal import Decimal


# ── Realiza ────────────────────────────────────────────────
class NotaBase(BaseModel):
    nota:       Decimal | None = None
    observacion: str | None   = None

class NotaOut(NotaBase):
    id_estudiante:       int
    id_parcial:          int
    ultima_modificacion: datetime | None = None

    class Config:
        from_attributes = True


# ── Parcial ────────────────────────────────────────────────
class ParcialBase(BaseModel):
    nombre_parcial: str | None  = None
    fecha:          date | None = None
    valoracion:     int | None  = None
    sigla_materia:  str | None  = None

class ParcialCreate(ParcialBase):
    pass

class ParcialOut(ParcialBase):
    id_parcial: int
    nota:    list[NotaOut] = []

    class Config:
        from_attributes = True


# ── Materia ────────────────────────────────────────────────
class MateriaBase(BaseModel):
    sigla:      str
    horario:    str | None = None
    anio:       int | None = None
    id_docente: int | None = None

class MateriaCreate(MateriaBase):
    pass

class MateriaOut(MateriaBase):
    parciales: list[ParcialOut] = []

    class Config:
        from_attributes = True


# ── Docente ────────────────────────────────────────────────
class DocenteBase(BaseModel):
    titulo: str | None = None

class DocenteOut(DocenteBase):
    materias: list[MateriaOut] = []

    class Config:
        from_attributes = True


# ── Estudiante ─────────────────────────────────────────────
class EstudianteBase(BaseModel):
    matricula: str | None = None
    correo:    str | None = None
    anio:      int | None = None
    mencion:   str | None = None

class EstudianteOut(EstudianteBase):
    nota: list[NotaOut] = []

    class Config:
        from_attributes = True


# ── Usuario ────────────────────────────────────────────────
class UsuarioBase(BaseModel):
    ci:       int
    nombre:   str
    apellido: str
    rol:      str

class UsuarioCreate(UsuarioBase):
    pass

class UsuarioOut(UsuarioBase):
    id_usuario: int
    docente:    DocenteOut    | None = None
    estudiante: EstudianteOut | None = None

    class Config:
        from_attributes = True


# ── Registro ───────────────────────────────────────────────
class RegistroDocenteCreate(BaseModel):
    ci:       int
    nombre:   str
    apellido: str
    password: str
    titulo:   str

class RegistroEstudianteCreate(BaseModel):
    ci:        int
    nombre:    str
    apellido:  str
    matricula: str
    correo:    str
    anio:      int | None = None
    mencion:   str | None = None


# ── Login ──────────────────────────────────────────────────
class LoginDocente(BaseModel):
    ci:       int
    password: str

class LoginEstudiante(BaseModel):
    ci:     int
    correo: str


# ── Token ──────────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type:   str