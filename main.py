from datetime import datetime, timedelta, timezone
from random import randint
from typing import Annotated, Any
from fastapi import Cookie, FastAPI, Form, HTTPException, Request, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

SECRET_KEY = "7e19d6b108943e9602f19a86d2c08f5533dc13abe9c95bf4f628eb7cb79a4b45"
TOKEN_SECONDS_EXP = 120

app = FastAPI(root_path="/api/v1")

jinja2_template = Jinja2Templates(directory="templates")

def get_user(username:str, db: list):
    if username in db:
        return db[username]
def authenticate_user(password:str, password_plane:str):
    password_clean = password.split("#")[0]
    if password_plane == password_clean:
        return True
    return False   
def create_token(data: dict):
    to_encode = data.copy()
    # Usar timezone-aware datetime es la mejor práctica actual
    expire = datetime.now(timezone.utc) + timedelta(seconds=TOKEN_SECONDS_EXP)
    to_encode.update({"exp": expire})
    # PyJWT devuelve un string directamente
    token_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
    return token_jwt

@app.get("/login", response_class=HTMLResponse)
def root(request: Request ):
    return jinja2_template.TemplateResponse("index.html",{"request": request})
@app.get("/users/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, access_token: Annotated[str | None, Cookie()] = None):
    if access_token is None:
        return RedirectResponse("/login", status_code=302)
    try:
        # IMPORTANTE: algorithms es en plural y espera una lista
        data_user = jwt.decode(access_token, key=SECRET_KEY, algorithms=["HS256"])
        print(f"Usuario logueado: {data_user['sub']}")
        return jinja2_template.TemplateResponse("dashboard.html", {"request": request, "user": data_user['sub']})
    except (InvalidTokenError, ExpiredSignatureError):
        return RedirectResponse("/login", status_code=302)
@app.post("/users/login")
def login(username: Annotated[str, Form()], password: Annotated[str, Form()]):
    user_data = get_user(username, db_users)
    if user_data is None:
        raise HTTPException(
            status_code=401,
            detail = "Username or password no authorization"
        )
    if not authenticate_user(user_data["password"], password):
        raise HTTPException(status_code=401, detail="Username or password no authorization")
    token = create_token({"sub": user_data["username"]})
    return RedirectResponse(
        "/users/dashboard",
        status_code=302,
        headers={"set-cookie": f"access_token={token}; Max-Age={TOKEN_SECONDS_EXP}"}
    )
@app.post("/users/logout")
def logout():
    return RedirectResponse("/login", status_code=302, headers={
        "set-cookie": "access_token; Max-Age:0"
    })
@app.get("/")

async def root():
    return {"message": "Hello world!"}

db_users : Any = {
    "gregory": {
        "id_user": 0,
        "username": "Gregory",
        "password": "12345#hash"
    },
    "melanie": {
        "id_user": 1,
        "username": "Melanie",
        "password": "23456#hash"
    }
}

# data : Any = [
#     {
#         "campaign_id": 1,
#         "name": "Summer Launch",
#         "due_date": datetime.now(),
#         "create_at": datetime.now()
#     },
#     {
#         "campaign_id": 2,
#         "name": "Black Friday",
#         "due_date": datetime.now(),
#         "create_at": datetime.now()
#     },
#     {
#         "campaign_id": 3,
#         "name": "Green Beard",
#         "due_date": datetime.now(),
#         "create_at": datetime.now()
#     }
# ]

# @app.get("/campaigns")
# async def read_campaigns():
#     return {"campaigns": data}

# @app.get("/campaigns/{id}")
# async def read_campaigns(id: int):
#     for campaign in data:
#         if campaign.get("campaign_id") == id:
#             return {"campaign": campaign}
#     raise HTTPException(status_code=404)

# @app.post("/campaigns")
# async def create_campaing(body: dict[str, Any]):

#     new : Any = {
#         "campaign_id": randint(100,1000),
#         "name": body.get("name"),
#         "due_date": body.get("due_date"),
#         "create_at": datetime.now()
#     }

#     data.append(new)
#     return {"campaign": new}

# @app.put("/campaigns/{id}")
# async def update_campaign(id: int, body: dict[str, Any]):

#     for index, campaign in enumerate(data):
#         if campaign.get("campaign_id") == id:
            
#             update : Any = {
#                 "campaign_id": id,
#                 "name": body.get("name"),
#                 "due_date": body.get("due_date"),
#                 "create_at": campaign.get("create_at")
#             }
#             data[index]=update
#             return {"campaign": update}
#     raise HTTPException(status_code=404)

# @app.delete("/campaign/{id}")
# async def delete_campaign(id: int, bady:dict[str,Any]):

#     for index, campaign in enumerate(data):
#         if campaign.get("campaign_id") == id:
#             data.pop(index)
#             return Response(status_code=204)
#     raise HTTPException(status_code=404)