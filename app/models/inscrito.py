from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from . .database import Base


class Inscrito(Base):
    __tablename__ = "inscrito"

    # PK compuesta igual que en el SQL
    id_estudiante       = Column(Integer,    ForeignKey("estudiante.id_usuario"), primary_key=True)
    sigla_materia       = Column(String(20), ForeignKey("materia.sigla"),         primary_key=True)
    id_parcial          = Column(Integer,    ForeignKey("parcial.id_parcial"),    primary_key=True)
    nota                = Column(Numeric(5, 2), nullable=True)
    observacion         = Column(Text,          nullable=True)
    ultima_modificacion = Column(DateTime, server_default=func.now(), onupdate=func.now())

    estudiante = relationship("Estudiante", back_populates="inscritos")
    materia    = relationship("Materia",    back_populates="inscritos")
    parcial    = relationship("Parcial",    back_populates="inscritos")