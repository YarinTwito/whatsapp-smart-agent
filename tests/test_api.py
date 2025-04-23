# test_api.py

"""Test API endpoints."""

from unittest.mock import patch, MagicMock
import pytest
import os
from app.models import Feedback, BugReport
from datetime import datetime
from fastapi import HTTPException


# Test health check endpoint
def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


# Test root endpoint
def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, Whatsapp PDF Assistant"}


# Test webhook verification for Twilio webhook
@patch("app.core.twilio_whatsapp_client.TwilioWhatsAppClient.send_message")
def test_webhook_verification(mock_send_message, client, twilio_webhook_form_data):
    """Test that Twilio webhooks are accepted"""
    # Configure mock
    mock_send_message.return_value = {"sid": "test_sid"}
    
    # Create form data for Twilio webhook
    form_data = twilio_webhook_form_data(body="test message")
    
    # Post to webhook endpoint
    response = client.post("/webhook", data=form_data)
    
    # Should be successful
    assert response.status_code == 200


# Test receiving a webhook message via Twilio
@patch("app.core.twilio_whatsapp_client.TwilioWhatsAppClient.send_message")
@patch("app.services.webhook_service.WebhookService.handle_text")
def test_webhook_message_twilio(
    mock_handle_text, mock_send_message, client, twilio_webhook_form_data
):
    # Configure mocks
    mock_send_message.return_value = {"sid": "test_sid"}
    mock_handle_text.return_value = {"status": "success"}

    # Create form data for Twilio webhook
    form_data = twilio_webhook_form_data(body="hello there")

    # Use form data for request
    response = client.post("/webhook", data=form_data)
    assert response.status_code == 200

    # Verify handle_text was called
    mock_handle_text.assert_called_once()


# Test receiving a webhook message with PDF via Twilio
@patch("app.core.twilio_whatsapp_client.TwilioWhatsAppClient.send_message")
@patch("app.services.webhook_service.WebhookService.handle_document")
def test_webhook_pdf_message_twilio(
    mock_handle_document, mock_send_message, client, twilio_webhook_media_form_data
):
    # Configure mocks
    mock_send_message.return_value = {"sid": "test_sid"}
    mock_handle_document.return_value = {"status": "success"}

    # Create form data for Twilio webhook with PDF
    form_data = twilio_webhook_media_form_data(
        media_content_type="application/pdf",
        media_url="https://api.twilio.com/media/test.pdf"
    )

    # Use form data for request
    response = client.post("/webhook", data=form_data)
    assert response.status_code == 200

    # Verify handle_document was called
    mock_handle_document.assert_called_once()


# Test receiving a webhook message with unsupported media type via Twilio
@patch("app.core.twilio_whatsapp_client.TwilioWhatsAppClient.download_media")
@patch("app.core.twilio_whatsapp_client.TwilioWhatsAppClient.send_message")
def test_webhook_unsupported_media_twilio(
    mock_send_message, mock_download_media, client, twilio_webhook_media_form_data
):
    # Configure mocks
    mock_send_message.return_value = {"sid": "test_sid"}
    mock_download_media.return_value = (b"fake image data", "test.jpg")

    # Create form data for Twilio webhook with unsupported media
    form_data = twilio_webhook_media_form_data(
        media_content_type="image/jpeg",
        media_url="https://api.twilio.com/media/test.jpg"
    )

    # Use form data for request
    response = client.post("/webhook", data=form_data)
    assert response.status_code == 200

    # Verify send_message was called with error message
    mock_send_message.assert_called_once()
    # Here we could verify the error message content if needed


# Test receiving a webhook with missing From parameter
def test_webhook_missing_from(client):
    """Test webhook requires 'From' field"""
    # Create form data without From field
    form_data = {
        "Body": "test message",
        "WaId": "1234567890"
    }
    
    # Post to webhook endpoint
    response = client.post("/webhook", data=form_data)
    
    # Should be rejected
    assert response.status_code == 400
    assert "Missing From" in response.text


# --- Admin Endpoint Tests ---


# Test getting all feedback
def test_get_all_feedback(client, mock_db_session, setup_admin_key):
    """Test getting all feedback"""
    api_key = setup_admin_key

    # Create mock feedback data
    mock_feedback = [
        Feedback(
            id=1, user_id="123", content="Great app!", submitted_at=datetime.now()
        ),
        Feedback(
            id=2,
            user_id="456",
            content="Needs improvement",
            submitted_at=datetime.now(),
        ),
    ]

    # Configure the mock session
    mock_exec = MagicMock()
    mock_exec.all.return_value = mock_feedback
    mock_db_session.exec.return_value = mock_exec

    # Make the request
    response = client.get(f"/admin/feedback?api_key={api_key}")

    # Check the response
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 2
    assert response_data[0]["content"] == "Great app!"

    # Verify database interactions
    mock_db_session.exec.assert_called_once()


