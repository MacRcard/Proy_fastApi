from pydantic import BaseModel


class MateriaOut(BaseModel):
    sigla:      str
    horario:    str | None
    anio:       int | None
    id_docente: int | None

    model_config = {"from_attributes": True}