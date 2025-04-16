import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.models import Feedback, BugReport
from datetime import datetime
import os
from app.core.database import get_db


@pytest.fixture(autouse=True)
def setup_admin_key():
    """Set admin API key for testing"""
    # Save old value to restore later
    old_key = os.environ.get("ADMIN_API_KEY")
    # Set test key
    os.environ["ADMIN_API_KEY"] = "admin_secret_key"
    yield
    # Restore previous value
    if old_key is not None:
        os.environ["ADMIN_API_KEY"] = old_key
    else:
        del os.environ["ADMIN_API_KEY"]


def test_verify_api_key():
    from app.routes.admin import verify_api_key
    from fastapi import HTTPException

    # Test valid API key
    os.environ["ADMIN_API_KEY"] = "test_key"
    assert verify_api_key("test_key") == True

    # Test invalid API key
    with pytest.raises(HTTPException) as exc:
        verify_api_key("wrong_key")
    assert exc.value.status_code == 403
    assert "Invalid API key" in exc.value.detail


def test_get_all_feedback_without_api_key(client):
    response = client.get("/admin/feedback")
    assert response.status_code == 422


def test_get_all_feedback_invalid_api_key(client):
    response = client.get("/admin/feedback?api_key=wrong_key")
    assert response.status_code == 403


def test_get_all_feedback_empty(client):
    with patch("sqlmodel.Session") as mock_session:
        mock_session.return_value.__enter__.return_value.exec.return_value.all.return_value = (
            []
        )

        response = client.get("/admin/feedback?api_key=admin_secret_key")
        assert response.status_code == 200
        assert response.json() == []


def test_get_all_reports_empty(client):
    with patch("sqlmodel.Session") as mock_session:
        mock_session.return_value.__enter__.return_value.exec.return_value.all.return_value = (
            []
        )

        response = client.get("/admin/reports?api_key=admin_secret_key")
        assert response.status_code == 200
        assert response.json() == []


def test_update_report_nonexistent(client):
    with patch("sqlmodel.Session") as mock_session:
        # Return None for get() to simulate nonexistent report
        mock_session.return_value.__enter__.return_value.get.return_value = None

        response = client.put(
            "/admin/reports/999/status?api_key=admin_secret_key&status=resolved"
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


def test_verify_api_key_valid():
    """Test valid API key succeeds"""
    from app.routes.admin import verify_api_key
    from fastapi import HTTPException

    # Set environment variable for test
    os.environ["ADMIN_API_KEY"] = "test_key"

    # Should return True for valid key
    assert verify_api_key("test_key") is True

    # Restore environment
    del os.environ["ADMIN_API_KEY"]


def test_verify_api_key_invalid():
    """Test invalid API key fails"""
    from app.routes.admin import verify_api_key
    from fastapi import HTTPException

    # Set environment variable for test
    os.environ["ADMIN_API_KEY"] = "test_key"

    # Should raise HTTPException for invalid key
    with pytest.raises(HTTPException) as exc:
        verify_api_key("wrong_key")

    # Check the specific error code and message
    assert exc.value.status_code == 403
    assert "Invalid API key" in exc.value.detail

    # Restore environment
    del os.environ["ADMIN_API_KEY"]


def test_admin_routes_without_api_key(client):
    """Test accessing routes without API key"""
    # Feedback endpoint
    response = client.get("/admin/feedback")
    assert response.status_code == 422  # Missing required query parameter

    # Reports endpoint
    response = client.get("/admin/reports")
    assert response.status_code == 422

    # Update report endpoint
    response = client.put("/admin/reports/1/status?status=resolved")
    assert response.status_code == 422


def test_update_report_status_fully(client):
    """Test the full update process including database operation"""
    # Create a mock session
    mock_session = MagicMock()

    # Configure the mock report and session behavior
    mock_report = BugReport(id=1, user_id="123", content="Test bug", status="new")
    mock_session.get.return_value = mock_report

    # Define the dependency override function
    def override_get_db():
        yield mock_session

    # Apply the dependency override
    client.app.dependency_overrides[get_db] = override_get_db

    # Send the update request
    response = client.put(
        "/admin/reports/1/status?api_key=admin_secret_key&status=in_progress"
    )

    # Verify the response
    assert response.status_code == 200
    assert response.json() == {"status": "updated"}

    # Verify the report was updated correctly
    assert mock_report.status == "in_progress"

    # Verify database interactions
    mock_session.get.assert_called_once_with(BugReport, 1)
    mock_session.add.assert_called_once_with(mock_report)
    mock_session.commit.assert_called_once()

    # Clean up the override
    del client.app.dependency_overrides[get_db]
