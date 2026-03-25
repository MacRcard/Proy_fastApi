from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import FastAPI, Form, HTTPException, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
import bcrypt

from .database import engine, get_db
from . import models

SECRET_KEY = "7e19d6b108943e9602f19a86d2c08f5533dc13abe9c95bf4f628eb7cb79a4b45"
TOKEN_SECONDS_EXP = 120

app = FastAPI()

models.Base.metadata.create_all(bind=engine)
jinja2_template = Jinja2Templates(directory="templates")

@app.get("/usuarios/")
def read_users(db: Session = Depends(get_db)):
    return db.query(models.Usuario).all()

def get_user_ci(ci: str, db: Session) -> models.Usuario | None:
    return db.query(models.Usuario).filter(models.Usuario.ci == ci).first()

def hash_password(plain_password: str) -> str:
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")

def authenticate_user(hashed_password: str, plain_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    ) 

def create_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(seconds=TOKEN_SECONDS_EXP)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
def registrar(ci: str,nombre: str,apellido: str,rol: str,plain_password: str,db: Session,) -> models.Usuario:
    if get_user_ci(ci, db) is not None:
        raise HTTPException(status_code=400, detail=f"El CI '{ci}' ya está registrado")
    nuevo_usuario = models.Usuario(
        ci=ci,
        nombre=nombre,
        apellido=apellido,
        rol=rol,
        contrasenia=hash_password(plain_password),
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario

##RUTAS##
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return jinja2_template.TemplateResponse("index.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return jinja2_template.TemplateResponse("register.html", {"request": request})

@app.post("/users/register")
def register(
    ci:       Annotated[str, Form()],
    nombre:   Annotated[str, Form()],
    apellido: Annotated[str, Form()],
    rol:      Annotated[str, Form()],   # 'estudiante' | 'docente' | 'admin'
    password: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    registrar(ci, nombre, apellido, rol, password, db)
    return RedirectResponse("/login", status_code=302)

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
                "request": request,
                "user":     data_user["nombre"],
                "apellido": data_user["apellido"],
                "rol":      data_user["rol"],
            },
        )
    except (InvalidTokenError, ExpiredSignatureError):
        return RedirectResponse("/login", status_code=302)
    
@app.post("/users/login")
def login(username: Annotated[str, Form()],password: Annotated[str, Form()],db: Session = Depends(get_db),):
    user = get_user_ci(username, db)
    if user is None:
        raise HTTPException(status_code=401, detail="CI o contraseña incorrectos")
    if not authenticate_user(user.contrasenia, password):
        raise HTTPException(status_code=401, detail="CI o contraseña incorrectos")
    token = create_token({
        "sub": user.ci,
        "nombre": user.nombre,
        "apellido": user.apellido,
        "rol": user.rol,
    })
    return RedirectResponse(
        "/users/dashboard",
        status_code=302,
        headers={"set-cookie": f"access_token={token}; Max-Age={TOKEN_SECONDS_EXP}; HttpOnly; SameSite=lax"},
    )

@app.post("/users/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response