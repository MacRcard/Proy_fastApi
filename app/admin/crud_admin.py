import uuid
from typing import List
from uuid import UUID

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from .schemas_admin import (DocenteCreate, DocenteUpdate, DocenteOut,AuxiliarCreate, AuxiliarUpdate, AuxiliarOut, AsignarAuxiliarBody)

router = APIRouter(prefix="/admin")

TITULOS_VALIDOS = {"licenciado", "doctor", "magister"}

def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def _username_libre(username: str, db: Session, excluir_id: UUID | None = None) -> None:
    q = db.query(models.Usuario).filter(models.Usuario.username == username)
    if excluir_id:
        q = q.filter(models.Usuario.id_usuario != excluir_id)
    if q.first():
        raise HTTPException(status_code=409, detail="El username ya está en uso")

def _email_libre(email: str, db: Session, excluir_id: UUID | None = None) -> None:
    q = db.query(models.Auxiliar).filter(models.Auxiliar.email == email)
    if excluir_id:
        q = q.filter(models.Auxiliar.id_usuario != excluir_id)
    if q.first():
        raise HTTPException(status_code=409, detail="El email ya está en uso")

def _get_docente_or_404(id_usuario: UUID, db: Session) -> models.Docente:
    obj = db.query(models.Docente).filter(models.Docente.id_usuario == id_usuario).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Docente no encontrado")
    return obj

def _get_auxiliar_or_404(id_usuario: UUID, db: Session) -> models.Auxiliar:
    obj = db.query(models.Auxiliar).filter(models.Auxiliar.id_usuario == id_usuario).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Auxiliar no encontrado")
    return obj

def _get_materia_or_404(id_materia: UUID, db: Session) -> models.Materia:
    obj = db.query(models.Materia).filter(models.Materia.id_materia == id_materia).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
    return obj

def _get_auxiliar_activo_or_404(id_auxiliar: UUID, db: Session) -> models.Auxiliar:
    obj = db.query(models.Auxiliar).filter(models.Auxiliar.id_usuario == id_auxiliar).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Auxiliar no encontrado")
    if not obj.activo:
        raise HTTPException(status_code=403, detail="El auxiliar está inactivo")
    return obj

# CRUD — DOCENTE
@router.get("/docentes/", response_model=List[DocenteOut])
def list_docentes(db: Session = Depends(get_db)):
    """Lista todos los docentes."""
    return [
        DocenteOut(
            id_usuario = d.id_usuario,
            username   = d.usuario.username,
            titulo     = d.titulo,
            nombre     = d.nombre_docente,
            apellido   = d.apellido_docente,
        )
        for d in db.query(models.Docente).all()
    ]

@router.get("/docentes/materias-parciales", tags=["Admin - Docente"])
def get_docentes_con_materias_y_parciales(db: Session = Depends(get_db)):
    """
    Lista todos los docentes con sus materias,
    y cada materia con sus parciales de tipo 'parcial'.
    """
    docentes = db.query(models.Docente).all()

    resultado = []
    for d in docentes:
        materias = []
        for m in d.materias:
            parciales = (db.query(models.Parcial).filter(models.Parcial.id_materia == m.id_materia,
                                                         models.Parcial.tipo == "parcial").all())
            materias.append({
                "id_materia":     m.id_materia,
                "sigla":          m.sigla,
                "nombre_materia": m.nombre_materia,
                "horario":        m.horario,
                "anio":           m.anio,
                "parciales":      parciales,
            })
        resultado.append({
            "id_usuario": d.id_usuario,
            "nombre":     d.nombre_docente,
            "apellido":   d.apellido_docente,
            "titulo":     d.titulo,
            "username":   d.usuario.username,
            "materias":   materias,
        })

    return resultado

@router.get("/docentes/{id_usuario}", response_model=DocenteOut, tags=["Admin - Docente"])
def get_docente(id_usuario: UUID, db: Session = Depends(get_db)):
    """Obtiene un docente por su id_usuario."""
    d = _get_docente_or_404(id_usuario, db)
    return DocenteOut(
        id_usuario = d.id_usuario,
        username   = d.usuario.username,
        titulo     = d.titulo,
        nombre     = d.nombre_docente,
        apellido   = d.apellido_docente,
    )

