# tests/test_database.py

import pytest
from sqlmodel import Session, SQLModel
from app.core.database import engine, init_db, get_db, DATABASE_URL, get_async_session
from app.data_schemas import PDFDocument
from app import create_app


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
    pdf_doc = PDFDocument(
        filename="test.pdf",
        content="Sample content",
        user_id="123",
        # whatsapp_file_id is optional now, no need to provide it
    )
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


def test_database_url():
    """Test database URL configuration"""
    assert DATABASE_URL.endswith("pdf_assistant.db")


def test_get_db():
    """Test database session creation and closure"""
    db_generator = get_db()
    db = next(db_generator)
    assert isinstance(db, Session)
    try:
        next(db_generator)
    except StopIteration:
        pass  # This is expected


def test_engine_configuration():
    """Test database engine configuration"""
    assert engine.url.database.endswith("pdf_assistant.db")


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before tests and drop them after"""
    SQLModel.metadata.create_all(bind=engine)
    yield
    SQLModel.metadata.drop_all(bind=engine)


@pytest.mark.asyncio
async def test_async_session():
    """Test async session management"""
    try:
        async with get_async_session() as session:
            # Test that session works
            assert session is not None
            # Add a document to verify session works
            pdf_doc = PDFDocument(filename="test.pdf", content="content", user_id="123")
            session.add(pdf_doc)
            session.commit()  # Use sync commit since we're using SQLite

            # Verify document was saved
            saved_doc = session.get(PDFDocument, pdf_doc.id)
            assert saved_doc is not None
    except Exception as e:
        pytest.fail(f"Async session failed: {str(e)}")


@pytest.mark.asyncio
async def test_async_session_rollback():
    """Test async session rollback on error"""
    with pytest.raises(Exception, match="Test error"):
        async with get_async_session() as session:
            pdf_doc = PDFDocument(filename="test.pdf", content="content", user_id="123")
            session.add(pdf_doc)
            raise Exception("Test error")


def test_init_db():
    """Test database initialization"""
    # Drop all tables first
    SQLModel.metadata.drop_all(engine)

    # Initialize DB
    init_db()

    # Verify tables were created by adding a document
    with Session(engine) as session:
        pdf_doc = PDFDocument(filename="test.pdf", content="content", user_id="123")
        session.add(pdf_doc)
        session.commit()

        # Verify document was saved
        assert session.get(PDFDocument, pdf_doc.id) is not None
