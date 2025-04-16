import pytest
import os
import sys
import logging
from unittest.mock import patch, MagicMock
import importlib

# No fixture needed now, we'll handle state within tests


def test_settings_defaults():
    """Test Settings defaults by patching os.getenv."""

    # Define a side effect for os.getenv to simulate unset variables
    def mock_getenv(key, default=None):
        if key == "DATABASE_URL":
            return default if default is not None else "sqlite:///./pdf_assistant.db"
        if key == "TEST_DATABASE_URL":
            return default if default is not None else "sqlite:///./test.db"
        if key == "UPLOAD_DIR":
            return default if default is not None else "uploads"
        if key == "VERSION":
            return default if default is not None else "v22.0"
        if key == "LANGCHAIN_PROJECT":
            return default if default is not None else "whatsapp-pdf-assistant"
        # For others, simulate them being unset by returning the default provided by Settings
        if key in ["WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "VERIFY_TOKEN"]:
            return default if default is not None else ""
        if key in ["OPENAI_API_KEY", "LANGCHAIN_API_KEY"]:
            return default  # Will be None if Settings provides no default
        return default  # Fallback for any other env var

    # Patch os.getenv *before* importing/instantiating Settings
    with patch("os.getenv", side_effect=mock_getenv):
        # Ensure config module is re-imported cleanly within the patch context
        if "app.core.config" in sys.modules:
            del sys.modules["app.core.config"]
        from app.core.config import Settings

        settings = Settings()

    assert settings.WHATSAPP_TOKEN == ""
    assert settings.WHATSAPP_PHONE_NUMBER_ID == ""
    assert settings.DATABASE_URL == "sqlite:///./pdf_assistant.db"
    assert settings.TEST_DATABASE_URL == "sqlite:///./test.db"
    assert settings.UPLOAD_DIR == "uploads"
    assert settings.VERIFY_TOKEN == ""
    assert settings.VERSION == "v22.0"
    assert settings.OPENAI_API_KEY is None
    assert settings.LANGCHAIN_API_KEY is None
    assert settings.LANGCHAIN_PROJECT == "whatsapp-pdf-assistant"


def test_settings_from_env():
    """Test Settings loading values by patching os.getenv."""

    # Define the specific values we want os.getenv to return
    env_values = {
        "WHATSAPP_TOKEN": "test_token",
        "WHATSAPP_PHONE_NUMBER_ID": "test_phone_id",
        "DATABASE_URL": "postgresql://user:pass@host/db",
        "TEST_DATABASE_URL": "sqlite:///./test_from_env.db",
        "UPLOAD_DIR": "test_uploads",
        "VERIFY_TOKEN": "test_verify",
        "VERSION": "v_test",
        "OPENAI_API_KEY": "test_openai_key",
        "LANGCHAIN_API_KEY": "test_lc_key",
        "LANGCHAIN_PROJECT": "test_lc_project",
    }

    def mock_getenv(key, default=None):
        return env_values.get(key, default)

    # Patch os.getenv *before* importing/instantiating Settings
    with patch("os.getenv", side_effect=mock_getenv):
        if "app.core.config" in sys.modules:
            del sys.modules["app.core.config"]
        from app.core.config import Settings

        settings = Settings()

    assert settings.WHATSAPP_TOKEN == "test_token"
    assert settings.WHATSAPP_PHONE_NUMBER_ID == "test_phone_id"
    assert settings.DATABASE_URL == "postgresql://user:pass@host/db"
    assert settings.TEST_DATABASE_URL == "sqlite:///./test_from_env.db"
    assert settings.UPLOAD_DIR == "test_uploads"
    assert settings.VERIFY_TOKEN == "test_verify"
    assert settings.VERSION == "v_test"
    assert settings.OPENAI_API_KEY == "test_openai_key"
    assert settings.LANGCHAIN_API_KEY == "test_lc_key"
    assert settings.LANGCHAIN_PROJECT == "test_lc_project"


@patch("logging.warning")
@patch("logging.error")
def test_settings_missing_critical_env(mock_log_error, mock_log_warning):
    """Test warnings and errors logged when critical env vars are missing by patching os.getenv."""

    # Simulate only critical vars being unset
    def mock_getenv(key, default=None):
        if key == "WHATSAPP_TOKEN":
            return ""  # Simulate missing
        if key == "WHATSAPP_PHONE_NUMBER_ID":
            return ""  # Simulate missing
        if key == "OPENAI_API_KEY":
            return None  # Simulate missing
        # Provide valid defaults or specific values for others to avoid warnings
        if key == "DATABASE_URL":
            return "sqlite:///./db.sqlite3"
        if key == "TEST_DATABASE_URL":
            return "sqlite:///./test.sqlite3"
        if key == "UPLOAD_DIR":
            return "uploads"
        if key == "VERIFY_TOKEN":
            return "verify_me"
        if key == "VERSION":
            return "v99.0"
        if key == "LANGCHAIN_API_KEY":
            return "lc_key_present"  # Provide value
        if key == "LANGCHAIN_PROJECT":
            return "lc_project_present"  # Provide value

        return default  # Fallback

    with patch("os.getenv", side_effect=mock_getenv):
        # No need to delete from sys.modules here, just instantiate
        from app.core.config import Settings

        settings = Settings()  # Instantiate *inside* the patch

    assert settings.WHATSAPP_TOKEN == ""
    assert settings.WHATSAPP_PHONE_NUMBER_ID == ""
    assert settings.OPENAI_API_KEY is None

    # Check that the specific logging calls we expect were made
    mock_log_warning.assert_any_call("WHATSAPP_TOKEN environment variable not set.")
    mock_log_warning.assert_any_call(
        "WHATSAPP_PHONE_NUMBER_ID environment variable not set."
    )
    # FIX: Use assert_any_call if assert_called_once fails due to multiple initializations
    mock_log_error.assert_any_call(
        "CRITICAL: OPENAI_API_KEY environment variable not set."
    )


# --- Tests for dotenv loading logic ---


@patch("dotenv.load_dotenv", create=True)
def test_dotenv_loading_success(mock_load_dotenv, monkeypatch):
    """Test successful loading of .env file."""
    monkeypatch.delenv("WEBSITE_SITE_NAME", raising=False)
    # Ensure dotenv module itself is available for patching/importing
    try:
        import dotenv
    except ImportError:
        pytest.skip("python-dotenv not installed, cannot run this test variation")

    import app.core.config

    importlib.reload(app.core.config)

    mock_load_dotenv.assert_called_once()
    call_args = mock_load_dotenv.call_args
    assert "dotenv_path" in call_args.kwargs
    assert call_args.kwargs.get("override") is True


def test_dotenv_loading_importerror(monkeypatch, capsys):
    """Test handling when python-dotenv is not installed."""
    monkeypatch.delenv("WEBSITE_SITE_NAME", raising=False)
    import app.core.config

    # Simulate ImportError during 'from dotenv import load_dotenv'
    with patch.dict(sys.modules, {"dotenv": None}):
        importlib.reload(app.core.config)

    # load_dotenv should NOT have been called, check the print output
    captured = capsys.readouterr()
    assert "python-dotenv not found" in captured.out


@patch(
    "dotenv.load_dotenv", side_effect=Exception("File permission error"), create=True
)
def test_dotenv_loading_general_exception(mock_load_dotenv, monkeypatch, capsys):
    """Test handling general exceptions during .env loading."""
    monkeypatch.delenv("WEBSITE_SITE_NAME", raising=False)
    # Ensure dotenv module itself is available for patching/importing
    try:
        import dotenv
    except ImportError:
        pytest.skip("python-dotenv not installed, cannot run this test variation")

    import app.core.config

    importlib.reload(app.core.config)

    mock_load_dotenv.assert_called_once()  # Check it was attempted
    captured = capsys.readouterr()
    assert "Error loading .env file: File permission error" in captured.out


@patch("dotenv.load_dotenv", create=True)
def test_dotenv_loading_skipped_in_cloud(mock_load_dotenv, monkeypatch):
    """Test that .env loading is skipped when WEBSITE_SITE_NAME is set."""
    monkeypatch.setenv("WEBSITE_SITE_NAME", "my-azure-app")
    # Ensure dotenv module itself is available for patching/importing
    try:
        import dotenv
    except ImportError:
        pytest.skip("python-dotenv not installed, cannot run this test variation")

    import app.core.config

    importlib.reload(app.core.config)

    mock_load_dotenv.assert_not_called()


def test_configure_logging(caplog):
    """Test that configure_logging runs and sets up basic config."""
    # Ensure config module is imported cleanly first
    if "app.core.config" in sys.modules:
        del sys.modules["app.core.config"]
    from app.core.config import configure_logging

    # Get the root logger
    root_logger = logging.getLogger()
    # Store original handlers and level
    original_handlers = root_logger.handlers[:]
    original_level = root_logger.level

    try:
        # Clear existing handlers before test
        root_logger.handlers.clear()

        # Call the function to configure logging FIRST
        configure_logging()

        # Check configuration results immediately
        assert len(root_logger.handlers) > 0
        assert root_logger.level == logging.INFO

        # FIX: Explicitly add caplog's handler after basicConfig
        # This ensures caplog captures output from the configured logger
        root_logger.addHandler(caplog.handler)

        # NOW use caplog context manager to set the level for capture
        with caplog.at_level(logging.INFO):
            # Log directly to the root logger
            root_logger.info("Test log message after config")

        # Check the captured message
        assert "Test log message after config" in caplog.text

    finally:
        # Restore original logging state
        root_logger.handlers[:] = original_handlers
        root_logger.setLevel(original_level)
        # Clean up the handler we added
        if caplog.handler in root_logger.handlers:
            root_logger.removeHandler(caplog.handler)
