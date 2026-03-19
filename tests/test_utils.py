"""Tests for _utils.py."""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _utils import is_valid_filename, UNKNOWN_VALUE, DEFAULT_DATE, normalize_unicode


class TestIsValidFilename:
    def test_valid_name(self):
        assert is_valid_filename("20240315 ACME ER") is True

    def test_empty_string(self):
        assert is_valid_filename("") is False

    def test_whitespace_only(self):
        assert is_valid_filename("   ") is False

    def test_forbidden_chars(self):
        assert is_valid_filename("file<name>") is False
        assert is_valid_filename('file"name') is False
        assert is_valid_filename("file|name") is False
        assert is_valid_filename("file?name") is False
        assert is_valid_filename("file*name") is False
        assert is_valid_filename("file:name") is False
        assert is_valid_filename("file/name") is False
        assert is_valid_filename("file\\name") is False

    def test_too_long(self):
        assert is_valid_filename("a" * 256) is False
        assert is_valid_filename("a" * 255) is True

    def test_normal_chars(self):
        assert is_valid_filename("Invoice 2024 - ACME") is True
        assert is_valid_filename("Rechnung_123") is True
        assert is_valid_filename("20240315 Test Company ER") is True


class TestConstants:
    def test_unknown_value(self):
        assert UNKNOWN_VALUE == "Unknown"

    def test_default_date(self):
        assert DEFAULT_DATE == "00000000"


class TestNormalizeUnicode:
    def test_normalizes_decomposed_text_to_nfc(self):
        assert normalize_unicode("RO\u0308HRS") == "R\u00d6HRS"
