from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import router as auth_router
from app.meeting import router as meeting_router

from app.database import engine, Base
from app import models


app = FastAPI(title="AI Meeting Assistant", 
              version="1.0.0", 
              description="An AI-powered meeting assistant",
              docs_url = "/docs",
              redoc_url = "/redoc",
              openapi_url = "/openapi.json")

@app.get("/")
async def read_root():
    return{"message": "Welcome to the AI Meeting Assistant API!"}

app.add_middleware(CORSMiddleware, 
                   allow_origins=["*"], 
                   allow_credentials=True, 
                   allow_methods=["*"], 
                   allow_headers=["*"]
                   )

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

app.include_router(auth_router)
app.include_router(meeting_router)

Base.metadata.create_all(bind=engine)
