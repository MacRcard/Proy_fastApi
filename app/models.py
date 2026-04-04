from sqlalchemy import Column, Integer, String, Enum, Numeric, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class Usuario(Base):
    __tablename__ = "usuario"

    id_usuario = Column(Integer, primary_key=True, autoincrement=True)
    ci         = Column(Integer, unique=True, nullable=False)
    nombre     = Column(String(100), nullable=False)
    apellido   = Column(String(100), nullable=False)
    rol        = Column(Enum("docente", "estudiante"))

    docente    = relationship("Docente",    back_populates="usuario", uselist=False, cascade="all, delete")
    estudiante = relationship("Estudiante", back_populates="usuario", uselist=False, cascade="all, delete")


class Docente(Base):
    __tablename__ = "docente"

    id_usuario  = Column(Integer, ForeignKey("usuario.id_usuario", ondelete="CASCADE"), primary_key=True)
    titulo      = Column(Enum("licenciado", "doctor", "magister"))
    contrasenia = Column(String(255), nullable=False)

    usuario  = relationship("Usuario", back_populates="docente")
    materias = relationship("Materia", back_populates="docente")


class Estudiante(Base):
    __tablename__ = "estudiante"

    id_usuario = Column(Integer, ForeignKey("usuario.id_usuario", ondelete="CASCADE"), primary_key=True)
    matricula  = Column(String(20),  unique=True)
    correo     = Column(String(100), unique=True)
    anio       = Column(Integer)
    mencion    = Column(String(100))

    usuario    = relationship("Usuario",   back_populates="estudiante")
    inscrito   = relationship("Inscrito",  back_populates="estudiante")
    notas      = relationship("Notas",     back_populates="estudiante")


class Materia(Base):
    __tablename__ = "materia"

    sigla      = Column(String(20), primary_key=True)
    horario    = Column(String(50))
    anio       = Column(Integer)
    id_docente = Column(Integer, ForeignKey("docente.id_usuario"))

    docente   = relationship("Docente",   back_populates="materias")
    parciales = relationship("Parcial",   back_populates="materia", cascade="all, delete")
    inscritos = relationship("Inscrito",  back_populates="materia")


class Inscrito(Base):
    __tablename__ = "inscrito"

    id_estudiante = Column(Integer, ForeignKey("estudiante.id_usuario"), primary_key=True)
    sigla_materia = Column(String(20), ForeignKey("materia.sigla"),      primary_key=True)

    estudiante = relationship("Estudiante", back_populates="inscrito")
    materia    = relationship("Materia",    back_populates="inscritos")


class Parcial(Base):
    __tablename__ = "parcial"

    id_parcial     = Column(Integer, primary_key=True, autoincrement=True)
    nombre_parcial = Column(String(100))
    fecha          = Column(Date)
    valoracion     = Column(Integer)
    sigla_materia  = Column(String(20), ForeignKey("materia.sigla", ondelete="CASCADE"))

    materia = relationship("Materia", back_populates="parciales")
    notas   = relationship("Notas",   back_populates="parcial", cascade="all, delete")


class Notas(Base):
    __tablename__ = "notas"

    id_estudiante       = Column(Integer, ForeignKey("estudiante.id_usuario"),                  primary_key=True)
    id_parcial          = Column(Integer, ForeignKey("parcial.id_parcial", ondelete="CASCADE"), primary_key=True)
    nota                = Column(Numeric(5, 2))
    observacion         = Column(Text)
    ultima_modificacion = Column(DateTime)

    estudiante = relationship("Estudiante", back_populates="notas")
    parcial    = relationship("Parcial",    back_populates="notas")