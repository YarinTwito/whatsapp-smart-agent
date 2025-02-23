import pytest
from sqlmodel import Session, SQLModel
from app.core.database import engine, init_db, get_db
from app.models import PDFDocument

@pytest.fixture(name="session")
def session_fixture():
    """Create a fresh database and session for each test."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


def test_database_connection(session):
    """Test that we can connect to the database."""
    assert session is not None 


def test_create_pdf_document(session):
    """Test creating a PDFDocument in the database."""
    pdf_doc = PDFDocument(filename="test.pdf", content="Sample content", user_id="123")
    session.add(pdf_doc)
    session.commit()
    
    # Query the database to check if the document was added
    retrieved_doc = session.get(PDFDocument, pdf_doc.id)
    assert retrieved_doc is not None
    assert retrieved_doc.filename == "test.pdf" 


def test_read_pdf_document(session):
    """Test reading a PDFDocument from the database."""
    # Create a new PDFDocument
    pdf_doc = PDFDocument(filename="test.pdf", content="Sample content", user_id="123")
    session.add(pdf_doc)
    session.commit()
    
    # Read the document back from the database
    retrieved_doc = session.get(PDFDocument, pdf_doc.id)
    
    # Assert that the retrieved document matches the original
    assert retrieved_doc is not None
    assert retrieved_doc.filename == "test.pdf"
    assert retrieved_doc.content == "Sample content"
    assert retrieved_doc.user_id == "123"

def test_update_pdf_document(session):
    """Test updating a PDFDocument in the database."""
    pdf_doc = PDFDocument(filename="test.pdf", content="Sample content", user_id="123")
    session.add(pdf_doc)
    session.commit()
    
    # Update the document
    pdf_doc.content = "Updated content"
    session.commit()
    
    # Retrieve the updated document
    updated_doc = session.get(PDFDocument, pdf_doc.id)
    assert updated_doc.content == "Updated content"

def test_delete_pdf_document(session):
    """Test deleting a PDFDocument from the database."""
    pdf_doc = PDFDocument(filename="test.pdf", content="Sample content", user_id="123")
    session.add(pdf_doc)
    session.commit()
    
    # Delete the document
    session.delete(pdf_doc)
    session.commit()
    
    # Verify it has been deleted
    deleted_doc = session.get(PDFDocument, pdf_doc.id)
    assert deleted_doc is None 