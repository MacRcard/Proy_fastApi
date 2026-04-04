from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import FastAPI, Form, HTTPException, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from .parciales import router as parciales_router
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
import bcrypt

from .database import engine, get_db
from . import models

SECRET_KEY = "7e19d6b108943e9602f19a86d2c08f5533dc13abe9c95bf4f628eb7cb79a4b45"
TOKEN_SECONDS_EXP = 60*10

app = FastAPI()

models.Base.metadata.create_all(bind=engine)
jinja2_template = Jinja2Templates(directory="templates")
app.include_router(parciales_router)

# ── Utilidades de autenticación ──────────────────────────────────────────────

def get_user_ci(ci: str, db: Session) -> models.Usuario | None:
    return db.query(models.Usuario).filter(models.Usuario.ci == ci).first()


def hash_password(plain_password: str) -> str:
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def authenticate_password(hashed_password: str, plain_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(seconds=TOKEN_SECONDS_EXP)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")


def set_auth_cookie(response: RedirectResponse, token: str) -> RedirectResponse:
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=TOKEN_SECONDS_EXP,
        httponly=True,
        samesite="lax",
    )
    return response


# ── Registro ─────────────────────────────────────────────────────────────────

def registrar_docente(
    ci: str, nombre: str, apellido: str,
    plain_password: str, titulo: str, db: Session,
) -> models.Usuario:
    if get_user_ci(ci, db) is not None:
        raise HTTPException(status_code=400, detail=f"El CI '{ci}' ya está registrado")
    nuevo_usuario = models.Usuario(ci=ci, nombre=nombre, apellido=apellido, rol="docente")
    db.add(nuevo_usuario)
    db.flush()
    nuevo_docente = models.Docente(
        id_usuario=nuevo_usuario.id_usuario,
        titulo=titulo,
        contrasenia=hash_password(plain_password),
    )
    db.add(nuevo_docente)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario


def registrar_estudiante(
    ci: str, nombre: str, apellido: str,
    matricula: str, correo: str,
    anio: int | None, mencion: str | None,
    db: Session,
) -> models.Usuario:
    if get_user_ci(ci, db) is not None:
        raise HTTPException(status_code=400, detail=f"El CI '{ci}' ya está registrado")
    nuevo_usuario = models.Usuario(ci=ci, nombre=nombre, apellido=apellido, rol="estudiante")
    db.add(nuevo_usuario)
    db.flush()
    nuevo_estudiante = models.Estudiante(
        id_usuario=nuevo_usuario.id_usuario,
        matricula=matricula,
        correo=correo,
        anio=anio,
        mencion=mencion,
    )
    db.add(nuevo_estudiante)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario


# ── Páginas ───────────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return jinja2_template.TemplateResponse("index.html", {"request": request})


@app.get("/register/docente", response_class=HTMLResponse)
def register_docente_page(request: Request):
    return jinja2_template.TemplateResponse("register_docente.html", {"request": request})


@app.get("/register/estudiante", response_class=HTMLResponse)
def register_estudiante_page(request: Request):
    return jinja2_template.TemplateResponse("register_estudiante.html", {"request": request})


# ── Endpoints de registro ─────────────────────────────────────────────────────

