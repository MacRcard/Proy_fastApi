from sqlalchemy import Column, Integer, String, Enum
from .database import Base

class Usuario(Base):
    __tablename__ = "USUARIO"

    id_usuario = Column(Integer, primary_key=True, index=True)
    ci = Column(String(20), unique=True, nullable=False)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    rol = Column(Enum('docente', 'estudiante', 'admin'), nullable=False)
    contrasenia = Column(String(255), nullable=False)