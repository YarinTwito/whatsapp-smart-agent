# app/core/twilio_whatsapp_client.py

import asyncio, httpx
from typing import Dict, Any
from twilio.rest import Client


class TwilioWhatsAppClient:
    def __init__(self, sid: str, token: str, from_number: str):
        self._client = Client(sid, token)

        # Ensure the “from” number is in the format whatsapp:+E164
        if from_number.startswith("whatsapp:"):
            self.from_number = from_number
        else:
            # Ensure '+' is present for E.164 consistency if not already whatsapp: prefixed
            self.from_number = f"whatsapp:+{from_number.lstrip('+')}"

    async def send_message(self, to: str, message: str) -> Dict[str, Any]:
        # Normalise destination number
        to_number = to if to.startswith("whatsapp:") else f"whatsapp:+{to.lstrip('+')}"

        # Use asyncio.to_thread for the blocking Twilio SDK call
        msg = await asyncio.to_thread(
            self._client.messages.create,
            from_=self.from_number,
            to=to_number,
            body=message,
        )

        return {"sid": msg.sid}

    async def download_media(self, media_url: str) -> tuple[bytes, str]:
        auth = (self._client.username, self._client.password)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            r = await client.get(media_url, auth=auth)
            r.raise_for_status()

            fname = "document.pdf"
            dispo = r.headers.get("content-disposition", "")
            if "filename=" in dispo:
                part = dispo.split("filename=")[1]
                fname = part.split("''")[-1].strip().strip('";')

            return r.content, fname
