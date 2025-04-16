import pytest
from app.services.prompts import (
    get_answer_prompt,
    get_document_loaded_prompt,
    get_invalid_document_prompt,
    SYSTEM_PROMPT,
    ANSWER_TEMPLATE,
    DOCUMENT_LOADED_TEMPLATE,
    INVALID_DOCUMENT_TEMPLATE,
)
from langchain_core.prompts import ChatPromptTemplate


def test_system_prompt_content():
    assert "PDF assistant" in SYSTEM_PROMPT
    assert "document content" in SYSTEM_PROMPT


def test_answer_template_content():
    assert "{context}" in ANSWER_TEMPLATE
    assert "{question}" in ANSWER_TEMPLATE


def test_document_loaded_template_content():
    assert "{document_name}" in DOCUMENT_LOADED_TEMPLATE
    assert "{system_prompt}" in DOCUMENT_LOADED_TEMPLATE


def test_invalid_document_template_content():
    assert "{document_path}" in INVALID_DOCUMENT_TEMPLATE
    assert "{error_message}" in INVALID_DOCUMENT_TEMPLATE


def test_get_answer_prompt():
    prompt = get_answer_prompt()
    assert isinstance(prompt, ChatPromptTemplate)
    assert "context" in prompt.input_variables
    assert "question" in prompt.input_variables


def test_get_document_loaded_prompt():
    prompt = get_document_loaded_prompt()
    assert isinstance(prompt, ChatPromptTemplate)
    assert "document_name" in prompt.input_variables
    assert "system_prompt" in prompt.input_variables


def test_get_invalid_document_prompt():
    prompt = get_invalid_document_prompt()
    assert isinstance(prompt, ChatPromptTemplate)
    assert "document_path" in prompt.input_variables
    assert "error_message" in prompt.input_variables
    assert "system_prompt" in prompt.input_variables
