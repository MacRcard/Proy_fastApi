from datetime import date
import uuid
from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
SECRET_KEY = "7e19d6b108943e9602f19a86d2c08f5533dc13abe9c95bf4f628eb7cb79a4b45"
ALGORITHM  = "HS256"
bearer  = HTTPBearer()
import jwt
from sqlalchemy.orm import Session, joinedload
from .schemas_admin import (EstudianteCreate, EstudianteOut, EstudianteUpdate)
from .schemas_notas import (PerfilEstudianteCompletoOut, NotaDetalleOut, ParcialConNotaOut, MateriaConEvaluacionesOut)

from ..database import get_db
from .. import models
router = APIRouter(prefix="/admin/estudiantes", tags=["Admin - Estudiantes"])

@router.get("/Estudiantes-filter/")
def get_estudiantes(
    mencion:  Optional[str] = None,
    anio:     Optional[int] = None,
    nombre:   Optional[str] = None,
    apellido: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Lista estudiantes con sus materias, parciales y notas.
    Filtros opcionales combinables:
      - ?mencion=fisioterapia
      - ?anio=1
      - ?nombre=carlos
      - ?apellido=mendoza
      - ?mencion=laboratorio&anio=2
    """
    q = db.query(models.Estudiante)
    if mencion:
        q = q.filter(models.Estudiante.mencion.ilike(f"%{mencion}%"))
    if anio:
        q = q.filter(models.Estudiante.anio == anio)
    if nombre:
        q = q.filter(models.Estudiante.nombre.ilike(f"%{nombre}%"))
    if apellido:
        q = q.filter(models.Estudiante.apellido.ilike(f"%{apellido}%"))
    estudiantes = q.all()
    if not estudiantes:
        return []
    resultado = []
    for e in estudiantes:
        materias = []
        for inscripcion in e.inscripciones:
            m = inscripcion.materia
            materias.append({
                "id_materia":     m.id_materia,
                "sigla":          m.sigla,
                "nombre_materia": m.nombre_materia,
                "horario":        m.horario,
                "anio":           m.anio,
                "parciales": [
                    {
                        "id_parcial":     p.id_parcial,
                        "nombre_parcial": p.nombre_parcial,
                        "tipo":           p.tipo,
                        "fecha":          str(p.fecha) if p.fecha else None,
                        "valoracion":     p.valoracion,
                        "nota":           next(
                            (float(n.nota) if n.nota is not None else None
                             for n in e.notas if n.id_parcial == p.id_parcial),
                            None,
                        ),
                        "observacion":    next(
                            (n.observacion
                             for n in e.notas if n.id_parcial == p.id_parcial),
                            None,
                        ),
                    }
                    for p in m.parciales
                ],
            })
        resultado.append({
            "id_estudiante": e.id_estudiante,
            "ci_estudiante": e.ci_estudiante,
            "matricula":     e.matricula,
            "nombre":        e.nombre,
            "apellido":      e.apellido,
            "anio":          e.anio,
            "mencion":       e.mencion,
            "materias":      materias,
        })
    return resultado

@router.get("/estudiantes/{id_estudiante}/kardex", response_model=PerfilEstudianteCompletoOut)
def obtener_perfil_estudiante_detallado(id_estudiante: UUID, db: Session = Depends(get_db)):
    # 1. Buscar al estudiante
    estudiante = db.query(models.Estudiante).filter(models.Estudiante.id_estudiante == id_estudiante).first()
    if not estudiante:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    # 2. Construir la lista de materias e información académica
    materias_resumen = []
    # Recorremos las inscripciones del estudiante
    for inscripcion in estudiante.inscripciones:
        materia = inscripcion.materia
        lista_parciales_con_nota = []

        # Recorremos cada parcial de la materia
        for parcial in materia.parciales:
            # Buscamos la nota específica de este estudiante para este parcial específico
            nota_db = db.query(models.Nota).filter(
                models.Nota.id_estudiante == id_estudiante,
                models.Nota.id_parcial == parcial.id_parcial
            ).first()

            nota_info = None
            if nota_db:
                nota_info = NotaDetalleOut(
                    nota=float(nota_db.nota) if nota_db.nota is not None else None,
                    observacion=nota_db.observacion
                )

            lista_parciales_con_nota.append(ParcialConNotaOut(
                id_parcial=parcial.id_parcial,
                nombre_parcial=parcial.nombre_parcial,
                fecha=parcial.fecha,
                tipo=parcial.tipo,
                valoracion=parcial.valoracion,
                nota_detalle=nota_info
            ))

        materias_resumen.append(MateriaConEvaluacionesOut(
            id_materia=materia.id_materia,
            sigla=materia.sigla,
            nombre_materia=materia.nombre_materia,
            parciales=lista_parciales_con_nota
        ))

    # 3. Retornar el objeto completo
    return PerfilEstudianteCompletoOut(
        id_estudiante=estudiante.id_estudiante,
        nombre=estudiante.nombre,
        apellido=estudiante.apellido,
        matricula=estudiante.matricula,
        mencion=estudiante.mencion,
        materias=materias_resumen
    )

@router.get("/acceder", response_model=PerfilEstudianteCompletoOut)
def acceder_portal_estudiante(ci: int, matricula: int, db: Session = Depends(get_db)):
    # 1. Verificar credenciales
    estudiante = db.query(models.Estudiante).filter(
        models.Estudiante.ci_estudiante == ci,
        models.Estudiante.matricula == matricula
    ).first()

    if not estudiante:
        raise HTTPException(
            status_code=404, 
            detail="Credenciales incorrectas. Verifica tu CI y Matrícula."
        )

    # 2. Reutilizar la lógica del Kardex para devolver todo el objeto
    # (Aquí llamarías a la misma lógica de construcción de JSON del mensaje anterior)
    # ... 
    return obtener_perfil_estudiante_detallado(estudiante.id_estudiante, db)

@router.post("/", response_model=EstudianteOut, status_code=status.HTTP_201_CREATED)
def crear_estudiante(obj_in: EstudianteCreate, db: Session = Depends(get_db)):
    """Crea un estudiante."""

    if db.query(models.Estudiante).filter(
        models.Estudiante.ci_estudiante == obj_in.ci_estudiante
    ).first():
        raise HTTPException(status_code=409, detail="El carnet ya está registrado")
    if db.query(models.Estudiante).filter(
        models.Estudiante.matricula == obj_in.matricula
    ).first():
        raise HTTPException(status_code=409, detail="La matrícula ya está registrada")

    nuevo = models.Estudiante(**obj_in.model_dump())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

@router.patch("/{id_estudiante}", response_model=EstudianteOut)
def actualizar_estudiante(
    id_estudiante: UUID,
    obj_in: EstudianteUpdate,
    db: Session = Depends(get_db),
):
    """Edita parcialmente un estudiante. solo de notas ya existentes"""
    estudiante = db.query(models.Estudiante).filter(
        models.Estudiante.id_estudiante == id_estudiante
    ).first()
    if not estudiante:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    # Verificar CI duplicado si se está cambiando
    if obj_in.ci_estudiante is not None:
        if db.query(models.Estudiante).filter(
            models.Estudiante.ci_estudiante == obj_in.ci_estudiante,
            models.Estudiante.id_estudiante != id_estudiante,
        ).first():
            raise HTTPException(status_code=409, detail="El carnet ya está registrado")

    # Verificar matrícula duplicada si se está cambiando
    if obj_in.matricula is not None:
        if db.query(models.Estudiante).filter(
            models.Estudiante.matricula == obj_in.matricula,
            models.Estudiante.id_estudiante != id_estudiante,
        ).first():
            raise HTTPException(status_code=409, detail="La matrícula ya está registrada")

    for key, value in obj_in.model_dump(exclude_unset=True).items():
        setattr(estudiante, key, value)

    db.commit()
    db.refresh(estudiante)
    return estudiante

# --- ELIMINAR ---
@router.delete("/{id_estudiante}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_estudiante(id_estudiante: UUID, db: Session = Depends(get_db)):
    """elimina un estudiante"""
    estudiante = db.query(models.Estudiante).filter(models.Estudiante.id_estudiante == id_estudiante).first()
    if not estudiante:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    
    db.delete(estudiante)
    db.commit()
    return None
# @router.get("/estudiantes/")
# def get_estudiantes(db: Session = Depends(get_db)):
#     """Lista todos los estudiantes con sus materias, parciales y notas."""
#     estudiantes = db.query(models.Estudiante).all()

#     resultado = []
#     for e in estudiantes:
#         materias = []
#         for inscripcion in e.inscripciones:
#             m = inscripcion.materia
#             materias.append({
#                 "id_materia":     m.id_materia,
#                 "sigla":          m.sigla,
#                 "nombre_materia": m.nombre_materia,
#                 "horario":        m.horario,
#                 "anio":           m.anio,
#                 "parciales": [
#                     {
#                         "id_parcial":     p.id_parcial,
#                         "nombre_parcial": p.nombre_parcial,
#                         "tipo":           p.tipo,
#                         "fecha":          str(p.fecha) if p.fecha else None,
#                         "valoracion":     p.valoracion,
#                         "nota":           next(
#                             (float(n.nota) if n.nota is not None else None
#                              for n in e.notas if n.id_parcial == p.id_parcial),
#                             None
#                         ),
#                         "observacion":    next(
#                             (n.observacion
#                              for n in e.notas if n.id_parcial == p.id_parcial),
#                             None
#                         ),
#                     }
#                     for p in m.parciales
#                 ],
#             })
#         resultado.append({
#             "id_estudiante": e.id_estudiante,
#             "ci_estudiante": e.ci_estudiante,
#             "matricula":     e.matricula,
#             "nombre":        e.nombre,
#             "apellido":      e.apellido,
#             "anio":          e.anio,
#             "mencion":       e.mencion,
#             "materias":      materias,
#         })
#     return resultado

# ── PATCH /notas/{id_estudiante}/{id_parcial} ─────────────────────────────────
@router.patch("/notas/{id_estudiante}/{id_parcial}", tags=["Admin - Estudiantes"])
def update_nota(
    id_estudiante: UUID,
    id_parcial:    UUID,
    nota:          float | None = None,
    observacion:   str   | None = None,
    db:            Session = Depends(get_db),
    credentials:   HTTPAuthorizationCredentials = Depends(bearer),
):
    # Decodificar token y obtener rol
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")
    
    rol = payload.get("rol")

    # Verificar límite de 10 días si no es admin
    if rol != "admin":
        parcial = db.query(models.Parcial).filter(
            models.Parcial.id_parcial == id_parcial
        ).first()
        if parcial and parcial.fecha:
            if (date.today() - parcial.fecha).days > 10:
                raise HTTPException(
                    status_code=403,
                    detail="Han pasado más de 10 días desde el parcial, no puedes modificar esta nota"
                )

    registro = (
        db.query(models.Nota)
        .filter(
            models.Nota.id_estudiante == id_estudiante,
            models.Nota.id_parcial    == id_parcial,
        )
        .first()
    )

    if not registro:
        raise HTTPException(status_code=404, detail="Nota no encontrada")

    if nota is not None:
        if nota < 0:
            raise HTTPException(status_code=422, detail="La nota no puede ser negativa")
        registro.nota = nota

    if observacion is not None:
        registro.observacion = observacion

    db.commit()
    db.refresh(registro)

    return {
        "id_estudiante":       registro.id_estudiante,
        "id_parcial":          registro.id_parcial,
        "nota":                float(registro.nota) if registro.nota is not None else None,
        "observacion":         registro.observacion,
        "ultima_modificacion": registro.ultima_modificacion,
    }

# ── POST /inscripciones/ ──────────────────────────────────────────────────────    
@router.post("/inscripciones/", tags=["Admin - Estudiantes"], status_code=201)
def inscribir_estudiante(
    id_estudiante: UUID,
    id_materia:    UUID,
    db:            Session = Depends(get_db),
):
    """Inscribe a un estudiante en una materia."""
    # Verificar que el estudiante existe
    estudiante = db.query(models.Estudiante).filter(
        models.Estudiante.id_estudiante == id_estudiante
    ).first()
    if not estudiante:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    # Verificar que la materia existe
    materia = db.query(models.Materia).filter(
        models.Materia.id_materia == id_materia
    ).first()
    if not materia:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
    # Verificar que no esté ya inscrito
    ya_inscrito = db.query(models.Inscrito).filter(
        models.Inscrito.id_estudiante == id_estudiante,
        models.Inscrito.id_materia    == id_materia,
    ).first()
    if ya_inscrito:
        raise HTTPException(status_code=409, detail="El estudiante ya está inscrito en esta materia")

    inscripcion = models.Inscrito(
        id_estudiante = id_estudiante,
        id_materia    = id_materia,
    )
    db.add(inscripcion)
    db.commit()

    return {
        "mensaje":        "Estudiante inscrito correctamente",
        "id_estudiante":  id_estudiante,
        "id_materia":     id_materia,
        "sigla":          materia.sigla,
        "nombre_materia": materia.nombre_materia,
    }