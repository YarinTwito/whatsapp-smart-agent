# app/services/webhook_service.py

from fastapi import HTTPException
from fastapi.responses import PlainTextResponse
from app.core.whatsapp_client import WhatsAppClient
from app.core.pdf_processor import PDFProcessor
from app.services.langchain_service import LLMService
from sqlmodel import Session, select
from app.data_schemas import PDFDocument, ProcessedMessage, UserState, BugReport
import logging
import traceback
from app.core.database import engine
from pathlib import Path

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
                    # Return the challenge as plain text
                    return PlainTextResponse(content=challenge)
                return PlainTextResponse(content="OK")
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
            elif message_data.get("type") == "image":
                return await self.handle_image(message_data)
            
            return {"status": "unsupported_message_type"}

        except HTTPException:
            raise  # Re-raise HTTP exceptions
        except Exception as e:
            logging.error(f"Error in webhook: {str(e)}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))

    async def handle_document(self, message_data: dict):
        """Handle document (PDF) messages and reject non-PDF files"""
        document = message_data.get("document", {})
        mime_type = document.get("mime_type", "")
        filename = document.get("filename", "Unknown file")
        
        # Check if the document is a PDF
        if mime_type != "application/pdf" and not filename.lower().endswith(".pdf"):
            # Determine file extension from filename
            file_extension = Path(filename).suffix.lower() if filename else ""
            if not file_extension and "." in mime_type:
                # Try to get extension from MIME type if not in filename
                file_extension = mime_type.split("/")[-1]
            
            # Send rejection message
            await self.whatsapp.send_message(
                message_data["from"],
                f"Sorry, I can only process PDF files. I cannot accept {file_extension} files at this time."
            )
            return {"status": "error", "type": "unsupported_document_type"}
        
        # Continue with PDF processing
        try:
            await self.whatsapp.send_message(
                message_data["from"],
                f"Received your PDF: {document.get('filename')}. Processing..."
            )
        except Exception as e:
            print(f"Error sending message: {str(e)}")
            traceback.print_exc()
        
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
                    pdf_doc.content = pdf_text
                    session.add(pdf_doc)
                    session.commit()
                    
                    # Process with LangChain
                    await self.llm_service.process_document(pdf_text, str(pdf_doc.id))
                    print(f"Successfully processed document {pdf_doc.id} with LangChain")
                    
                    # Send completion message
                    await self.whatsapp.send_message(
                        message_data["from"],
                        f"I've finished processing your PDF: {document.get('filename')}! 📄✓\n\n"
                        f"You can now ask me any questions about the content.\n\n"
                        f"For example:\n"
                        f"- What is this document about?\n"
                        f"- Summarize the main points\n"
                        f"- Find information about a specific topic"
                    )
                    
        except Exception as e:
            # Send error message if processing fails
            await self.whatsapp.send_message(
                message_data["from"],
                f"Sorry, I encountered an error while processing your PDF. Please try sending it again."
            )
            print(f"Error processing document: {str(e)}")
            traceback.print_exc()

        return {"status": "success", "type": "document"}

    async def handle_text(self, message_data: dict):
        """Handle text messages"""
        try:
            message_text = message_data.get("message_body", "").lower()
            user_id = message_data.get("from")
            user_name = message_data.get("name", "there")
            
            # Check if this is a command
            if message_text.startswith("/"):
                return await self.handle_command(message_text, user_id, user_name)
            
            # Get the latest PDF document for this user
            with Session(engine) as session:
                # First check if user has an active document set
                user_state = session.exec(
                    select(UserState)
                    .where(UserState.user_id == user_id)
                ).first()
                
                # If user has an active document, use it
                pdf_doc = None
                if user_state and user_state.active_pdf_id:
                    pdf_doc = session.get(PDFDocument, user_state.active_pdf_id)
                
                # If no active document, fall back to latest
                if not pdf_doc:
                    pdf_doc = session.exec(
                        select(PDFDocument)
                        .where(PDFDocument.user_id == user_id)
                        .order_by(PDFDocument.upload_date.desc())
                    ).first()
            
            # Handle report in progress
            if user_state and user_state.state == "awaiting_report":
                # Store the report
                report = BugReport(
                    user_id=user_id,
                    user_name=user_name,
                    content=message_text,
                )
                session.add(report)
                session.commit()
                
                # Clear the state
                session.delete(user_state)
                session.commit()
                
                await self.whatsapp.send_message(
                    user_id, 
                    "Thank you for reporting this issue. We'll investigate it as soon as possible and work on a fix."
                )
                return {"status": "success", "type": "report_received"}
            
            # Normal message handling
            if pdf_doc and message_text:
                # Debug logs
                print(f"Getting answer for document: {pdf_doc.id}, filename: {pdf_doc.filename}")
                
                # Ensure the document has been processed by LangChain first
                if not pdf_doc.content:
                    await self.whatsapp.send_message(user_id, "This document hasn't been fully processed yet. Please wait a moment and try again.")
                    return {"status": "error", "type": "document_not_processed"}
                
                # Get answer from LLM - make sure we're passing the correct ID format
                answer = await self.llm_service.get_answer(message_text, str(pdf_doc.id))
                await self.whatsapp.send_message(user_id, answer["answer"])
            else:
                # Send a more helpful welcome message if no PDF found
                response = (
                    f"Hi {user_name}! 👋\n\n"
                    f"I'm your smart PDF assistant. I can help you analyze and extract information from PDF files.\n\n"
                    f"Please send me a PDF file to get started, and I'll help you understand what's inside!\n\n"
                    f"Type /help to see all available commands."
                )
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

    async def handle_command(self, command: str, user_id: str, user_name: str):
        """Handle special commands starting with /"""
        command = command.lower().strip()
        
        if command == "/help":
            help_message = (
                f"📚 *WhatsApp PDF Assistant Commands* 📚\n\n"
                f"Send a PDF file to analyze it\n\n"
                f"*Available commands:*\n"
                f"/list - Show all your uploaded PDFs\n"
                f"/latest - Select your most recent PDF\n"
                f"/report - Report a bug or issue\n"
            )
            await self.whatsapp.send_message(user_id, help_message)
            return {"status": "success", "command": "help"}
        
        elif command == "/list":
            # List all PDFs for this user
            with Session(engine) as session:
                pdf_docs = session.exec(
                    select(PDFDocument)
                    .where(PDFDocument.user_id == user_id)
                    .order_by(PDFDocument.upload_date.desc())
                ).all()
            
            if not pdf_docs:
                await self.whatsapp.send_message(user_id, "You haven't uploaded any PDFs yet.")
                return {"status": "success", "command": "list"}
            
            response = "Your PDF files:\n\n"
            for idx, doc in enumerate(pdf_docs, 1):
                # Format date as readable string
                date_str = doc.upload_date.strftime("%Y-%m-%d %H:%M")
                response += f"{idx}. {doc.filename} (uploaded on {date_str})\n"
            
            response += "\nTo select a PDF, send: /select [number]"
            await self.whatsapp.send_message(user_id, response)
            return {"status": "success", "command": "list"}
        
        elif command == "/latest":
            # Select the most recent PDF
            with Session(engine) as session:
                latest_pdf = session.exec(
                    select(PDFDocument)
                    .where(PDFDocument.user_id == user_id)
                    .order_by(PDFDocument.upload_date.desc())
                ).first()
            
            if not latest_pdf:
                await self.whatsapp.send_message(user_id, "You haven't uploaded any PDFs yet.")
                return {"status": "error", "command": "latest"}
            
            await self.whatsapp.send_message(
                user_id, 
                f"Selected your most recent PDF: {latest_pdf.filename}\n\nYou can now ask questions about this document."
            )
            return {"status": "success", "command": "latest"}
        
        elif command.startswith("/select "):
            try:
                # Extract the number from the command
                idx = int(command.split(" ")[1]) - 1
                
                with Session(engine) as session:
                    pdf_docs = session.exec(
                        select(PDFDocument)
                        .where(PDFDocument.user_id == user_id)
                        .order_by(PDFDocument.upload_date.desc())
                    ).all()
                    
                    if not pdf_docs or idx < 0 or idx >= len(pdf_docs):
                        await self.whatsapp.send_message(user_id, "Invalid selection. Please use /list to see available PDFs.")
                        return {"status": "error", "command": "select"}
                    
                    selected_pdf = pdf_docs[idx]
                    
                    # Set this as the active PDF
                    user_state = session.exec(
                        select(UserState)
                        .where(UserState.user_id == user_id)
                    ).first()
                    
                    if user_state:
                        user_state.active_pdf_id = selected_pdf.id
                        session.add(user_state)
                    else:
                        user_state = UserState(
                            user_id=user_id,
                            state="active",  # Set a default state value
                            active_pdf_id=selected_pdf.id
                        )
                        session.add(user_state)
                    session.commit()
                    
                    await self.whatsapp.send_message(
                        user_id, 
                        f"Selected PDF: {selected_pdf.filename}\nYou can now ask questions about this document."
                    )
                    return {"status": "success", "command": "select"}
                
            except (ValueError, IndexError):
                await self.whatsapp.send_message(user_id, "Invalid command format. Use: /select [number]")
                return {"status": "error", "command": "select"}
        
        elif command == "/report":
            # Set user state to awaiting report
            with Session(engine) as session:
                # Check if user already has a state
                existing_state = session.exec(
                    select(UserState)
                    .where(UserState.user_id == user_id)
                ).first()
                
                if existing_state:
                    existing_state.state = "awaiting_report"
                    session.add(existing_state)
                else:
                    user_state = UserState(
                        user_id=user_id,
                        state="awaiting_report"
                    )
                    session.add(user_state)
                session.commit()
            
            await self.whatsapp.send_message(
                user_id, 
                "I'm sorry you encountered an issue. Please describe the problem in detail, and our team will look into it."
            )
            return {"status": "success", "command": "report_started"}
        
        # Unknown command
        await self.whatsapp.send_message(
            user_id, 
            f"Sorry, I don't recognize that command. Type /help to see available commands."
        )
        return {"status": "error", "command": "unknown"}

    async def handle_image(self, message_data: dict):
        """Handle image messages with rejection response"""
        try:
            # Send rejection message
            await self.whatsapp.send_message(
                message_data["from"],
                "Sorry, I can only process PDF files. I cannot accept .jpg or other image files."
            )
            return {"status": "rejected", "type": "unsupported_file_type"}
        except Exception as e:
            logging.error(f"Error handling image message: {str(e)}")
            traceback.print_exc()
            return {"status": "error", "type": "image_handling_error"} 