@app.post("/users/register/docente")
def register_docente(
    ci:       Annotated[str, Form()],
    nombre:   Annotated[str, Form()],
    apellido: Annotated[str, Form()],
    password: Annotated[str, Form()],
    titulo:   Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    registrar_docente(ci, nombre, apellido, password, titulo, db)
    return RedirectResponse("/login", status_code=302)


@app.post("/users/register/estudiante")
def register_estudiante(
    ci:        Annotated[str, Form()],
    nombre:    Annotated[str, Form()],
    apellido:  Annotated[str, Form()],
    matricula: Annotated[str, Form()],
    correo:    Annotated[str, Form()],
    anio:      Annotated[int | None, Form()] = None,
    mencion:   Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
):
    registrar_estudiante(ci, nombre, apellido, matricula, correo, anio, mencion, db)
    return RedirectResponse("/login", status_code=302)


# ── Endpoints de login ────────────────────────────────────────────────────────

@app.post("/users/login/docente")
def login_docente(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    user = get_user_ci(username, db)
    if user is None or user.rol != "docente":
        raise HTTPException(status_code=401, detail="CI o contraseña incorrectos")
    if user.docente is None or not authenticate_password(user.docente.contrasenia, password):
        raise HTTPException(status_code=401, detail="CI o contraseña incorrectos")
    token = create_token({
        "sub":      str(user.ci),
        "nombre":   user.nombre,
        "apellido": user.apellido,
        "rol":      user.rol,
    })
    return set_auth_cookie(RedirectResponse("/users/dashboard", status_code=302), token)


@app.post("/users/login/estudiante")
def login_estudiante(
    ci:     Annotated[str, Form()],
    correo: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    user = get_user_ci(ci, db)
    if user is None or user.rol != "estudiante":
        raise HTTPException(status_code=401, detail="CI o correo incorrectos")
    if user.estudiante is None or user.estudiante.correo != correo:
        raise HTTPException(status_code=401, detail="CI o correo incorrectos")
    token = create_token({
        "sub":      str(user.ci),
        "nombre":   user.nombre,
        "apellido": user.apellido,
        "rol":      user.rol,
    })
    return set_auth_cookie(RedirectResponse("/users/dashboard", status_code=302), token)


# ── Dashboard y logout ────────────────────────────────────────────────────────

@app.get("/users/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    access_token = request.cookies.get("access_token")
    if access_token is None:
        return RedirectResponse("/login", status_code=302)
    try:
        data_user = jwt.decode(access_token, key=SECRET_KEY, algorithms=["HS256"])
        return jinja2_template.TemplateResponse(
            "dashboard.html",
            {
                "request":  request,
                "user":     data_user["nombre"],
                "apellido": data_user["apellido"],
                "rol":      data_user["rol"],
            },
        )
    except (InvalidTokenError, ExpiredSignatureError):
        return RedirectResponse("/login", status_code=302)


@app.post("/users/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response


# ── Endpoints de consulta ─────────────────────────────────────────────────────

@app.get("/usuarios/")
def read_users(db: Session = Depends(get_db)):
    usuarios = db.query(models.Usuario).all()
    resultado = []
    for u in usuarios:
        base = {
            "id_usuario": u.id_usuario,
            "ci":         u.ci,
            "nombre":     u.nombre,
            "apellido":   u.apellido,
            "rol":        u.rol,
        }
        if u.rol == "docente" and u.docente:
            base["titulo"] = u.docente.titulo
        elif u.rol == "estudiante" and u.estudiante:
            base["matricula"] = u.estudiante.matricula
            base["correo"]    = u.estudiante.correo
            base["anio"]      = u.estudiante.anio
            base["mencion"]   = u.estudiante.mencion
        resultado.append(base)
    return resultado


@app.get("/docentes/{id_usuario}/materias")
def get_materias_docente(id_usuario: int, db: Session = Depends(get_db)):
    user = db.query(models.Usuario).filter(
        models.Usuario.id_usuario == id_usuario,
        models.Usuario.rol == "docente",
    ).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Docente no encontrado")

    materias = user.docente.materias if user.docente else []

    return {
        "id_usuario": user.id_usuario,
        "nombre":     user.nombre,
        "apellido":   user.apellido,
        "titulo":     user.docente.titulo if user.docente else None,
        "materias": [
            {
                "sigla":   m.sigla,
                "horario": m.horario,
                "anio":    m.anio,
            }
            for m in materias
        ],
    }


@app.get("/estudiantes/{id_usuario}/materias")
def get_materias_estudiante(id_usuario: int, db: Session = Depends(get_db)):
    user = db.query(models.Usuario).filter(
        models.Usuario.id_usuario == id_usuario,
        models.Usuario.rol == "estudiante",
    ).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    # Las materias del estudiante se obtienen a través de la tabla inscrito
    inscripciones = user.estudiante.inscrito if user.estudiante else []

    return {
        "id_usuario": user.id_usuario,
        "nombre":     user.nombre,
        "apellido":   user.apellido,
        "matricula":  user.estudiante.matricula if user.estudiante else None,
        "materias": [
            {
                "sigla":   i.materia.sigla,
                "horario": i.materia.horario,
                "anio":    i.materia.anio,
            }
            for i in inscripciones
            if i.materia
        ],
    }