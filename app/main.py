# app/main.py

from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/")
def read_root():
    return {"message": "Hello, Whatsapp PDF Assistant"}
    
