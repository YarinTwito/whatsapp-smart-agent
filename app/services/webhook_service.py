# app/services/webhook_service.py

from fastapi import HTTPException
from fastapi.responses import PlainTextResponse
from app.core.twilio_whatsapp_client import TwilioWhatsAppClient
from app.core.pdf_processor import PDFProcessor
from app.services.langchain_service import LLMService
from sqlmodel import Session, select, delete, func
from app.data_schemas import PDFDocument, ProcessedMessage, UserState, BugReport
import logging
from app.core.database import engine
from pathlib import Path
from sqlalchemy import Column, Boolean

# Import the specific Twilio client we are using
from app.core.twilio_whatsapp_client import TwilioWhatsAppClient


class WebhookService:
    def __init__(
        self,
        # Change the type hint to the specific Twilio client
        whatsapp: TwilioWhatsAppClient,
        pdf_processor: PDFProcessor,
        llm_service: LLMService,
    ):
        self.whatsapp = whatsapp
        self.pdf_processor = pdf_processor
        self.llm_service = llm_service
        self.MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

    async def verify_webhook(
        self, mode: str, token: str, challenge: str, verify_token: str
    ):
        """Verify webhook for WhatsApp API"""
        if mode and token:
            if mode == "subscribe" and token == verify_token:
                return PlainTextResponse(content=challenge or "OK")
            raise HTTPException(status_code=403, detail="Invalid verify token")
        raise HTTPException(status_code=400, detail="Invalid request")

    async def handle_webhook(self, body: dict):
        """Handle incoming webhook events from WhatsApp"""
        try:
            logging.info(f"Received webhook body: {body}")

            # Add this validation check
            if (
                not body.get("object")
                or body.get("object") != "whatsapp_business_account"
            ):
                raise HTTPException(status_code=400, detail="Invalid webhook body")

            message_data = await self.whatsapp.extract_message_data(
                body
            )  # This might need adjustment if extract_message_data expects Meta format
            if not message_data:
                return {"status": "no_message"}

            if message_data.get("type") == "status":
                return {"status": "ok", "type": "status_update"}

            # Process message by type
            msg_type = message_data.get("type", "")
            if msg_type == "document":
                return await self.handle_document(message_data)
            elif msg_type == "text":
                return await self.handle_text(message_data)
            elif msg_type == "image":
                await self.whatsapp.send_message(
                    message_data["from"],
                    "Sorry, I can only process PDF files, not images.",
                )
                return {"status": "rejected", "type": "unsupported_file_type"}

            return {"status": "unsupported_message_type"}

        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error in webhook: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def handle_document(self, message_data: dict):
        """Handle document (PDF) messages and reject non-PDF files"""
        document = message_data["document"]
        mime_type = document["mime_type"]
        user_id = message_data["from"]

        pdf_bytes = await self.pdf_processor.download_pdf_from_whatsapp(document)

        if mime_type != "application/pdf":
            await self.whatsapp.send_message(
                user_id, "Sorry, I can only process PDF files."
            )
            return {"status": "error", "type": "unsupported_document_type"}

        # Download
        pdf_bytes = await self.pdf_processor.download_pdf_from_whatsapp(document)
        filename = document.get("filename") or "document.pdf"

        # Continue with PDF processing
        try:
            await self.whatsapp.send_message(
                user_id, f"Processing your PDF: {filename}..."
            )
            if len(pdf_bytes) > self.MAX_FILE_SIZE:
                await self.whatsapp.send_message(
                    user_id,
                    f"Sorry, the file is too large ({len(pdf_bytes)/1_048_576:.1f} MB).",
                )
                return {"status": "error", "type": "file_too_large"}

            # Check and manage file limit
            with Session(engine) as session:
                # Count user's documents
                user_docs_count = session.exec(
                    select(func.count(PDFDocument.id)).where(
                        PDFDocument.user_id == user_id
                    )
                ).one()

                # If at limit, delete oldest document
                if user_docs_count >= 10:
                    oldest_doc = session.exec(
                        select(PDFDocument)
                        .where(PDFDocument.user_id == user_id)
                        .order_by(PDFDocument.upload_date)
                        .limit(1)
                    ).first()

                    if oldest_doc:
                        session.delete(oldest_doc)
                        session.commit()
                        logging.info(
                            f"Deleted oldest document {oldest_doc.filename} for user {user_id}"
                        )

                # Store new PDF in database
                pdf_doc = PDFDocument(
                    filename=filename,
                    content="",
                    user_id=user_id,
                    whatsapp_file_id=document.get("id"),
                )
                session.add(pdf_doc)
                session.commit()
                doc_id = pdf_doc.id

            # Try processing up to 3 times
            max_retries = 2
            for attempt in range(max_retries + 1):
                try:
                    # Process the already downloaded PDF content
                    pdf_text = self.pdf_processor.extract_text_from_bytes(pdf_bytes)

                    # Update database with content
                    with Session(engine) as session:
                        pdf_doc = session.get(PDFDocument, doc_id)
                        if pdf_doc:
                            pdf_doc.content = pdf_text
                            session.add(pdf_doc)
                            session.commit()

                            await self.llm_service.process_document(
                                pdf_text, str(doc_id)
                            )

                            # Set this document as the active one for the user
                            self._set_user_state(session, user_id, "active", doc_id)

                            # Send completion message with examples
                            await self.whatsapp.send_message(
                                user_id,
                                f"I've finished processing your PDF: {filename}! 📄✓\n\n"
                                f"The document should be ready for questions now, but it might take a moment to become fully searchable.\n\n"
                                f"You can ask me things like:\n"
                                f"- What is this document about?\n"
                                f"- Summarize the main points\n"
                                f"- Find information about a specific topic",
                            )
                            return {"status": "success", "type": "document"}
                        else:
                            # Handle case where pdf_doc is somehow None after getting ID
                            logging.error(
                                f"Could not retrieve PDFDocument with id {doc_id} after creation."
                            )
                            raise Exception(
                                "Failed to retrieve PDF document from database after creation."
                            )

                except Exception as e:
                    logging.error(
                        f"Error processing document (attempt {attempt + 1}/{max_retries + 1}): {str(e)}"
                    )
                    if attempt == max_retries:
                        await self.whatsapp.send_message(
                            user_id,
                            f"Sorry, I've tried processing this PDF multiple times but encountered errors. "
                            f"Please try a different PDF file or contact support if the issue persists.",
                        )
                        raise

        except Exception as e:
            logging.error(f"Error processing document: {str(e)}")
            await self.whatsapp.send_message(
                user_id,
                f"Sorry, I encountered an error while processing your PDF. Please try sending it again.",
            )
            # Ensure we don't return a success status implicitly
            return {"status": "error", "type": "document_processing_exception"}

    async def process_uploaded_pdf(self, file_path, user_id=None):
        try:
            filename = Path(file_path).name

            with Session(engine) as session:
                pdf_doc = PDFDocument(
                    filename=filename, content="", user_id=user_id or "api_upload"
                )
                session.add(pdf_doc)
                session.commit()
                doc_id = pdf_doc.id

            with open(file_path, "rb") as f:
                pdf_content = f.read()

            pdf_text = self.pdf_processor.extract_text_from_bytes(pdf_content)

            with Session(engine) as session:
                pdf_doc = session.get(PDFDocument, doc_id)
                if pdf_doc:
                    pdf_doc.content = pdf_text
                    session.add(pdf_doc)
                    session.commit()

                    await self.llm_service.process_document(pdf_text, str(doc_id))

            return {"status": "success", "pdf_id": str(doc_id), "filename": filename}

        except Exception as e:
            logging.error(f"Error processing uploaded PDF: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"PDF processing error: {str(e)}"
            )

    async def handle_text(self, message_data: dict):
        """Handle text messages"""
        try:
            message_text = message_data.get("message_body", "").lower()
            user_id = message_data.get("from")
            user_name = message_data.get("name", "there")

            # Check if this is a command
            if message_text.startswith("/"):
                return await self.handle_command(message_text, user_id, user_name)

            # Check for special intents before proceeding to document queries
            if await self.handle_special_intent(message_text, user_id, user_name):
                return {"status": "success", "type": "intent_handled"}

            # Get active PDF and check conversation state
            with Session(engine) as session:
                user_state = session.exec(
                    select(UserState).where(UserState.user_id == user_id)
                ).first()

                # Initialize user state if none exists
                if not user_state:
                    user_state = UserState(user_id=user_id, state="new")
                    session.add(user_state)
                    session.commit()

                # If user has an active document, use it
                pdf_doc = None
                if user_state and user_state.active_pdf_id:
                    pdf_doc = session.get(PDFDocument, user_state.active_pdf_id)

                if not pdf_doc:
                    # If no active doc, try getting the latest uploaded one
                    pdf_doc = session.exec(
                        select(PDFDocument)
                        .where(PDFDocument.user_id == user_id)
                        .order_by(PDFDocument.upload_date.desc())
                    ).first()
                    # Update user state if we found a latest document
                    if pdf_doc and user_state:
                        self._set_user_state(
                            session, user_id, user_state.state, pdf_doc.id
                        )

                # Handle report
                if user_state and user_state.state == "awaiting_report":
                    report = BugReport(
                        user_id=user_id, user_name=user_name, content=message_text
                    )
                    session.add(report)
                    # Reset state after report
                    user_state.state = (
                        "active"  # Or 'welcomed' if they haven't interacted much
                    )
                    session.add(user_state)
                    # Don't delete user state, just update it
                    session.commit()

                    await self.whatsapp.send_message(
                        user_id, "Thanks for your report. We'll investigate soon."
                    )
                    return {"status": "success", "type": "report_received"}

            # Normal message handling
            if pdf_doc and message_text:
                # If we're here, the user is in an active conversation
                # Update state to "active" if it's new or welcomed
                if user_state and user_state.state in ["new", "welcomed"]:
                    self._set_user_state(session, user_id, "active", pdf_doc.id)

                # Directly ask LLMService for the answer based on the PDF
                answer = await self.llm_service.get_answer(
                    message_text, str(pdf_doc.id)
                )
                await self.whatsapp.send_message(user_id, answer["answer"])

            else:
                # Only send welcome message if state is "new"
                if user_state.state == "new":
                    # Set state to welcomed to prevent future welcome messages
                    self._set_user_state(
                        session, user_id, "welcomed"
                    )  # No active PDF yet

                    # Send welcome message
                    response = (
                        f"Hi {user_name}! 👋\n\n"
                        f"I'm your smart PDF assistant. I can help you analyze and extract information from PDF files.\n\n"
                        f"Please send me a PDF file to get started, and I'll help you understand what's inside!\n\n"
                        f"Type /help to see all available commands."
                    )
                    await self.whatsapp.send_message(user_id, response)
                else:  # State could be 'welcomed' or 'active' but pdf_doc is None
                    # If state is not new but we have no PDF, remind them to upload
                    await self.whatsapp.send_message(
                        user_id,
                        "I don't see any PDF files to analyze. Please upload a PDF file to continue, or use /list to select a previous one.",
                    )

            return {"status": "success", "type": "text"}
        except Exception as e:
            logging.error(f"Error processing text: {str(e)}")
            # Also send a message to the user in case of error during text processing
            user_id = message_data.get("from")
            if user_id:
                await self.whatsapp.send_message(
                    user_id,
                    "Sorry, I encountered an error trying to process your message. Please try again.",
                )
            raise HTTPException(status_code=500, detail=str(e))

    async def handle_special_intent(
        self, message_text: str, user_id: str, user_name: str
    ) -> bool:
        """
        Handle special user intents that aren't directly related to document questions.
        Returns True if an intent was handled, False otherwise.
        """
        # Convert to lowercase for easier matching
        text = message_text.lower()

        # Check for upload intent
        upload_patterns = [
            "upload",
            "send",
            "share",
            "new file",
            "another file",
            "different file",
            "add file",
            "attach",
        ]

        if any(pattern in text for pattern in upload_patterns):
            await self.whatsapp.send_message(
                user_id,
                "I'd be happy to help you with another file! Please send me the PDF you'd like to analyze next.",
            )
            return True

        # Check for thank you intent
        thanks_patterns = ["thank", "thanks", "appreciate", "grateful"]
        if any(pattern in text for pattern in thanks_patterns):
            await self.whatsapp.send_message(
                user_id,
                "You're welcome! Let me know if you need help with anything else regarding your documents.",
            )
            return True

        # Check for capability questions
        capability_patterns = [
            "what can you do",
            "help me",
            "your abilities",
            "your features",
            "how do you work",
        ]
        if any(pattern in text for pattern in capability_patterns):
            capabilities = (
                f"I'm your PDF assistant! Here's what I can do:\n\n"
                f"• Extract and analyze text from your PDF files\n"
                f"• Answer questions about the content\n"
                f"• Summarize key points\n"
                f"• Find specific information\n\n"
                f"Just upload a PDF and ask me anything about it!"
            )
            await self.whatsapp.send_message(user_id, capabilities)
            return True

        # No special intent detected
        return False

    async def handle_command(self, command: str, user_id: str, user_name: str):
        command = command.lower().strip()

        # Common database query for /list, /delete, /select
        async def get_pdfs():
            with Session(engine) as session:
                pdfs = session.exec(
                    select(PDFDocument)
                    .where(PDFDocument.user_id == user_id)
                    .order_by(PDFDocument.upload_date.desc())
                ).all()
                return session, pdfs

        if command == "/help":
            help_message = (
                f"📚 *WhatsApp PDF Assistant Commands* 📚\n\n"
                f"Send a PDF file to analyze it\n\n"
                f"*Available commands:*\n"
                f"/list - View your uploaded PDF files\n"
                f"/select [number] - Select a PDF to ask questions about\n"
                f"/delete [number] - Delete a PDF from your list\n"
                f"/delete_all - Delete all your PDFs\n"
                f"/report - Report a bug or issue\n"
            )
            await self.whatsapp.send_message(user_id, help_message)
            return {"status": "success", "command": "help"}

        elif command == "/list":
            session, pdfs = await get_pdfs()
            if not pdfs:
                await self.whatsapp.send_message(user_id, "No PDFs uploaded yet.")
                return {"status": "success", "command": "list"}

            response = "Your PDF files:\n\n" + "\n".join(
                f"{i}. {pdf.filename} ({pdf.upload_date.strftime('%b %d %H:%M')})"
                for i, pdf in enumerate(pdfs, 1)
            )
            await self.whatsapp.send_message(user_id, response)
            return {"status": "success", "command": "list"}

        elif command.startswith(("/delete ", "/select ")):
            try:
                idx = int(command.split(" ")[1]) - 1
                session, pdfs = await get_pdfs()

                if not pdfs or idx < 0 or idx >= len(pdfs):
                    await self.whatsapp.send_message(
                        user_id,
                        "Invalid selection. Please use /list to see available PDFs.",
                    )
                    return {"status": "error", "command": command[1:].split()[0]}

                selected_pdf = pdfs[idx]
                is_delete = command.startswith("/delete")

                if is_delete:
                    session.delete(selected_pdf)
                    self._set_user_state(session, user_id, "active", None)
                    msg = f"Deleted PDF: {selected_pdf.filename}"
                else:
                    self._set_user_state(session, user_id, "active", selected_pdf.id)
                    msg = f"Selected: {selected_pdf.filename}\nYou can now ask questions about this PDF."

                await self.whatsapp.send_message(user_id, msg)
                return {"status": "success", "command": command[1:].split()[0]}

            except (ValueError, IndexError):
                await self.whatsapp.send_message(
                    user_id,
                    f"Invalid command format. Use: {command.split()[0]} [number]",
                )
                return {"status": "error", "command": command[1:].split()[0]}

        elif command == "/delete_all":
            # Delete all PDFs for this user
            with Session(engine) as session:
                pdf_count = session.exec(
                    select(func.count())
                    .select_from(PDFDocument)
                    .where(PDFDocument.user_id == user_id)
                ).one()

                if pdf_count == 0:
                    await self.whatsapp.send_message(
                        user_id, "You haven't uploaded any PDFs yet."
                    )
                    return {"status": "success", "command": "delete_all"}

                session.exec(delete(PDFDocument).where(PDFDocument.user_id == user_id))
                self._set_user_state(session, user_id, "active", None)
                await self.whatsapp.send_message(
                    user_id, f"All your PDFs have been deleted ({pdf_count} files)."
                )
                return {"status": "success", "command": "delete_all"}

        elif command == "/report":
            with Session(engine) as session:
                self._set_user_state(session, user_id, "awaiting_report")
            await self.whatsapp.send_message(
                user_id,
                "I'm sorry you encountered an issue. Please describe the problem in detail, and our team will look into it.",
            )
            return {"status": "success", "command": "report_started"}

        await self.whatsapp.send_message(
            user_id,
            f"Sorry, I don't recognize that command. Type /help to see available commands.",
        )
        return {"status": "error", "command": "unknown"}

    def _set_user_state(self, session, user_id, state, active_pdf_id=None):
        user_state = session.exec(
            select(UserState).where(UserState.user_id == user_id)
        ).first()
        if user_state:
            user_state.state = state
            # Only update active_pdf_id if provided, otherwise keep existing
            if active_pdf_id is not None:
                user_state.active_pdf_id = active_pdf_id
            session.add(user_state)
        else:
            session.add(
                UserState(user_id=user_id, state=state, active_pdf_id=active_pdf_id)
            )
        session.commit()
