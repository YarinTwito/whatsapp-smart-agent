# app/core/whatsapp_client.py

from typing import Dict, Any
import httpx
from fastapi import HTTPException
import logging
import re
import json
import os
import traceback


class WhatsAppClient:
    """Client for interacting with WhatsApp Cloud API"""

    def __init__(
        self,
        token: str,
        phone_number_id: str,
        api_version: str = "v22.0"
    ):
        """Initialize WhatsApp client with credentials"""
        self.token = token
        self.phone_number_id = phone_number_id
        self.base_url = f"https://graph.facebook.com/{api_version}/{phone_number_id}"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }


    async def _log_response(self, response: httpx.Response) -> None:
        """Log HTTP response details"""
        logging.info(f"Status: {response.status_code}")
        content_type = response.headers.get('content-type')
        if hasattr(content_type, '__await__'):  # Check if it's a coroutine
            content_type = await content_type
        logging.info(f"Content-type: {content_type}")
        
        body = response.text
        if hasattr(body, '__await__'):  # Check if it's a coroutine
            body = await body
        logging.info(f"Body: {body}")


    def _prepare_message_payload(self, to: str, message: str) -> Dict[str, Any]:
        """Prepare the message payload"""
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": message}
        }


    @staticmethod
    def process_text_for_whatsapp(text: str) -> str:
        """Process text to be WhatsApp-friendly"""
        # Remove brackets
        text = re.sub(r"\【.*?\】", "", text).strip()
        
        # Convert markdown-style bold to WhatsApp-style bold
        text = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)
        
        return text


    @staticmethod
    def is_valid_message(body: Dict[str, Any]) -> bool:
        """Check if the incoming webhook event has a valid WhatsApp message structure"""
        try:
            # Check for WhatsApp business account webhook structure
            if not (body.get("object") == "whatsapp_business_account" and body.get("entry")):
                return False
            
            # Get the first entry and its changes
            entry = body["entry"][0]
            changes = entry["changes"][0]
            value = changes["value"]
            
            # Check if this is a status update
            if value.get("statuses"):
                # Ignore status updates
                return False
            
            # Verify it's a messages notification
            if changes.get("field") != "messages" or not value.get("messages"):
                return False
            
            # Get the value containing the message
            return bool(
                value.get("messaging_product") == "whatsapp"
                and value.get("contacts")
                and value.get("messages")
                and value["messages"][0].get("type") == "text"
                and value["messages"][0].get("text", {}).get("body")
            )
        except (KeyError, IndexError):
            return False


    async def send_message(self, to: str, message: str) -> dict:
        """Send a message to a WhatsApp user."""
        try:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "text",
                "text": {
                    "preview_url": False,
                    "body": message
                }
            }

            # Use self.base_url which already has the correct path structure
            url = f"{self.base_url}/messages"
            
            print(f"Sending message to URL: {url}")
            print(f"Headers: {self.headers}")
            print(f"Payload: {payload}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload
                )
                
                print(f"Response status: {response.status_code}")
                
                # In tests, response.text is a coroutine that needs to be awaited
                if hasattr(response.text, "__await__"):
                    response_body = await response.text
                else:
                    response_body = response.text
                print(f"Response body: {response_body}")
                
                # Check specifically for token errors
                if response.status_code == 401:
                    print("Token authentication error. Check if token has expired.")
                    # Log detailed error information
                    if "Session has expired" in response_body:
                        print("ERROR: WhatsApp token has expired. Please update your token.")
                
                # Properly handle the response
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Failed to send message: {response_body}"
                    )
                    
                # Parse JSON safely
                try:
                    if isinstance(response_body, str):
                        response_data = json.loads(response_body) if response_body else {}
                    else:
                        # For tests where json() is mocked
                        response_data = await response.json()
                    return response_data
                except json.JSONDecodeError:
                    return {"success": True, "raw_response": response_body}

        except httpx.ReadTimeout:
            print(f"Timeout sending message to {to}")
            raise HTTPException(
                status_code=408,  # Request Timeout
                detail=f"Request timed out while sending message to {to}"
            )
        except Exception as e:
            print(f"Error sending message: {str(e)}")
            traceback.print_exc()  # Add traceback for debugging
            
            # Preserve the original status code for specific errors
            if isinstance(e, HTTPException):
                raise
            
            # For TimeoutException, use 408
            if isinstance(e, httpx.TimeoutException):
                raise HTTPException(
                    status_code=408,
                    detail=f"Request timed out: {str(e)}"
                )
            
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send message: {str(e)}"
            )


    async def extract_message_data(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant data from webhook message"""
        try:
            # Navigate through the webhook structure
            value = body["entry"][0]["changes"][0]["value"]
            
            # Check if this is a status update
            if value.get("statuses"):
                return {"type": "status", "status": value["statuses"][0]["status"]}
            
            # Check for messages
            if not value.get("messages"):
                return {}
            
            message = value["messages"][0]
            contact = value.get("contacts", [{}])[0]
            
            # Create base message data with common fields
            message_data = {
                "type": message.get("type"),
                "from": message.get("from"),
                "wa_id": contact.get("wa_id"),
                "name": contact.get("profile", {}).get("name"),
                "timestamp": message.get("timestamp"),
                "message_id": message.get("id"),
                "message_body": message.get("text", {}).get("body") if message.get("type") == "text" else None,
                "document": message.get("document") if message.get("type") == "document" else None
            }
            
            # Add image data if present
            if message.get("type") == "image":
                message_data["image"] = message.get("image")
            
            return message_data
        except (KeyError, IndexError) as e:
            logging.error(f"Error extracting message data: {str(e)}")
            return {}


    async def send_document(
        self,
        to: str,
        document_url: str,
        caption: str = ""
    ) -> Dict[str, Any]:
        """Send a document via WhatsApp"""
        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "document",
            "document": {
                "link": document_url,
                "caption": caption
            }
        }


        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self.headers,
                json=payload
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"WhatsApp API error: {response.text}"
            )

        return response.json() 