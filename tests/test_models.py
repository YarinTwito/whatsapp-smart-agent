import pytest
from datetime import datetime
from sqlmodel import Session, SQLModel, select, delete, Field
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import IntegrityError
from typing import Optional
from app.models import PDFDocument, ProcessedMessage
from app import create_app

# Create a separate test database
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Renamed fto MockPDFDocument
class MockPDFDocument(SQLModel, table=True):
    __tablename__ = "test_pdfdocument"
    
    id: int = Field(default=None, primary_key=True)
    filename: str
    content: str = ""
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    user_id: str
    whatsapp_file_id: Optional[str] = Field(default=None)
    processed: bool = Field(default=False)

# Renamed from TestProcessedMessage to MockProcessedMessage
class MockProcessedMessage(SQLModel, table=True):
    __tablename__ = "test_processedmessage"
    
    id: int = Field(default=None, primary_key=True)
    message_id: str = Field(unique=True)
    timestamp: str

@pytest.fixture(scope="session")
def setup_test_db():
    """Create tables once for all tests"""
    SQLModel.metadata.create_all(test_engine)
    yield test_engine
    SQLModel.metadata.drop_all(test_engine)

@pytest.fixture(autouse=True)
def session(setup_test_db):
    """Create a new session for each test"""
    connection = setup_test_db.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    
    # Clear any existing data
    session.exec(delete(MockPDFDocument))
    session.exec(delete(MockProcessedMessage))
    session.commit()
    
    yield session
    
    # Rollback transaction instead of committing deletes
    transaction.rollback()
    connection.close()

def test_pdf_document_creation():
    pdf = MockPDFDocument(
        filename="test.pdf",
        content="test content",
        user_id="123",
        whatsapp_file_id="456"
    )
    
    with Session(test_engine) as session:
        session.add(pdf)
        session.commit()
        session.refresh(pdf)
        
        assert pdf.id is not None
        assert pdf.filename == "test.pdf"
        assert not pdf.processed
        assert isinstance(pdf.upload_date, datetime)

def test_pdf_document_query():
    # Create multiple documents
    docs = [
        MockPDFDocument(filename=f"test{i}.pdf", content=f"content{i}", 
                   user_id="123", whatsapp_file_id=f"456{i}")
        for i in range(3)
    ]
    
    with Session(test_engine) as session:
        for doc in docs:
            session.add(doc)
        session.commit()
        
        # Query by user_id
        results = session.exec(
            select(MockPDFDocument).where(MockPDFDocument.user_id == "123")
        ).all()
        assert len(results) == 3

def test_pdf_document_update():
    pdf = MockPDFDocument(
        filename="test.pdf",
        content="initial content",
        user_id="123",
        whatsapp_file_id="456"
    )
    
    with Session(test_engine) as session:
        session.add(pdf)
        session.commit()
        
        # Update content and processed status
        pdf.content = "updated content"
        pdf.processed = True
        session.add(pdf)
        session.commit()
        
        # Verify updates
        updated = session.get(MockPDFDocument, pdf.id)
        assert updated.content == "updated content"
        assert updated.processed

def test_processed_message_creation():
    msg = MockProcessedMessage(
        message_id="test_123",
        timestamp="1234567890"
    )
    
    with Session(test_engine) as session:
        session.add(msg)
        session.commit()
        session.refresh(msg)
        
        assert msg.id is not None
        assert msg.message_id == "test_123"

def test_processed_message_unique_constraint():
    msg1 = MockProcessedMessage(message_id="test_123", timestamp="1234567890")
    msg2 = MockProcessedMessage(message_id="test_124", timestamp="1234567891")
    
    with Session(test_engine) as session:
        session.add(msg1)
        session.commit()
        
        # Try to add message with same ID
        msg3 = MockProcessedMessage(message_id="test_123", timestamp="1234567892")
        session.add(msg3)
        with pytest.raises(IntegrityError):
            session.commit()

def test_get_latest_pdf_for_user():
    # Create documents with different timestamps
    docs = [
        MockPDFDocument(filename=f"test{i}.pdf", content=f"content{i}", 
                   user_id="123", whatsapp_file_id=f"456{i}")
        for i in range(3)
    ]
    
    with Session(test_engine) as session:
        for doc in docs:
            session.add(doc)
        session.commit()
        
        # Get latest document
        latest = session.exec(
            select(MockPDFDocument)
            .where(MockPDFDocument.user_id == "123")
            .order_by(MockPDFDocument.upload_date.desc())
        ).first()
        
        assert latest.filename == "test2.pdf"

# Add the real model tests at the end
def test_real_pdf_document():
    """Test the actual PDFDocument model"""
    pdf = PDFDocument(
        filename="real_test.pdf",
        content="real test content",
        user_id="123",
        whatsapp_file_id="456"
    )
    
    with Session(test_engine) as session:
        session.add(pdf)
        session.commit()
        session.refresh(pdf)
        
        assert pdf.id is not None
        assert pdf.filename == "real_test.pdf"
        assert not pdf.processed
        assert isinstance(pdf.upload_date, datetime)

def test_real_processed_message():
    """Test the actual ProcessedMessage model"""
    msg = ProcessedMessage(
        message_id="real_test_123",
        timestamp="1234567890"
    )
    
    with Session(test_engine) as session:
        session.add(msg)
        session.commit()
        session.refresh(msg)
        
        assert msg.id is not None
        assert msg.message_id == "real_test_123"
        assert msg.timestamp == "1234567890"

def test_real_models_database_integration():
    """Test actual models with database"""
    with Session(test_engine) as session:
        # Create and save a PDF document
        pdf = PDFDocument(
            filename="real_test.pdf",
            content="real test content",
            user_id="123",
            whatsapp_file_id="456"
        )
        session.add(pdf)
        session.commit()
        
        # Query the saved document
        saved_pdf = session.get(PDFDocument, pdf.id)
        assert saved_pdf.filename == "real_test.pdf"
        assert not saved_pdf.processed

# ... add other real model tests ... 