# tests/test_langchain.py

import pytest
from app.services.langchain_service import LLMService
from unittest.mock import patch, MagicMock
from langchain_core.prompts import ChatPromptTemplate

@pytest.fixture
def llm_service():
    return LLMService()

@pytest.mark.asyncio
async def test_process_document(llm_service):
    test_text = "This is a test document about AI."
    doc_id = "test_123"
    
    with patch('langchain_community.embeddings.openai.OpenAIEmbeddings.embed_documents') as mock_embed:
        mock_embed.return_value = [[0.1] * 1536]
        vectorstore = await llm_service.process_document(test_text, doc_id)
        assert vectorstore is not None

@pytest.mark.asyncio
async def test_get_answer(llm_service):
    test_question = "What is this document about?"
    doc_id = "test_123"
    
    # First process a document
    await test_process_document(llm_service)
    
    with patch('langchain_community.chat_models.ChatOpenAI.__call__') as mock_chat:
        mock_chat.return_value = "Test answer"
        answer = await llm_service.get_answer(test_question, doc_id)
        assert isinstance(answer, str) 