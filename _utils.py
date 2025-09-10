"""
Utility functions and data models.
This module contains validation functions, data models, and general utilities.
"""

import os
import sys
import logging
import re
import ctypes
from typing import Dict, Tuple, Optional
from pydantic import BaseModel, Field

# Constants
UNKNOWN_VALUE = "Unknown"
DEFAULT_DATE = "00000000"

class DocumentResponse(BaseModel):
    """Data model for document response."""
    company_name: str = Field(..., description="Name of the company in the document")
    document_date: str = Field(..., description="Date of the document in format dd.mm.yyyy")
    document_type: str = Field(..., description="Type of the document (ER, AR, etc.)")

def is_valid_filename(filename: str) -> bool:
    """Check if a filename is valid for the filesystem."""
    forbidden_chars = r'[<>:"/\\|?*]'
    
    if re.search(forbidden_chars, filename):
        return False
    
    if not filename or filename.isspace():
        return False
    
    if len(filename) > 255:
        return False
    
    return True

def attempt_to_close_file(file_path: str) -> None:
    """Attempt to close the file if it's open (Windows-specific)."""
    if sys.platform == "win32":
        try:
            # Convert the file path to a wide character string
            file_path_wide = ctypes.c_wchar_p(file_path)
            # Attempt to close the file handle
            ctypes.windll.kernel32.CloseHandle(file_path_wide)
        except Exception as e:
            logging.warning(f"Failed to close file handle for {file_path}: {str(e)}")
