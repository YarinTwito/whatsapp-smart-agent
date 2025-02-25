from fastapi import HTTPException
from app.core.whatsapp_client import WhatsAppClient
from app.core.pdf_processor import PDFProcessor
from app.services.langchain_service import LLMService
from sqlmodel import Session, select
from app.data_schemas import PDFDocument, ProcessedMessage
import logging
import traceback
from app.core.database import engine

class WebhookService:
    def __init__(self, whatsapp: WhatsAppClient, pdf_processor: PDFProcessor, llm_service: LLMService):
        self.whatsapp = whatsapp
        self.pdf_processor = pdf_processor
        self.llm_service = llm_service

    async def verify_webhook(self, mode: str, token: str, challenge: str, verify_token: str):
        """Verify webhook for WhatsApp API"""
        if mode and token:
            if mode == "subscribe" and token == verify_token:
                if challenge:
                    # Return the challenge value directly, not as JSON
                    return int(challenge)
                return "OK"
            raise HTTPException(status_code=403, detail="Invalid verify token")
        
        raise HTTPException(status_code=400, detail="Invalid request")

    async def handle_webhook(self, body: dict):
        """Handle incoming webhook events from WhatsApp"""
        try:
            logging.info(f"Received webhook body: {body}")

            # Add this validation check
            if not body.get("object") or body.get("object") != "whatsapp_business_account":
                raise HTTPException(status_code=400, detail="Invalid webhook body")

            message_data = await self.whatsapp.extract_message_data(body)
            if not message_data:
                return {"status": "no_message"}

            # Check if this is a status update
            if message_data.get("type") == "status":
                return {"status": "ok", "type": "status_update"}

            # Process the message based on type
            if message_data.get("type") == "document":
                return await self.handle_document(message_data)
            elif message_data.get("type") == "text":
                return await self.handle_text(message_data)
            
            return {"status": "unsupported_message_type"}

        except HTTPException:
            raise  # Re-raise HTTP exceptions
        except Exception as e:
            logging.error(f"Error in webhook: {str(e)}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))

    async def handle_document(self, message_data: dict):
        """Handle document (PDF) messages"""
        document = message_data.get("document", {})
        if document.get("mime_type") == "application/pdf":
            # Store PDF metadata in database
            with Session(engine) as session:
                pdf_doc = PDFDocument(
                    filename=document.get("filename"),
                    content="",  # Will be updated after processing
                    user_id=message_data.get("from"),
                    whatsapp_file_id=document.get("id")
                )
                session.add(pdf_doc)
                session.commit()
                
                # Add debug logging
                print(f"Stored PDF document with ID: {pdf_doc.id}")

            # Process the document with LangChain
            try:
                # Get the PDF content
                print(f"Processing document: {document}")
                pdf_content = await self.pdf_processor.download_pdf_from_whatsapp(document)
                
                # Extract text from PDF bytes
                pdf_text = self.pdf_processor.extract_text_from_bytes(pdf_content)
                
                # Process with LangChain
                with Session(engine) as session:
                    # Get the document again
                    pdf_doc = session.get(PDFDocument, pdf_doc.id)
                    if pdf_doc:
                        # Update the document content in database
                        pdf_doc.content = pdf_text  # Store the text, not the binary content
                        session.add(pdf_doc)
                        session.commit()
                        
                        # Now process with LangChain using the text
                        await self.llm_service.process_document(pdf_text, str(pdf_doc.id))
                        print(f"Successfully processed document {pdf_doc.id} with LangChain")
                        
            except Exception as e:
                print(f"Error processing document: {str(e)}")
                traceback.print_exc()  # Print full traceback
                # Continue with sending a message even if processing fails

            # Send confirmation message
            try:
                await self.whatsapp.send_message(
                    message_data["from"],
                    f"Received your PDF: {document.get('filename')}. Processing..."
                )
            except Exception as e:
                print(f"Error sending message: {str(e)}")
                traceback.print_exc()
            return {"status": "success", "type": "document"}
        return {"status": "unsupported_document_type"}

    async def handle_text(self, message_data: dict):
        """Handle text messages"""
        try:
            message_text = message_data.get("message_body", "").lower()
            user_id = message_data.get("from")
            
            # Get the latest PDF document for this user
            with Session(engine) as session:
                pdf_doc = session.exec(
                    select(PDFDocument)
                    .where(PDFDocument.user_id == user_id)
                    .order_by(PDFDocument.upload_date.desc())
                ).first()
            
            if pdf_doc and message_text:
                # Get answer from LLM
                answer = await self.llm_service.get_answer(message_text, str(pdf_doc.id))
                await self.whatsapp.send_message(user_id, answer)
            else:
                # Send default response if no PDF found
                response = f"Hi {message_data.get('name', 'there')}! 👋\nPlease send me a PDF file first."
                await self.whatsapp.send_message(user_id, response)

            return {"status": "success", "type": "text"}
        except Exception as e:
            logging.error(f"Error processing text message: {str(e)}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))

    async def process_uploaded_pdf(self, file_path: str):
        """Process an uploaded PDF file"""
        try:
            text = self.pdf_processor.extract_text(file_path)
            return {"message": "PDF processed successfully", "text_length": len(text)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) 