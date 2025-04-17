from pydantic import BaseModel, Field, field_validator, model_validator
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
    # Allow messages to be initialized as a string OR a list. Default to empty list.
    messages: Union[List[Message], str] = Field(default_factory=list)
    command: Optional[str] = None
    document_valid: Optional[bool] = None
    response: Optional[str] = None

    @model_validator(mode='after')
    def normalize_messages(self) -> 'State':
        """Ensure messages is always List[Message] after initialization."""
        if isinstance(self.messages, str):
            # If input was a string, convert it to the first user message
            initial_content = self.messages
            print(f"Validator converting initial messages string '{initial_content}' to list.")
            self.messages = [Message(role="user", content=initial_content)]
        elif self.messages is None:
             self.messages = []
        # If it was already a list, Pydantic would have validated its contents
        return self

    # Helper methods can now assume messages is List[Message]
    def add_message(
        self, role: Literal["user", "system", "assistant"], content: str
    ) -> None:
        """Add a message to the conversation history."""
        if not isinstance(self.messages, list):
             print("Warning: add_message called when messages is not a list. Resetting.")
             self.messages = []
        self.messages.append(Message(role=role, content=content))

    def get_last_user_message(self) -> Optional[Message]:
        """Get the most recent user message if available."""
        if not isinstance(self.messages, list):
             return None
        for message in reversed(self.messages):
            if message.role == "user":
                return message
        return None
