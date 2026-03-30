from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from . .database import Base


class Estudiante(Base):
    __tablename__ = "estudiante"

    id_usuario = Column(Integer, ForeignKey("usuario.id_usuario", ondelete="CASCADE"), primary_key=True)
    matricula  = Column(String(20),  unique=True, nullable=True)
    correo     = Column(String(100), unique=True, nullable=True)   # usado para login
    anio       = Column(Integer,     nullable=True)
    mencion    = Column(String(100), nullable=True)

    usuario   = relationship("Usuario",   back_populates="estudiante")
    inscritos = relationship("Inscrito",  back_populates="estudiante")