# tests/test_langchain_service.py

import pytest
from app.services.langchain_service import LLMService, State, Message
from unittest.mock import patch, MagicMock
import os
from langgraph.types import interrupt
from langchain.prompts import ChatPromptTemplate
from app.services.state import State


@pytest.fixture
def llm_service():
    return LLMService()


@pytest.fixture
def sample_state():
    return State(file_path="test.pdf", messages=[Message(role="user", content="Hello")])


def test_show_welcome(llm_service):
    # Create a proper State object with messages attribute
    state = State(messages=[])

    # Test with a properly formatted State object
    result = llm_service.show_welcome(state)

    # Check the result is a dictionary with the messages key
    assert "messages" in result

    # Verify the welcome message is present
    welcome_message = result["messages"][0].content
    assert "PDF Assistant" in welcome_message


def test_route_after_validation(llm_service):
    # Test valid document
    valid_state = State(document_valid=True)
    assert llm_service.route_after_validation(valid_state) == "request_question"

    # Test invalid document
    invalid_state = State(document_valid=False)
    assert (
        llm_service.route_after_validation(invalid_state) == "handle_invalid_document"
    )


@pytest.mark.asyncio
async def test_validate_document(llm_service, tmp_path):
    # Create a test PDF file
    pdf_path = tmp_path / "test.pdf"
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4\ntest content")

    # Test valid PDF
    state = State(file_path=str(pdf_path))
    with patch("pypdf.PdfReader") as mock_reader:
        mock_reader.return_value.pages = [MagicMock()]
        mock_reader.return_value.pages[0].extract_text.return_value = "test content"
        result = llm_service.validate_document(state)
        assert result.document_valid is True

    # Test non-existent file
    state = State(file_path="nonexistent.pdf")
    result = llm_service.validate_document(state)
    assert result.document_valid is False
    assert "does not exist" in result.response

    # Test non-PDF file
    txt_path = tmp_path / "test.txt"
    txt_path.write_text("test")
    state = State(file_path=str(txt_path))
    result = llm_service.validate_document(state)
    assert result.document_valid is False
    assert "not a PDF file" in result.response


def test_handle_invalid_document(llm_service):
    # Test with error message
    state = State(file_path="test.pdf", response="Invalid file", messages=[])
    result = llm_service.handle_invalid_document(state)
    assert result.file_path == ""
    assert any(msg.content == "Invalid file" for msg in result.messages)

    # Test without error message - need to provide default message
    state = State(file_path="test.pdf", messages=[], response="")
    result = llm_service.handle_invalid_document(state)
    assert result.file_path == ""
    assert len(result.messages) > 0


def test_check_next_action(llm_service):
    # Test end command
    state = State(command="end")
    assert llm_service.check_next_action(state) == "end"

    # Test new command
    state = State(command="new")
    assert llm_service.check_next_action(state) == "initialize_context"

    # Test default case
    state = State(command=None)
    assert llm_service.check_next_action(state) == "generate_response"


def test_request_question(llm_service):
    state = State(file_path="test.pdf", messages=[])

    # Test with no input
    with patch("app.services.langchain_service.interrupt") as mock_interrupt:
        mock_interrupt.return_value = None
        result = llm_service.request_question(state)
        assert result.file_path == "test.pdf"
        assert len(result.messages) > 0

    # Test with "end" command
    with patch("app.services.langchain_service.interrupt") as mock_interrupt:
        mock_interrupt.return_value = "end"
        result = llm_service.request_question(state)
        assert result.command == "end"

    # Test with "new" command
    with patch("app.services.langchain_service.interrupt") as mock_interrupt:
        mock_interrupt.return_value = "new"
        result = llm_service.request_question(state)
        assert result.command == "new"
        assert result.file_path == ""

    # Test with regular question
    with patch("app.services.langchain_service.interrupt") as mock_interrupt:
        mock_interrupt.return_value = "What is this about?"
        result = llm_service.request_question(state)
        assert result.messages[-1].content == "What is this about?"


def test_process_document_sync(llm_service):
    # Test normal case
    text = "This is a test document"
    file_path = "test.pdf"

    with patch(
        "langchain_openai.embeddings.base.OpenAIEmbeddings.embed_documents"
    ) as mock_embed:
        mock_embed.return_value = [[0.1] * 1536]  # Mock embedding dimensions
        vectorstore = llm_service.process_document_sync(text, file_path)
        assert vectorstore is not None
        assert file_path in llm_service._vectorstores


def test_generate_response(llm_service):
    # Test with invalid document
    state = State(document_valid=False)
    result = llm_service.generate_response(state)
    assert result == state

    # Test with no user message
    state = State(document_valid=True, messages=[])
    result = llm_service.generate_response(state)
    assert result == state

    # Test with command message
    state = State(document_valid=True, messages=[Message(role="user", content="end")])
    result = llm_service.generate_response(state)
    assert result == state

    # Test with missing vectorstore
    state = State(
        document_valid=True,
        file_path="nonexistent.pdf",
        messages=[Message(role="user", content="test question")],
    )
    result = llm_service.generate_response(state)
    assert "Document not properly loaded" in result.response

    # Test successful case
    state = State(
        document_valid=True,
        file_path="test.pdf",
        messages=[Message(role="user", content="test question")],
    )
    llm_service._vectorstores["test.pdf"] = MagicMock()

    # Mock the retriever and chain response
    mock_retriever = MagicMock()
    mock_document = MagicMock()
    mock_document.page_content = "test content"
    mock_retriever.invoke.return_value = [mock_document]

    with patch.object(
        llm_service._vectorstores["test.pdf"],
        "as_retriever",
        return_value=mock_retriever,
    ):
        with patch(
            "langchain_core.output_parsers.StrOutputParser.invoke",
            return_value="Test response",
        ):
            result = llm_service.generate_response(state)
            assert result.response == "Test response"


@pytest.mark.asyncio
async def test_get_answer(llm_service):
    # Test with non-existent vectorstore - adjusted assertion to match actual error
    result = await llm_service.get_answer("test question", "nonexistent_id")
    assert "error" in result["answer"].lower()

    # Test with existing vectorstore
    llm_service._vectorstores["test_id"] = MagicMock()
    mock_retriever = MagicMock()
    mock_document = MagicMock()
    mock_document.page_content = "test content"
    mock_retriever.invoke.return_value = [mock_document]

    with patch.object(
        llm_service._vectorstores["test_id"],
        "as_retriever",
        return_value=mock_retriever,
    ):
        with patch(
            "langchain_core.output_parsers.StrOutputParser.invoke",
            return_value="Test answer",
        ):
            result = await llm_service.get_answer("test question", "test_id")
            assert result["answer"] == "Test answer"

    # Test with exception
    with patch.object(
        llm_service._vectorstores["test_id"],
        "as_retriever",
        side_effect=Exception("Test error"),
    ):
        result = await llm_service.get_answer("test question", "test_id")
        assert "error" in result["answer"].lower()


def test_initialize_context(llm_service):
    # Test without file path
    with patch("app.services.langchain_service.interrupt") as mock_interrupt:
        mock_interrupt.return_value = "test.pdf"
        state = State(file_path="", messages=[])
        result = llm_service.initialize_context(state)
        assert result.file_path == "test.pdf"

    # Test with existing file path
    state = State(file_path="already_set.pdf", messages=[])
    result = llm_service.initialize_context(state)
    assert result.file_path == "already_set.pdf"
