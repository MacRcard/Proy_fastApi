from pydantic import BaseModel
from typing import Literal


TituloEnum = Literal["licenciado", "doctor", "magister"]


class DocenteRegister(BaseModel):
    ci:       int
    nombre:   str
    apellido: str
    password: str
    titulo:   TituloEnum


class DocenteLogin(BaseModel):
    ci:       int
    password: str


class DocenteOut(BaseModel):
    id_usuario: int
    ci:         int
    nombre:     str
    apellido:   str
    titulo:     TituloEnum | None

    model_config = {"from_attributes": True}