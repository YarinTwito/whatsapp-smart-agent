# app/core/whatsapp_client.py

from typing import Dict, Any
import httpx
from fastapi import HTTPException
import logging
import re
import json
import os


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
    def _log_response(self, response: httpx.Response) -> None:
        """Log HTTP response details"""
        logging.info(f"Status: {response.status_code}")
        logging.info(f"Content-type: {response.headers.get('content-type')}")
        logging.info(f"Body: {response.text}")

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

    async def send_message(self, to: str, message: str) -> Dict[str, Any]:
        """Send a text message to a WhatsApp number"""
        url = f"https://graph.facebook.com/{os.getenv('VERSION')}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.token}",  # Make sure token is being added here
            "Content-Type": "application/json"
        }
        # Debug print headers
        print(f"Using headers: {headers}")
        
        # Process the message text
        processed_message = self.process_text_for_whatsapp(message)
        payload = self._prepare_message_payload(to, processed_message)

        try:
            print(f"Sending message to URL: {url}")  # Debug 
            print(f"Headers: {headers}")  # Debug 
            print(f"Payload: {payload}")  # Debug 
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=10.0
                )
                
                print(f"Response status: {response.status_code}")  # Debug log
                print(f"Response body: {response.text}")  # Debug log
                
                self._log_response(response)
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"WhatsApp API error: {response.text}"
                    )

                return response.json()
                
        except httpx.TimeoutException as e:
            print(f"Timeout error: {str(e)}")  # Debug log
            raise HTTPException(
                status_code=408,
                detail="Request timed out while sending message"
            )
        except Exception as e:
            print(f"Error sending message: {str(e)}")  # Debug log
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
                raise HTTPException(
                    status_code=200,  # Return 200 for status updates
                    detail="Status update received"
                )
            
            message = value["messages"][0]
            contact = value["contacts"][0]
            
            return {
                "wa_id": contact["wa_id"],
                "name": contact["profile"]["name"],
                "message_body": message["text"]["body"]
            }
        except (KeyError, IndexError) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid message format: {str(e)}"
            )

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