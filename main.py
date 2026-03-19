from datetime import datetime
from typing import Any
from fastapi import FastAPI, HTTPException

app = FastAPI(root_path="/api/v1")
@app.get("/")

async def root():
    return {"message": "Hello world!"}

data : Any = [
    {
        "campaign_id": 1,
        "name": "Summer Launch",
        "due_date": datetime.now(),
        "create_at": datetime.now()
    },
    {
        "campaign_id": 2,
        "name": "Black Friday",
        "due_date": datetime.now(),
        "create_at": datetime.now()
    },
    {
        "campaign_id": 3,
        "name": "Green Beard",
        "due_date": datetime.now(),
        "create_at": datetime.now()
    }
]

@app.get("/campaigns")
async def read_campaigns():
    return {"campaigns": data}

@app.get("/campaigns/{id}")
async def read_campaigns(id: int):
    for campaign in data:
        if campaign.get("campaign_id") == id:
            return {"campaign": campaign}
    raise HTTPException(status_code=404)