from fastapi import FastAPI
from db import init_db
from routes.test import router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)