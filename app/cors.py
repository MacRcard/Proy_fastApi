from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Definir los orígenes permitidos (la URL de tu frontend)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Permite todos los métodos (GET, POST, etc.)
    allow_headers=["*"], # Permite todos los encabezados
)

@app.get("/estudiante/{matricula}")
async def obtener_notas(matricula: str):
    # Aquí iría tu lógica de base de datos
    return {
        "materia": "Bioquímica I",
        "parciales": [85, 72, 90],
        "final": 78
    }