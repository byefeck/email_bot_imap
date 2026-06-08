from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI

from web.routes import router

load_dotenv(find_dotenv())

app = FastAPI(title="Email Bot — подключение почты")
app.include_router(router)
