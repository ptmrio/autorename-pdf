"""
Utility functions for filename validation and system operations.
"""

import sys
import logging
import re
import unicodedata

# Constants
UNKNOWN_VALUE = "Unknown"
DEFAULT_DATE = "00000000"


class ExitCode:
    """Process exit codes for structured CLI output."""
    SUCCESS = 0
    GENERAL_ERROR = 1
    USAGE_ERROR = 2
    CONFIG_ERROR = 3
    NO_FILES = 4
    PARTIAL_FAILURE = 5
    PROVIDER_ERROR = 10
    AUTH_ERROR = 11


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


def normalize_unicode(value: str) -> str:
    """Normalize user-visible text to NFC for stable comparisons and filenames."""
    return unicodedata.normalize("NFC", value) if isinstance(value, str) else value
