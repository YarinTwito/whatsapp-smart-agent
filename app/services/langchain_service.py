# app/services/langchain_service.py

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Annoy
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain.docstore.document import Document
from typing import List, Optional
import os
import glob
import pypdf
from langsmith import Client
import logging
from sqlmodel import Session
from app.core.database import engine
from app.data_schemas import PDFDocument

# Import langgraph components
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt

# Import state classes
from app.services.state import State, Message

# Import the prompts
from app.services.prompts import (
    get_answer_prompt,
    get_document_loaded_prompt,
    get_invalid_document_prompt,
    SYSTEM_PROMPT,
)


class LLMService:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        )
        openai_api_key = os.getenv("OPENAI_API_KEY")
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo", temperature=0, openai_api_key=openai_api_key
        )
        self._vectorstores = {}
        self.workflow = self._create_workflow_graph()

    def initialize_context(self, state: State) -> State:
        """Get file path from user."""
        print(f"Initializing context with file path: {state.file_path}")

        # If we don't have a file path, get one
        if not state.file_path:
            # Get user input for file path
            user_input = interrupt("awaiting_file_path")

            if user_input:
                # Keep existing messages
                new_messages = (
                    state.messages if isinstance(state.messages, list) else []
                )
                return State(file_path=user_input.strip(), messages=new_messages)
            else:
                # If no input yet, keep waiting
                return state

        # Normal case - we have a file path
        return state

    def validate_document(self, state: State) -> State:
        """Validate if the document exists and is a PDF"""
        file_path = state.file_path
        print(f"Validating document: {file_path}")

        # Default to invalid until proven valid
        is_valid = False
        error_message = None

        # Check if already processed (this is valid)
        if file_path in self._vectorstores:
            print(f"Document already processed: {file_path}")
            is_valid = True
        # Check if file exists
        elif not os.path.exists(file_path):
            error_message = f"Error: File '{file_path}' does not exist. Please provide a valid file path."
            print(error_message)
        # Check if file is a PDF
        elif not file_path.lower().endswith(".pdf"):
            error_message = f"Error: File '{file_path}' is not a PDF file. Please provide a .pdf file."
            print(error_message)
        # Try processing the document
        else:
            try:
                # Open the file
                with open(file_path, "rb") as f:
                    header = f.read(5)
                    # Check for PDF header signature
                    if header.startswith(b"%PDF-"):
                        print(
                            f"File appears to be a valid PDF based on header signature"
                        )

                        try:
                            # Import in function to avoid dependency issues
                            reader = pypdf.PdfReader(file_path)
                            page_count = len(reader.pages)
                            print(f"Successfully opened PDF with {page_count} pages")

                            sample_text = ""
                            for i in range(min(3, page_count)):
                                try:
                                    sample_text += reader.pages[i].extract_text()[
                                        :1000
                                    ]  # Limited sample
                                except:
                                    continue

                            # If we got some text, process it
                            if sample_text:
                                print(f"Successfully extracted sample text")
                                self.process_document_sync(sample_text, file_path)
                                is_valid = True
                            else:
                                print(
                                    "No text extracted, but treating PDF as valid anyway"
                                )
                                self.process_document_sync(
                                    "This PDF contains no extractable text.", file_path
                                )
                                is_valid = True

                        except Exception as e:
                            # If pypdf fails, still consider it valid but use placeholder text
                            error_message = f"Warning: PDF appears valid but couldn't extract text: {str(e)}"
                            print(error_message)
                            self.process_document_sync(
                                "This PDF could not be properly processed for text.",
                                file_path,
                            )
                            is_valid = True  # Still valid
                    else:
                        error_message = "Error: File doesn't appear to be a valid PDF (incorrect header)"
            except Exception as e:
                error_message = f"Error accessing file: {str(e)}"

        # Create new state
        new_messages = state.messages.copy()

        # If document is valid, add the success message
        if is_valid:
            document_name = os.path.basename(file_path)
            success_message = f"The document '{document_name}' has been successfully loaded and processed.\n\nWhat would you like to know about this document? You can ask me any question about its content."

            # Only add the message if it's not already there
            if not any(msg.content == success_message for msg in new_messages):
                new_messages.append(Message(role="system", content=success_message))
                print(f"Added success message for document: {document_name}")

        # Create a new State with all fields properly set
        result = State(
            file_path=file_path,
            messages=new_messages,
            document_valid=is_valid,
            response=success_message if is_valid else error_message,
        )

        return result

    def handle_invalid_document(self, state: State) -> State:
        """Handle the case where the document is invalid"""
        print(f"Handling invalid document")

        # Get the error message from validation
        error_message = getattr(
            state,
            "response",
            f"Sorry, I couldn't process '{state.file_path}'. Please provide a valid PDF file path.",
        )

        print(f"Invalid document error: {error_message}")

        # Don't add the error message again if it's already in messages
        new_messages = state.messages.copy()

        # Check if this error message is already in the messages
        error_already_in_messages = any(
            msg.role == "system" and msg.content == error_message
            for msg in new_messages
        )

        # Only add if not already there
        if not error_already_in_messages:
            new_messages.append(Message(role="system", content=error_message))

        # Reset file_path but keep the messages
        result = State(file_path="", messages=new_messages)

        return result

    def generate_response(self, state: State) -> State:
        """Generate response using the LLM"""
        # Handle invalid document case
        if getattr(state, "document_valid", None) is False:
            return state

        # Get user question
        last_user_message = state.get_last_user_message()

        # If there's no user message or it's a command, just return current state
        if not last_user_message:
            return state

        question = last_user_message.content

        # Skip command-like inputs to prevent LLM processing them
        command_phrases = ["new", "end", "quit", "exit"]
        if any(cmd in question.lower() for cmd in command_phrases):
            # Return a message asking for a real question
            return state

        # Get document context
        vectorstore = self._vectorstores.get(state.file_path)
        if not vectorstore:
            error_message = "Error: Document not properly loaded."
            return State(file_path=state.file_path, response=error_message)

        # Retrieve content and generate response
        retriever = vectorstore.as_retriever()
        docs = retriever.invoke(question)
        print(f"Retrieved {len(docs)} documents for question: {question}")
        context = "\n\n".join([doc.page_content for doc in docs])

        # Use the prompt from prompts.py
        prompt = get_answer_prompt()
        chain = prompt | self.llm | StrOutputParser()
        response = chain.invoke(
            {"system_prompt": SYSTEM_PROMPT, "context": context, "question": question}
        )

        # Check generate_response
        print(f"Generating response for question: {question}")
        # If your code reaches here without setting a response:
        return State(file_path=state.file_path, response=response)

    def request_question(self, state: State) -> State:
        """Request a question from the user about the document"""
        messages = state.messages.copy()

        # Add system prompt if needed
        prompt = "Your document has been processed. What would you like to know about it? (To upload a new document, type 'new'. To end, type 'end')"
        if not messages or messages[-1].role == "assistant":
            messages.append(Message(role="system", content=prompt))

        # Get user input
        user_input = interrupt("ask_or_new_or_end")

        if not user_input:
            return State(file_path=state.file_path, messages=messages)

        # Process user commands
        user_input_lower = user_input.strip().lower()

        # Handle exit commands
        if user_input_lower in ["end", "quit", "exit"]:
            print("End command detected")
            return State(file_path=state.file_path, messages=messages, command="end")

        # Handle "new" command - just set the command to redirect to initialize_context
        if user_input_lower == "new":
            print("New document command detected")
            # Send user back to initialize_context
            return State(file_path="", messages=[], command="new")

        # Handle file path input (PDF files)
        if user_input_lower.endswith(".pdf"):
            print(f"File path detected: {user_input}")
            file_path = user_input.strip()

            # Return state with new file path and redirect to initialize_context
            return State(file_path=file_path, messages=[], command="new")

        # Handle regular question
        messages.append(Message(role="user", content=user_input))
        return State(file_path=state.file_path, messages=messages)

    def check_next_action(self, state: State) -> str:
        """Determine the next action based on command"""
        command = getattr(state, "command", None)
        print(f"Checking next action. Command: {command}")

        if command == "end":
            return "end"
        elif command == "new":
            # Go to initialize_context to get a new file
            return "initialize_context"
        else:
            return "generate_response"

    def _create_workflow_graph(self):
        """Create the workflow graph"""
        graph_builder = StateGraph(State)

        # Add nodes
        graph_builder.add_node("show_welcome", self.show_welcome)
        graph_builder.add_node("initialize_context", self.initialize_context)
        graph_builder.add_node("validate_document", self.validate_document)
        graph_builder.add_node("request_question", self.request_question)
        graph_builder.add_node("handle_invalid_document", self.handle_invalid_document)
        graph_builder.add_node("generate_response", self.generate_response)

        # Simple direct edge from START to show_welcome
        graph_builder.add_edge(START, "show_welcome")

        # After welcome, go to initialize_context to get file path
        graph_builder.add_edge("show_welcome", "initialize_context")

        # After initialize_context, go to validate_document
        graph_builder.add_edge("initialize_context", "validate_document")

        # Conditional routing from validate_document
        graph_builder.add_conditional_edges(
            "validate_document",
            self.route_after_validation,
            {
                "request_question": "request_question",
                "handle_invalid_document": "handle_invalid_document",
            },
        )

        # From handle_invalid_document, go back to initialize_context to get a new file path
        graph_builder.add_edge("handle_invalid_document", "initialize_context")

        graph_builder.add_conditional_edges(
            "request_question",
            self.check_next_action,
            {
                "generate_response": "generate_response",
                "initialize_context": "initialize_context",
                "end": END,
            },
        )

        graph_builder.add_edge("generate_response", "request_question")

        return graph_builder.compile()

    def process_document_sync(self, text: str, file_path: str):
        """Process a document synchronously"""
        chunks = self.text_splitter.split_text(text)
        documents = [Document(page_content=chunk) for chunk in chunks]
        vectorstore = Annoy.from_documents(documents, self.embeddings)
        self._vectorstores[file_path] = vectorstore
        print(f"Vectorstore created with {len(chunks)} chunks")
        return vectorstore

    async def get_answer(self, question: str, doc_id: str):
        """Get answer for a question about a specific document"""
        try:
            # Check if vectorstore exists
            vectorstore = self._vectorstores.get(doc_id)

            # If not, try to recreate it from the stored document content
            if not vectorstore:
                with Session(engine) as session:
                    pdf_doc = session.get(PDFDocument, int(doc_id))
                    if pdf_doc and pdf_doc.content:
                        print(f"Recreating vectorstore for document: {pdf_doc.id}")
                        # Recreate the vectorstore from stored content
                        vectorstore = self.process_document_sync(
                            pdf_doc.content, str(pdf_doc.id)
                        )

            if not vectorstore:
                return {
                    "answer": "Sorry, I couldn't find or process the document you selected."
                }

            # Use vectorstore to answer question
            retriever = vectorstore.as_retriever()
            docs = retriever.invoke(question)
            context = "\n\n".join([doc.page_content for doc in docs])

            prompt = get_answer_prompt()
            chain = prompt | self.llm | StrOutputParser()
            response = chain.invoke(
                {
                    "system_prompt": SYSTEM_PROMPT,
                    "context": context,
                    "question": question,
                }
            )

            return {"answer": response}

        except Exception as e:
            logging.error(f"Error in get_answer: {str(e)}")
            return {
                "answer": f"I encountered an error while processing your question: {str(e)}"
            }

    def route_after_validation(self, state: State) -> str:
        """Explicitly determine route after document validation"""
        is_valid = getattr(state, "document_valid", False)
        print(f"Routing after validation: document_valid={is_valid}")

        if is_valid:
            return "request_question"
        else:
            return "handle_invalid_document"

    def show_welcome(self, state: State):
        """Show welcome message. Assumes state.messages is List[Message]."""
        # Validator in State should have handled initial string conversion.
        print(f"Entering show_welcome. Messages type: {type(state.messages)}")

        # Defensively check if messages is a list, though it should be.
        if not isinstance(state.messages, list):
            # Attempt recovery or raise an error
            current_messages = [
                Message(role="system", content="Yarin Twito: pdf-assistant")
            ]
        else:
            # Work with a mutable copy
            current_messages = list(state.messages)

        # Check if there's already a welcome message (to prevent duplicates on re-runs)
        welcome_already_shown = any(
            msg.role == "system" and "I'm your PDF Assistant" in msg.content
            for msg in current_messages
        )

        if not welcome_already_shown:
            # Welcome message content
            welcome_message_content = (
                "Hello! I'm your PDF Assistant. I can help you analyze and understand any PDF document.\n\n"
                "Here's what I can do:\n"
                "• Read and process PDF documents\n"
                "• Answer questions about the document content\n"
                "• Extract key information and insights\n\n"
                "To get started, please provide the path to your PDF file."
            )
            welcome_message = Message(role="system", content=welcome_message_content)

            user_message_index = next(
                (i for i, msg in enumerate(current_messages) if msg.role == "user"), -1
            )
            if user_message_index != -1:
                current_messages.insert(user_message_index, welcome_message)
            else:
                current_messages.append(welcome_message)

        # Return only the modified field(s) as a dictionary for state update
        return {"messages": current_messages}

    async def process_document(self, text: str, doc_id: str):
        """Process a document asynchronously"""
        # This method calls the sync version but in an async context
        vectorstore = self.process_document_sync(text, doc_id)
        # Store the vectorstore in the dictionary
        return vectorstore


# Create service instance
llm_service = LLMService()
workflow = llm_service.workflow
