import enum
import uuid
from sqlalchemy import TIMESTAMP, Column, Integer, String, Enum, Numeric, Text, Date, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .database import Base

# ENUMS

class RolEnum(str, enum.Enum):
    docente = "docente"
    admin   = "admin"

class TituloEnum(str, enum.Enum):
    licenciado = "licenciado"
    doctor     = "doctor"
    magister   = "magister"

# TABLA USUARIO (UUID)

class Usuario(Base):
    __tablename__ = "usuario"

    id_usuario = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4  # Genera UUID automáticamente en Python
    )
    rol        = Column(Enum(RolEnum), nullable=False, default=RolEnum.docente)
    username   = Column(String(100), nullable=False, unique=True)
    password   = Column(String(100), nullable=False)

    docente = relationship(
        "Docente",
        back_populates="usuario",
        uselist=False,          # uno a uno
        cascade="all, delete-orphan",
    )

class Docente(Base):
    __tablename__ = "docente"
    
    id_usuario = Column(
        UUID(as_uuid=True),
        ForeignKey("usuario.id_usuario", ondelete="CASCADE"),
        primary_key=True,
    )
    titulo           = Column(Enum(TituloEnum), nullable=True)
    nombre_docente   = Column(String(100), nullable=False)
    apellido_docente = Column(String(100), nullable=False)

    usuario = relationship("Usuario", back_populates="docente")
    materias = relationship("Materia", back_populates="docente")

class Estudiante(Base):
    __tablename__ = "estudiante"

    id_estudiante = Column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)

    ci_estudiante = Column(Integer, nullable=False)
    matricula     = Column(Integer, nullable=False, unique=True)
    nombre        = Column(String(100), nullable=False)
    apellido      = Column(String(100), nullable=False)
    anio          = Column(Integer, nullable=True)
    mencion       = Column(String(100), nullable=True)

    inscripciones = relationship(
        "Inscrito",
        back_populates="estudiante",
        cascade="all, delete-orphan",
    )
    notas = relationship(
        "Nota",
        back_populates="estudiante",
        cascade="all, delete-orphan",
    )

class Materia(Base):
    __tablename__ = "materia"

    id_materia = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sigla      = Column(String(20), nullable=False)  # NOT NULL pero no es PK
    horario    = Column(String(50), nullable=True)
    anio       = Column(Integer, nullable=True)
    id_docente = Column(
        UUID(as_uuid=True),
        ForeignKey("docente.id_usuario"),
        nullable=True,
    )

    docente = relationship("Docente", back_populates="materias")
    inscripciones = relationship(
        "Inscrito",
        back_populates="materia",
        cascade="all, delete-orphan",
    )
    parciales = relationship(
        "Parcial",
        back_populates="materia",
        cascade="all, delete-orphan",
    )


class Inscrito(Base):
    __tablename__ = "inscrito"

    id_estudiante = Column(UUID(as_uuid=True),ForeignKey("estudiante.id_estudiante", ondelete="CASCADE"),primary_key=True,
    )
    id_materia = Column(                                  # era sigla_materia (String FK → materia.sigla)
        UUID(as_uuid=True),
        ForeignKey("materia.id_materia", ondelete="CASCADE"),
        primary_key=True,
    )

    estudiante = relationship("Estudiante", back_populates="inscripciones")
    materia    = relationship("Materia",    back_populates="inscripciones")


class Parcial(Base):
    __tablename__ = "parcial"

    id_parcial = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # era Integer autoincrement
    nombre_parcial = Column(String(100), nullable=True)
    fecha          = Column(Date, nullable=True)
    valoracion     = Column(Integer, nullable=True)
    id_materia     = Column(                              # era sigla_materia (String FK → materia.sigla)
        UUID(as_uuid=True),
        ForeignKey("materia.id_materia", ondelete="CASCADE"),
        nullable=True,
    )

    materia = relationship("Materia", back_populates="parciales")
    notas = relationship(
        "Nota",
        back_populates="parcial",
        cascade="all, delete-orphan",
    )


class Nota(Base):
    __tablename__ = "notas"

    id_estudiante = Column(UUID(as_uuid=True),ForeignKey("estudiante.id_estudiante", ondelete="CASCADE"),primary_key=True,
    )
    id_parcial = Column(
        UUID(as_uuid=True),                               # era Integer
        ForeignKey("parcial.id_parcial", ondelete="CASCADE"),
        primary_key=True,
    )
    nota                = Column(Numeric(5, 2), nullable=True)
    observacion         = Column(Text, nullable=True)
    ultima_modificacion = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    estudiante = relationship("Estudiante", back_populates="notas")
    parcial    = relationship("Parcial",    back_populates="notas")