# from typing import List, Optional
# from uuid import UUID

# import bcrypt
# from fastapi import APIRouter, Depends, HTTPException
# # from pydantic import BaseModel, EmailStr
# from sqlalchemy.orm import Session

# from app.admin.schemas_admin import (AuxiliarCreate, AuxiliarOut, AuxiliarUpdate)

# from ..database import get_db
# from .. import models

# router = APIRouter(prefix="/auxiliares", tags=["Auxiliar"])


# # ── Helpers ───────────────────────────────────────────────────────────────────

# def _hash(plain: str) -> str:
#     return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# def _get_auxiliar_or_404(id_usuario: UUID, db: Session) -> models.Auxiliar:
#     obj = db.query(models.Auxiliar).filter(
#         models.Auxiliar.id_usuario == id_usuario
#     ).first()
#     if not obj:
#         raise HTTPException(status_code=404, detail="Auxiliar no encontrado")
#     return obj


# # ── CRUD ──────────────────────────────────────────────────────────────────────

# @router.get("/", response_model=List[AuxiliarOut])
# def list_auxiliares(db: Session = Depends(get_db)):
#     """Lista todos los auxiliares con su información de usuario."""
#     auxiliares = db.query(models.Auxiliar).all()
#     result = []
#     for aux in auxiliares:
#         result.append(AuxiliarOut(
#             id_usuario = aux.id_usuario,
#             nombre     = aux.nombre,
#             email      = aux.email,
#             activo     = aux.activo,
#             username   = aux.usuario.username if aux.usuario else "",
#         ))
#     return result


# @router.get("/{id_usuario}", response_model=AuxiliarOut)
# def get_auxiliar(id_usuario: UUID, db: Session = Depends(get_db)):
#     """Obtiene un auxiliar por su id_usuario."""
#     aux = _get_auxiliar_or_404(id_usuario, db)
#     return AuxiliarOut(
#         id_usuario = aux.id_usuario,
#         nombre     = aux.nombre,
#         email      = aux.email,
#         activo     = aux.activo,
#         username   = aux.usuario.username if aux.usuario else "",
#     )


# @router.post("/", response_model=AuxiliarOut, status_code=201)
# def create_auxiliar(body: AuxiliarCreate, db: Session = Depends(get_db)):
#     """
#     Crea un usuario con rol='auxiliar' y su registro en la tabla auxiliar.
#     El trigger de la BD valida que el rol sea 'auxiliar' antes del INSERT en auxiliar.
#     """
#     # Verificar que el username no esté en uso
#     if db.query(models.Usuario).filter(
#         models.Usuario.username == body.username
#     ).first():
#         raise HTTPException(status_code=409, detail="El username ya está en uso")

#     # Verificar que el email no esté en uso
#     if db.query(models.Auxiliar).filter(
#         models.Auxiliar.email == body.email
#     ).first():
#         raise HTTPException(status_code=409, detail="El email ya está en uso")

#     # 1. Crear usuario con rol='auxiliar'
#     nuevo_usuario = models.Usuario(
#         rol        = "auxiliar",
#         username   = body.username,
#         password   = _hash(body.password),
#     )
#     db.add(nuevo_usuario)
#     db.flush()   # persiste para que el trigger encuentre el registro

#     # 2. Crear auxiliar (el trigger check_auxiliar_role valida el rol)
#     nuevo_auxiliar = models.Auxiliar(
#         nombre     = body.nombre,
#         email      = body.email,
#         activo     = body.activo,
#     )
#     db.add(nuevo_auxiliar)
#     db.commit()
#     db.refresh(nuevo_auxiliar)

#     return AuxiliarOut(
#         id_usuario = nuevo_auxiliar.id_usuario,
#         nombre     = nuevo_auxiliar.nombre,
#         email      = nuevo_auxiliar.email,
#         activo     = nuevo_auxiliar.activo,
#         username   = nuevo_usuario.username,
#     )


# @router.patch("/{id_usuario}", response_model=AuxiliarOut)
# def update_auxiliar(
#     id_usuario: UUID,
#     body: AuxiliarUpdate,
#     db: Session = Depends(get_db),
# ):
#     """
#     Actualiza parcialmente un auxiliar.
#     - nombre / email / activo se actualizan en la tabla auxiliar.
#     - password se re-hashea y se actualiza en la tabla usuario.
#     """
#     aux = _get_auxiliar_or_404(id_usuario, db)

#     if body.nombre is not None:
#         aux.nombre = body.nombre

#     if body.email is not None:
#         # Verificar unicidad del nuevo email
#         conflicto = db.query(models.Auxiliar).filter(
#             models.Auxiliar.email      == body.email,
#             models.Auxiliar.id_usuario != id_usuario,
#         ).first()
#         if conflicto:
#             raise HTTPException(status_code=409, detail="El email ya está en uso")
#         aux.email = body.email

#     if body.activo is not None:
#         aux.activo = body.activo

#     if body.password is not None:
#         if aux.usuario:
#             aux.usuario.password = _hash(body.password)

#     db.commit()
#     db.refresh(aux)

#     return AuxiliarOut(
#         id_usuario = aux.id_usuario,
#         nombre     = aux.nombre,
#         email      = aux.email,
#         activo     = aux.activo,
#         username   = aux.usuario.username if aux.usuario else "",
#     )


# @router.delete("/{id_usuario}", status_code=204)
# def delete_auxiliar(id_usuario: UUID, db: Session = Depends(get_db)):
#     """
#     Elimina el auxiliar y su usuario asociado en cascada
#     (el CASCADE ON DELETE en la BD se encarga de limpiar auxiliar al borrar usuario).
#     """
#     aux = _get_auxiliar_or_404(id_usuario, db)

#     # Borrar el usuario dispara el CASCADE que elimina el auxiliar también
#     if aux.usuario:
#         db.delete(aux.usuario)
#     else:
#         db.delete(aux)

#     db.commit()