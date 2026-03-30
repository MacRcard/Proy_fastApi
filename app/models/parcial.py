from sqlalchemy import Column, Integer, String, Date
from sqlalchemy.orm import relationship
from . .database import Base


class Parcial(Base):
    __tablename__ = "parcial"

    id_parcial     = Column(Integer,      primary_key=True, autoincrement=True)
    nombre_parcial = Column(String(100),  nullable=True)
    fecha          = Column(Date,         nullable=True)
    valoracion     = Column(Integer,      nullable=True)

    inscritos = relationship("Inscrito", back_populates="parcial")