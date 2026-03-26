"""Pydantic response models for structured LLM outputs.

These models are used as response_format with OpenAI's parse() API
to guarantee schema-compliant responses from LLM calls.
"""
from pydantic import BaseModel


class EditResponse(BaseModel):
    """Structured response from the editor LLM call."""
    anchor: str
    replacement: str


class ValidatorFeedback(BaseModel):
    """Structured error feedback from validation failures."""
    file_path: str
    error_message: str
    line: int | None = None
    suggestion: str | None = None
