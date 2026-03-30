from pydantic import BaseModel, EmailStr


class EstudianteRegister(BaseModel):
    ci:        int
    nombre:    str
    apellido:  str
    matricula: str
    correo:    EmailStr
    anio:      int | None = None
    mencion:   str | None = None


class EstudianteLogin(BaseModel):
    ci:     int
    correo: EmailStr


class EstudianteOut(BaseModel):
    id_usuario: int
    ci:         int
    nombre:     str
    apellido:   str
    matricula:  str | None
    correo:     str | None
    anio:       int | None
    mencion:    str | None

    model_config = {"from_attributes": True}