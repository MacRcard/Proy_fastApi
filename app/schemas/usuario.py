from pydantic import BaseModel
from typing import Literal


class UsuarioOut(BaseModel):
    id_usuario: int
    ci:         int
    nombre:     str
    apellido:   str
    rol:        str | None

    model_config = {"from_attributes": True}