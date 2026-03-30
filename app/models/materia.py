from sqlalchemy import Column, Integer, String, Enum, ForeignKey
from sqlalchemy.orm import relationship
from . .database import Base


class Aula(Base):
    __tablename__ = "aula"

    cod_aula = Column(String(20), primary_key=True)
    tipo     = Column(Enum("laboratorio", "salon", "auditorio"), nullable=False)

    asignaciones = relationship("AsignacionAula", back_populates="aula")


class Materia(Base):
    __tablename__ = "materia"

    sigla      = Column(String(20), primary_key=True)
    horario    = Column(String(50), nullable=True)
    anio       = Column(Integer,    nullable=True)
    id_docente = Column(Integer, ForeignKey("docente.id_usuario"), nullable=True)

    docente      = relationship("Docente",       back_populates="materias")
    inscritos    = relationship("Inscrito",       back_populates="materia")
    asignaciones = relationship("AsignacionAula", back_populates="materia")


class AsignacionAula(Base):
    __tablename__ = "asignacion_aula"

    cod_aula      = Column(String(20), ForeignKey("aula.cod_aula"),  primary_key=True)
    sigla_materia = Column(String(20), ForeignKey("materia.sigla"),  primary_key=True)

    aula    = relationship("Aula",    back_populates="asignaciones")
    materia = relationship("Materia", back_populates="asignaciones")