from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Formato: postgresql+psycopg2://usuario:contraseña@host:puerto/nombre_bd
USER = "postgres"
PASSWORD = "andrea"       # Cambia esto por tu contraseña de PostgreSQL
HOST = "localhost"
PORT = "5432"                     # Puerto por defecto de PostgreSQL
DB = "TecMed"                     # Nombre exacto de tu base de datos (case-sensitive)

SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB}"

# El engine se comunica con la BD
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