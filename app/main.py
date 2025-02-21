# app/main.py

from fastapi import FastAPI, UploadFile, File, HTTPException
from app.core.pdf_processor import PDFProcessor

app = FastAPI()
pdf_processor = PDFProcessor()


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/")
def read_root():
    return {"message": "Hello, Whatsapp PDF Assistant"}


@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    try:
        file_path = await pdf_processor.save_pdf(file)
        text = pdf_processor.extract_text(file_path)
        return {"message": "PDF processed successfully", "text_length": len(text)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