@router.post("/docentes/", response_model=DocenteOut, status_code=201, tags=["Admin - Docente"])
def create_docente(body: DocenteCreate, db: Session = Depends(get_db)):
    """Crea un usuario con rol='docente' y su registro en la tabla docente."""
    if body.titulo and body.titulo not in TITULOS_VALIDOS:
        raise HTTPException(status_code=422, detail=f"Título inválido. Opciones: {TITULOS_VALIDOS}")

    _username_libre(body.username, db)

    nuevo_id = uuid.uuid4()
    usuario = models.Usuario(
        id_usuario = nuevo_id,
        rol        = "docente",
        username   = body.username,
        password   = _hash(body.password),
    )
    db.add(usuario)
    db.flush()

    docente = models.Docente(
        id_usuario       = nuevo_id,
        titulo           = body.titulo,
        nombre_docente   = body.nombre,
        apellido_docente = body.apellido,
    )
    db.add(docente)
    db.commit()
    db.refresh(docente)

    return DocenteOut(
        id_usuario = docente.id_usuario,
        username   = usuario.username,
        titulo     = docente.titulo,
        nombre     = docente.nombre_docente,
        apellido   = docente.apellido_docente,
    )

@router.patch("/docentes/{id_usuario}", response_model=DocenteOut, tags=["Admin - Docente"])
def update_docente(id_usuario: UUID,body: DocenteUpdate,db: Session = Depends(get_db)):
    """Actualiza parcialmente un docente."""
    docente = _get_docente_or_404(id_usuario, db)

    if body.titulo is not None:
        if body.titulo not in TITULOS_VALIDOS:
            raise HTTPException(status_code=422, detail=f"Título inválido. Opciones: {TITULOS_VALIDOS}")
        docente.titulo = body.titulo

    if body.nombre is not None:
        docente.nombre_docente = body.nombre

    if body.apellido is not None:
        docente.apellido_docente = body.apellido

    if body.username is not None:
        _username_libre(body.username, db, excluir_id=id_usuario)
        docente.usuario.username = body.username

    if body.password is not None:
        docente.usuario.password = _hash(body.password)

    db.commit()
    db.refresh(docente)

    return DocenteOut(
        id_usuario = docente.id_usuario,
        username   = docente.usuario.username,
        titulo     = docente.titulo,
        nombre     = docente.nombre_docente,
        apellido   = docente.apellido_docente,
    )

@router.delete("/docentes/{id_usuario}", status_code=204, tags=["Admin - Docente"])
def delete_docente(id_usuario: UUID, db: Session = Depends(get_db)):
    """Elimina el docente y su usuario (CASCADE en BD limpia la tabla docente)."""
    docente = _get_docente_or_404(id_usuario, db)
    db.delete(docente.usuario)
    db.commit()

# CRUD — AUXILIAR
@router.get("/auxiliares/", response_model=List[AuxiliarOut])
def list_auxiliares(db: Session = Depends(get_db)):
    """Lista todos los auxiliares."""
    return [
        AuxiliarOut(
            id_usuario = a.id_usuario,
            username   = a.usuario.username,
            nombre     = a.nombre,
            email      = a.email,
            activo     = a.activo,
        )
        for a in db.query(models.Auxiliar).all()
    ]

@router.get("/auxiliares/materias-parciales", tags=["Admin - Auxiliares"])
def get_docentes_con_materias_y_parciales(db: Session = Depends(get_db)):
    """
    Lista todos los auxiliares con sus materias,
    y cada materia con sus parciales de tipo 'practicas'.
    """
    auxiliares = db.query(models.Auxiliar).all()

    resultado = []
    for d in auxiliares:
        materias = []
        for m in d.materias:
            practicas = (db.query(models.Parcial).filter(models.Parcial.id_materia == m.id_materia,
                                                         models.Parcial.tipo == "practica").all())
            materias.append({
                "id_materia":     m.id_materia,
                "sigla":          m.sigla,
                "nombre_materia": m.nombre_materia,
                "horario":        m.horario,
                "anio":           m.anio,
                "practicas":      practicas,
            })
        resultado.append({
            "id_usuario": d.id_usuario,
            "nombre":     d.nombre,
            "username":   d.usuario.username,
            "materias":   materias,
        })
    return resultado

@router.get("/auxiliares/{id_usuario}", response_model=AuxiliarOut, tags=["Admin - Auxiliares"])
def get_auxiliar(id_usuario: UUID, db: Session = Depends(get_db)):
    """Obtiene un auxiliar por su id_usuario."""
    a = _get_auxiliar_or_404(id_usuario, db)
    return AuxiliarOut(
        id_usuario = a.id_usuario,
        username   = a.usuario.username,
        nombre     = a.nombre,
        email      = a.email,
        activo     = a.activo,
    )
