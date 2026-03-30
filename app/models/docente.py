from sqlalchemy import Column, Integer, String, Enum, ForeignKey
from sqlalchemy.orm import relationship
from . .database import Base


class Docente(Base):
    __tablename__ = "docente"

    id_usuario  = Column(Integer, ForeignKey("usuario.id_usuario", ondelete="CASCADE"), primary_key=True)
    titulo      = Column(Enum("licenciado", "doctor", "magister"), nullable=True)
    contrasenia = Column(String(255), nullable=False)   # contraseña solo para docentes

    usuario  = relationship("Usuario",  back_populates="docente")
    materias = relationship("Materia",  back_populates="docente")