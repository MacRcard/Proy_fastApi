from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from . .database import Base


class Usuario(Base):
    __tablename__ = "usuario"

    id_usuario = Column(Integer, primary_key=True, autoincrement=True, index=True)
    rol        = Column(String(10),  nullable=True)
    ci         = Column(Integer,     unique=True, nullable=False)
    nombre     = Column(String(100), nullable=False)
    apellido   = Column(String(100), nullable=False)
    # Sin contrasenia: en el SQL vive en la tabla docente

    docente    = relationship("Docente",    back_populates="usuario", uselist=False, cascade="all, delete")
    estudiante = relationship("Estudiante", back_populates="usuario", uselist=False, cascade="all, delete")