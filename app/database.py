from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Formato: mysql+pymysql://usuario:contraseña@host:puerto/nombre_bd
USER = "utecmed"
PASSWORD = "tecmed123"
DB = "tecmed1"
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://utecmed:tecmed123@localhost:3306/tecmed1"

# El engine es el encargado de comunicarse con la BD
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Cada instancia de SessionLocal será una sesión de base de datos
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clase base para crear los modelos (tablas)
Base = declarative_base()

# Dependencia para obtener la sesión en tus rutas de FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()