# Test getting all bug reports
def test_get_all_reports(client, mock_db_session, setup_admin_key):
    """Test getting all bug reports"""
    api_key = setup_admin_key

    # Create mock report data
    mock_reports = [
        BugReport(
            id=1,
            user_id="123",
            content="Found a bug",
            status="new",
            submitted_at=datetime.now(),
        ),
        BugReport(
            id=2,
            user_id="456",
            content="Another issue",
            status="in_progress",
            submitted_at=datetime.now(),
        ),
    ]

    # Configure the mock session
    mock_exec = MagicMock()
    mock_exec.all.return_value = mock_reports
    mock_db_session.exec.return_value = mock_exec

    # Make the request
    response = client.get(f"/admin/reports?api_key={api_key}")

    # Check the response
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 2
    assert response_data[0]["content"] == "Found a bug"

    # Verify database interactions
    mock_db_session.exec.assert_called_once()


# Test updating a bug report status
def test_update_report_status(client, mock_db_session, setup_admin_key):
    """Test updating a bug report status"""
    api_key = setup_admin_key
    report_id = 1
    new_status = "in_progress"

    # Create a mock report
    mock_report = BugReport(
        id=report_id,
        user_id="123",
        content="Test bug",
        status="new",
        submitted_at=datetime.now(),
    )

    # Configure the mock session
    mock_db_session.get.return_value = mock_report

    # Make the request
    response = client.put(
        f"/admin/reports/{report_id}/status?api_key={api_key}&status={new_status}"
    )

    # Check the response
    assert response.status_code == 200
    assert response.json() == {"status": "updated"}

    # Verify the status was updated on the mock object
    assert mock_report.status == new_status

    # Verify database interactions
    mock_db_session.get.assert_called_once_with(BugReport, report_id)
    mock_db_session.add.assert_called_once_with(mock_report)
    mock_db_session.commit.assert_called_once()


# Test admin endpoints with missing API key
@pytest.mark.parametrize(
    "url_template",
    ["/admin/feedback", "/admin/reports", "/admin/reports/{report_id}/status"],
)
@patch("app.routes.admin.verify_api_key")
def test_admin_endpoints_missing_key(mock_check_api_key, client, url_template):
    """Test admin endpoints with missing API key"""
    # Replace any placeholders in the URL
    url = url_template.format(report_id=1)

    # Make requests without API key
    if "status" in url:
        response = client.put(f"{url}?status=in_progress")
    else:
        response = client.get(url)

    # FastAPI returns 422 for missing required parameters
    assert response.status_code == 422


# Test admin endpoints with invalid API key
@pytest.mark.parametrize(
    "url_template",
    ["/admin/feedback", "/admin/reports", "/admin/reports/{report_id}/status"],
)
@patch("app.routes.admin.verify_api_key")
def test_admin_endpoints_invalid_key(mock_check_api_key, client, setup_admin_key, url_template):
    """Test admin endpoints with invalid API key"""
    # Configure mock to raise appropriate exception
    mock_check_api_key.side_effect = HTTPException(status_code=403, detail="Invalid API key")
    
    # Replace any placeholders in the URL
    url = url_template.format(report_id=1)

    # Make requests with invalid API key
    if "status" in url:
        response = client.put(f"{url}?api_key=invalid_key&status=in_progress")
    else:
        response = client.get(f"{url}?api_key=invalid_key")

    # Verify API returns 403 Forbidden
    assert response.status_code == 403
    assert "Invalid API key" in response.json().get("detail", "")


# Test update report status with non-existent report
def test_update_report_status_not_found(client, mock_db_session, setup_admin_key):
    """Test updating a non-existent bug report"""
    api_key = setup_admin_key
    report_id = 999  # Non-existent ID
    new_status = "in_progress"

    # Configure the mock session to return None (not found)
    mock_db_session.get.return_value = None

    # Make the request
    response = client.put(
        f"/admin/reports/{report_id}/status?api_key={api_key}&status={new_status}"
    )

    # Should return 404 Not Found
    assert response.status_code == 404
    assert "Report not found" in response.json().get("detail", "")

    # Verify database interactions
    mock_db_session.get.assert_called_once_with(BugReport, report_id)
    # These should not be called
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()


# Test PDF upload with invalid file
def test_pdf_upload_invalid_file(client):
    response = client.post(
        "/upload-pdf", files={"file": ("test.txt", b"test content", "text/plain")}
    )
    # The endpoint now correctly returns 400 for non-PDF files
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


# Test uploading a non-PDF file
def test_upload_pdf_non_pdf_file(client):
    files = {"file": ("test.txt", b"this is text", "text/plain")}
    response = client.post("/upload-pdf", files=files)
    # The endpoint now correctly returns 400 for non-PDF files
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]
