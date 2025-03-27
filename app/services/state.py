from pydantic import BaseModel, Field
from typing import Dict, Any, TypedDict, List, Optional, Union, Literal

# Define Message structure for better type safety
class Message(BaseModel):
    """A message in the conversation."""
    role: Literal["user", "system", "assistant"] 
    content: str

class State(BaseModel):
    """
    The complete state object for the entire workflow.
    
    This state manages document processing workflow with the following stages:
    1. Initialize context with document
    2. Validate document format/content
    3. Request user questions about the document
    4. Generate AI responses based on document context
    """
    file_path: str = ""
    messages: List[Message] = Field(default_factory=list)
    command: Optional[str] = None
    
    # Adding validation and helpful methods
    def add_message(self, role: Literal["user", "system", "assistant"], content: str) -> None:
        """Add a message to the conversation history."""
        self.messages.append(Message(role=role, content=content))
    
    def get_last_user_message(self) -> Optional[Message]:
        """Get the most recent user message if available."""
        for message in reversed(self.messages):
            if message.role == "user":
                return message
        return None

# Define UI visibility for initialize_context
class InitializeContextUI(TypedDict):
    """
    UI definition for the document initialization stage.
    
    VISIBLE FIELDS: file_path, messages
    REQUIRED FIELDS: file_path
    """
    file_path: str
    messages: List[Message]

# Define UI visibility for request_question
class RequestQuestionUI(TypedDict):
    """
    VISIBLE FIELDS: messages, file_path
    REQUIRED FIELDS: messages
    """
    messages: List[Message]
    file_path: str
    # Removed end_session as it's no longer needed

# Define UI visibility for validate_document
class ValidateDocumentUI(TypedDict):
    """
    No user interaction required at this stage
    """
    file_path: str
    document_valid: bool

# Define UI visibility for handle_invalid_document
class HandleInvalidDocumentUI(TypedDict):
    """
    No user interaction required at this stage
    """
    file_path: str
    response: str

# Define UI visibility for generate_response
class GenerateResponseUI(TypedDict):
    """
    No user interaction required at this stage
    """
    file_path: str
    messages: List[Message]

# Input/Output for each node to help with type checking
class InitializeContextInput(BaseModel):
    file_path: str = ""
    messages: List[Message] = Field(default_factory=list)

class InitializeContextOutput(BaseModel):
    file_path: str = ""
    messages: List[Message] = Field(default_factory=list)

class ValidateDocumentInput(BaseModel):
    file_path: str = ""

class ValidateDocumentOutput(BaseModel):
    file_path: str = ""
    document_valid: bool = False

class RequestQuestionInput(BaseModel):
    file_path: str = ""
    messages: List[Message] = Field(default_factory=list)

class RequestQuestionOutput(BaseModel):
    file_path: str = ""
    messages: List[Message] = Field(default_factory=list)
    command: Optional[str] = None  # Changed from end_session/switch_document booleans

class HandleInvalidDocumentInput(BaseModel):
    file_path: str = ""
    document_valid: bool = False

class HandleInvalidDocumentOutput(BaseModel):
    file_path: str = ""
    response: str = ""

class GenerateResponseInput(BaseModel):
    file_path: str = ""
    messages: List[Message] = Field(default_factory=list)

class GenerateResponseOutput(BaseModel):
    file_path: str = ""
    messages: List[Message] = Field(default_factory=list)