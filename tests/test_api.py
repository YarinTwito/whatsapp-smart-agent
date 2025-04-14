# test_api.py

"""Test API endpoints."""

from unittest.mock import patch, MagicMock
import pytest
import os
from app.models import Feedback, BugReport
from datetime import datetime

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

# Test webhook verification
def test_webhook_verification(client):
    verify_token = os.getenv("VERIFY_TOKEN")
    challenge = "1234"
    response = client.get("/webhook", params={
        "hub.mode": "subscribe",
        "hub.verify_token": verify_token,
        "hub.challenge": challenge
    })
    assert response.status_code == 200
    assert response.text == challenge

# Test webhook verification with invalid token
def test_webhook_verification_invalid_token(client):
    response = client.get("/webhook", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong_token",
        "hub.challenge": "1234"
    })
    assert response.status_code == 403

# Test webhook verification with invalid request (missing params)
def test_webhook_verification_invalid_request(client):
    response = client.get("/webhook")
    # FastAPI usually returns 422 for missing query params if defined
    # Adjust if your specific setup returns 400
    assert response.status_code == 422 or response.status_code == 400

# Test receiving a webhook message
@patch('app.core.whatsapp_client.WhatsAppClient.send_message')
@patch('app.services.langchain_service.LLMService.get_answer')
def test_webhook_message(mock_get_answer, mock_send_message, client, whatsapp_text_message_payload):
    # Configure mocks
    mock_send_message.return_value = {"success": True}
    mock_get_answer.return_value = "This is a test answer" # Kept in case logic changes

    # Use the fixture to create the payload
    message_payload = whatsapp_text_message_payload(text="hello there")

    response = client.post("/webhook", json=message_payload)
    assert response.status_code == 200

    # Verify send_message was called (Removed get_answer assertion)
    mock_send_message.assert_called_once()

# Test receiving an invalid webhook message
def test_webhook_message_invalid(client):
    # Use a payload that might fail Pydantic validation in the endpoint
    invalid_message = {"object": "wrong_type", "entry": [{ "id": "123", "changes": [{}]}]}
    response = client.post("/webhook", json=invalid_message)
    # Depending on validation, this could be 400 or 422
    assert response.status_code in [400, 422]

# Test receiving a status update webhook
def test_webhook_status_update(client):
    # Simplified status payload structure
    status_message = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "ACCOUNT_ID",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                          "display_phone_number": "15556078886",
                          "phone_number_id": "123456789"
                     },
                    "statuses": [{
                        "id": "wamid.TEST",
                        "status": "delivered",
                        "timestamp": "1603059201",
                        "recipient_id": "123456789"
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    response = client.post("/webhook", json=status_message)
    # Status updates should usually be accepted with 200 OK
    assert response.status_code == 200

# --- Admin Endpoint Tests ---

# Test getting all feedback
def test_get_all_feedback(client, mock_db_session, setup_admin_key):
    """Test getting all feedback"""
    api_key = setup_admin_key

    # Create mock feedback data
    mock_feedback = [
        Feedback(id=1, user_id="123", content="Great app!", submitted_at=datetime.now()),
        Feedback(id=2, user_id="456", content="Needs improvement", submitted_at=datetime.now())
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
    assert response_data[0]['content'] == "Great app!"

    # Verify database interactions
    mock_db_session.exec.assert_called_once()


# Test getting all bug reports
def test_get_all_reports(client, mock_db_session, setup_admin_key):
    """Test getting all bug reports"""
    api_key = setup_admin_key

    # Create mock report data
    mock_reports = [
        BugReport(id=1, user_id="123", content="Found a bug", status="new", submitted_at=datetime.now()),
        BugReport(id=2, user_id="456", content="Another issue", status="in_progress", submitted_at=datetime.now())
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
    assert response_data[0]['content'] == "Found a bug"

    # Verify database interactions
    mock_db_session.exec.assert_called_once()

# Test updating a bug report status
def test_update_report_status(client, mock_db_session, setup_admin_key):
    """Test updating a bug report status"""
    api_key = setup_admin_key
    report_id = 1
    new_status = "in_progress"

    # Create a mock report
    mock_report = BugReport(id=report_id, user_id="123", content="Test bug", status="new", submitted_at=datetime.now())

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
@pytest.mark.parametrize("url_template", [
    "/admin/feedback",
    "/admin/reports",
    "/admin/reports/{report_id}/status"
])
def test_admin_endpoints_missing_key(client, url_template):
    """Test admin endpoints fail without API key (expect 422)"""
    report_id = 1 # Example report ID for the status URL
    url = url_template.format(report_id=report_id)

    if "{report_id}/status" in url_template:
         # Missing api_key
         response = client.put(url, params={"status": "fixed"})
    else:
        response = client.get(url)
    assert response.status_code == 422

# Test admin endpoints with invalid API key
@pytest.mark.parametrize("url_template", [
    "/admin/feedback",
    "/admin/reports",
    "/admin/reports/{report_id}/status"
])
def test_admin_endpoints_invalid_key(client, setup_admin_key, url_template):
    """Test admin endpoints fail with invalid API key (expect 403)"""
    _ = setup_admin_key # Ensure ADMIN_API_KEY env var is set by the fixture
    report_id = 1
    url = url_template.format(report_id=report_id)
    invalid_key = "wrong_key"

    if "{report_id}/status" in url_template: # Check the template name
        response = client.put(url, params={"api_key": invalid_key, "status": "fixed"}) # Use params argument
    else:
        response = client.get(url, params={"api_key": invalid_key}) # Use params argument
    # Security dependency should catch the invalid key
    assert response.status_code == 403

# Test updating status of a non-existent report
def test_update_report_status_not_found(client, mock_db_session, setup_admin_key):
    """Test updating status of a non-existent bug report"""
    api_key = setup_admin_key
    report_id = 999
    new_status = "closed"

    # Configure mock session to return None when getting the report
    mock_db_session.get.return_value = None

    # Make the request
    response = client.put(
        f"/admin/reports/{report_id}/status?api_key={api_key}&status={new_status}"
    )

    # Check response (should be 404 Not Found)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

    # Verify database interactions
    mock_db_session.get.assert_called_once_with(BugReport, report_id)
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()