# corrergir
@router.post("/auxiliares/", response_model=AuxiliarOut, status_code=201, tags=["Admin - Auxiliares"])
def create_auxiliar(body: AuxiliarCreate, db: Session = Depends(get_db)):
    """
    Crea un usuario con rol='auxiliar' y su registro en la tabla auxiliar.
    El flush() previo asegura que el trigger check_auxiliar_role de PG encuentre el usuario.
    """
    _username_libre(body.username, db)
    _email_libre(body.email, db)

    nuevo_id = uuid.uuid4()
    usuario = models.Usuario(
        id_usuario = nuevo_id,
        rol        = "auxiliar",
        username   = body.username,
        password   = _hash(body.password),
    )
    db.add(usuario)
    db.flush()

    auxiliar = models.Auxiliar(
        id_usuario = nuevo_id,
        nombre     = body.nombre,
        email      = body.email,
        activo     = body.activo,
    )
    db.add(auxiliar)
    db.commit()
    db.refresh(auxiliar)

    return AuxiliarOut(
        id_usuario = auxiliar.id_usuario,
        username   = usuario.username,
        nombre     = auxiliar.nombre,
        email      = auxiliar.email,
        activo     = auxiliar.activo,
    )

@router.patch("/auxiliares/{id_usuario}", response_model=AuxiliarOut, tags=["Admin - Auxiliares"])
def update_auxiliar(
    id_usuario: UUID,
    body: AuxiliarUpdate,
    db: Session = Depends(get_db),
):
    """Actualiza parcialmente un auxiliar."""
    auxiliar = _get_auxiliar_or_404(id_usuario, db)

    if body.nombre is not None:
        auxiliar.nombre = body.nombre

    if body.email is not None:
        _email_libre(body.email, db, excluir_id=id_usuario)
        auxiliar.email = body.email

    if body.activo is not None:
        auxiliar.activo = body.activo
    # if body.username is not None:
    #     _username_libre(body.username, db, excluir_id=id_usuario)
    #     auxiliar.usuario.username = body.username
    if body.password is not None:
        auxiliar.usuario.password = _hash(body.password)

    db.commit()
    db.refresh(auxiliar)

    return AuxiliarOut(
        id_usuario = auxiliar.id_usuario,
        username   = auxiliar.usuario.username,
        nombre     = auxiliar.nombre,
        email      = auxiliar.email,
        activo     = auxiliar.activo,
    )
 
@router.delete("/auxiliares/{id_usuario}", status_code=204, tags=["Admin - Auxiliares"])
def delete_auxiliar(id_usuario: UUID, db: Session = Depends(get_db)):
    """Elimina el auxiliar y su usuario (CASCADE en BD limpia la tabla auxiliar)."""
    auxiliar = _get_auxiliar_or_404(id_usuario, db)
    db.delete(auxiliar.usuario)
    db.commit()

# @router.patch("/materias/{id_materia}/auxiliar", tags=["Admin"])
# def asignar_auxiliar(
#     id_materia: UUID,
#     body: AsignarAuxiliarBody,
#     db: Session = Depends(get_db),
# ):
#     """
#     Asigna un auxiliar a una materia.
#     - Pasa None en id_auxiliar para desasignar.
#     - Valida que el auxiliar exista y esté activo.
#     """
#     materia = _get_materia_or_404(id_materia, db)
#     _get_auxiliar_activo_or_404(body.id_auxiliar, db)

#     materia.id_auxiliar = body.id_auxiliar
#     db.commit()
#     db.refresh(materia)

#     return {
#         "id_materia":  materia.id_materia,
#         "sigla":       materia.sigla,
#         "id_auxiliar": materia.id_auxiliar,
#         "auxiliar":    materia.auxiliar.nombre if materia.auxiliar else None,
#     }

# @router.delete("/materias/{id_materia}/auxiliar", status_code=204, tags=["Admin"])
# def desasignar_auxiliar(id_materia: UUID, db: Session = Depends(get_db)):
    # """Quita el auxiliar asignado a una materia."""
    # materia = _get_materia_or_404(id_materia, db)
    # materia.id_auxiliar = None
    # db.commit()