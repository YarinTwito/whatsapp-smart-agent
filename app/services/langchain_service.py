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
import PyPDF2

# Import langgraph components
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt

# Import state classes
from app.services.state import State, Message

class LLMService:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        self.llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        self._vectorstores = {}
        self.workflow = self._create_workflow_graph()
        
    def initialize_context(self, state: State) -> State:
        """Initialize the context for processing"""
        print(f"Initializing context with file path: {state.file_path}")
        
        # If file_path is empty string or just "pdfs/", treat as no file path
        if not state.file_path or state.file_path == "pdfs/":
            # Clear the file path completely to be safe
            state.file_path = ""
            
            # Prompt for a file path
            new_messages = [Message(role="system", content="Please provide the path to a PDF file:")]
            
            # Use interrupt to get user input
            user_input = interrupt("user_input")
            
            if user_input:
                file_path = user_input.strip()
                # Try prefixing with pdfs/ if needed
                if not file_path.startswith('pdfs/') and not os.path.exists(file_path):
                    file_path = f"pdfs/{file_path}"
                
                return State(file_path=file_path, messages=[])
            else:
                # If no input yet, return the current state to wait for input
                return State(file_path="", messages=new_messages, command="waiting_for_file")
        
        # Normal case - we have a file path
        return state
    
    def validate_document(self, state: State) -> State:
        """Validate if the document exists and is a PDF"""
        file_path = state.file_path
        
        # Check if already processed
        if file_path in self._vectorstores:
            return State(file_path=file_path, messages=state.messages, document_valid=True)
        
        # Try prefixing with pdfs/ if needed
        if not os.path.exists(file_path) and not file_path.startswith('pdfs/'):
            file_path = f"pdfs/{file_path}"
            state = State(file_path=file_path, messages=state.messages)
        
        # Check existence and type
        if not os.path.exists(file_path):
            return State(file_path=state.file_path, messages=state.messages, document_valid=False)
            
        if not file_path.lower().endswith('.pdf'):
            return State(file_path=state.file_path, messages=state.messages, document_valid=False)
        
        # Process document
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = "".join(page.extract_text() for page in pdf_reader.pages)
            
            self.process_document_sync(text, file_path)
            return State(file_path=file_path, messages=state.messages, document_valid=True)
        except Exception as e:
            print(f"Error processing document {file_path}: {str(e)}")
            return State(file_path=file_path, messages=state.messages, document_valid=False)
    
    def handle_invalid_document(self, state: State) -> State:
        """Handle the case where the document is invalid"""
        pdf_dir = "pdfs"
        
        if os.path.exists(pdf_dir):
            pdf_files = [os.path.basename(f) for f in glob.glob(f"{pdf_dir}/*.pdf")]
            if pdf_files:
                response = f"Sorry, I couldn't find or process '{state.file_path}'. Available files: {', '.join(pdf_files)}"
            else:
                response = f"Sorry, no PDF files found in /{pdf_dir}/. Please add some PDF files."
        else:
            response = f"Sorry, the /{pdf_dir}/ directory doesn't exist. Please create it and add PDF files."
        
        new_messages = state.messages.copy()
        new_messages.append(Message(role="system", content=response))
        
        return State(file_path=state.file_path, messages=new_messages, response=response)
    
    def generate_response(self, state: State) -> State:
        """Generate response using the LLM"""
        # Handle invalid document case
        if getattr(state, 'document_valid', None) is False:
            return state
        
        # Get user question
        last_user_message = state.get_last_user_message()
        
        # If there's no user message or it's a command, don't generate a response
        if not last_user_message:
            # Just return a default document loaded message
            new_messages = state.messages.copy()
            response = "Document loaded successfully. What would you like to know about it?"
            new_messages.append(Message(role="system", content=response))
            return State(file_path=state.file_path, messages=new_messages, response=response)
        
        question = last_user_message.content
        
        # Skip command-like inputs to prevent LLM processing them
        command_phrases = ["new", "end", "quit", "exit"]
        if any(cmd in question.lower() for cmd in command_phrases):
            # Return a message asking for a real question
            new_messages = state.messages.copy()
            response = "I didn't understand that as a question. Please ask a question about the document."
            new_messages.append(Message(role="system", content=response))
            return State(file_path=state.file_path, messages=new_messages, response=response)
        
        # Get document context
        vectorstore = self._vectorstores.get(state.file_path)
        if not vectorstore:
            error_message = "Error: Document not properly loaded."
            new_messages = state.messages.copy()
            new_messages.append(Message(role="system", content=error_message))
            return State(file_path=state.file_path, messages=new_messages, response=error_message)
        
        # Retrieve content and generate response
        docs = vectorstore.as_retriever().get_relevant_documents(question)
        context = "\n\n".join([doc.page_content for doc in docs])
        
        template = """Answer the question based on the following context:
        {context}
        
        Question: {question}
        """
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm | StrOutputParser()
        response = chain.invoke({"context": context, "question": question})
        
        # Update messages
        new_messages = state.messages.copy()
        new_messages.append(Message(role="assistant", content=response))
        
        return State(file_path=state.file_path, messages=new_messages, response=response)
    
    def request_question(self, state: State) -> State:
        """Request a question from the user about the document"""
        messages = state.messages.copy()
        
        # Add system prompt if needed
        prompt = "Your document has been processed. What would you like to know about it? (To upload a new document, type 'new'. To end, type 'end')"
        if not messages or messages[-1].role == "assistant":
            messages.append(Message(role="system", content=prompt))
        
        # Get user input
        user_input = interrupt("user_input")
        
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
            
            # Try prefixing with pdfs/ if needed
            if not file_path.startswith('pdfs/') and not os.path.exists(file_path):
                file_path = f"pdfs/{file_path}"
            
            # Return state with new file path and redirect to initialize_context
            return State(file_path=file_path, messages=[], command="new") 
        
        # Handle regular question
        messages.append(Message(role="user", content=user_input))
        return State(file_path=state.file_path, messages=messages)
    
    def should_route_to_invalid_handler(self, state: State) -> str:
        """Determine routing after document validation"""
        return "handle_invalid_document" if getattr(state, 'document_valid', None) is False else "request_question"
        
    def check_next_action(self, state: State) -> str:
        """Determine the next action based on command"""
        command = getattr(state, 'command', None)
        print(f"Checking next action. Command: {command}")
        
        if command == "end":
            return "end"
        elif command == "new":
            # Go to initialize_context to get a new file
            return "initialize_context"
        elif command == "waiting_for_file":
            # Stay at initialize_context until we get a file
            return "initialize_context"
        else:
            return "generate_response"
    
    def _create_workflow_graph(self):
        """Create the workflow graph"""
        graph_builder = StateGraph(State)
        
        # Add nodes
        graph_builder.add_node("initialize_context", self.initialize_context)
        graph_builder.add_node("validate_document", self.validate_document)
        graph_builder.add_node("request_question", self.request_question)
        graph_builder.add_node("handle_invalid_document", self.handle_invalid_document)
        graph_builder.add_node("generate_response", self.generate_response)
        
        # Set up edges
        graph_builder.add_edge(START, "initialize_context")
        
        # Add conditional edge from initialize_context
        graph_builder.add_conditional_edges(
            "initialize_context",
            lambda state: "initialize_context" if getattr(state, 'command', None) == "waiting_for_file" else "validate_document",
            {
                "initialize_context": "initialize_context",
                "validate_document": "validate_document"
            }
        )
        
        # Conditional routing
        graph_builder.add_conditional_edges(
            "validate_document", 
            self.should_route_to_invalid_handler,
            {
                "request_question": "request_question",
                "handle_invalid_document": "handle_invalid_document"
            }
        )
        
        graph_builder.add_conditional_edges(
            "request_question", 
            self.check_next_action,
            {
                "generate_response": "generate_response",
                "initialize_context": "initialize_context",
                "end": END
            }
        )
        
        graph_builder.add_edge("handle_invalid_document", "generate_response")
        graph_builder.add_edge("generate_response", "request_question")
        
        return graph_builder.compile()
    
    def process_document_sync(self, text: str, file_path: str):
        """Process a document synchronously"""
        chunks = self.text_splitter.split_text(text)
        documents = [Document(page_content=chunk) for chunk in chunks]
        vectorstore = Annoy.from_documents(documents, self.embeddings)
        self._vectorstores[file_path] = vectorstore
        return vectorstore
    
    async def get_answer(self, question: str, doc_id: str):
        """Get answer for a question using the workflow"""
        initial_state = State(
            file_path=doc_id,
            messages=[Message(role="user", content=question)]
        )
        
        print("🔍 Running workflow with LangGraph...")
        result = await self.workflow.ainvoke(initial_state)
        return getattr(result, 'response', "No response generated.")

# Create service instance
llm_service = LLMService()
workflow = llm_service.workflow