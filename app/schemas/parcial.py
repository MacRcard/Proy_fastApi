from pydantic import BaseModel, Field
from datetime import date


class ParcialCreate(BaseModel):
    nombre_parcial: str
    fecha:          date
    valoracion:     int = Field(ge=1, le=100)


class ParcialOut(BaseModel):
    id_parcial:     int
    nombre_parcial: str | None
    fecha:          date | None
    valoracion:     int | None

    model_config = {"from_attributes": True}