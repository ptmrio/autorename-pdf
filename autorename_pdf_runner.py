"""
Importable module exposing core functions from autorename-pdf.py.
Python can't import hyphenated filenames directly, so this bridges the gap.
"""

import importlib.util
import os
import sys

# Load the hyphenated module by file path
_spec = importlib.util.spec_from_file_location(
    "autorename_pdf",
    os.path.join(os.path.dirname(__file__), "autorename-pdf.py"),
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["autorename_pdf"] = _mod  # Register so @patch("autorename_pdf.X") works
_spec.loader.exec_module(_mod)

# Re-export key functions
process_pdf = _mod.process_pdf
collect_pdf_files = _mod.collect_pdf_files
build_parser = _mod.build_parser
setup_logging = _mod.setup_logging
get_base_directory = _mod.get_base_directory
resolve_output_format = _mod.resolve_output_format
error_exit = _mod.error_exit

# Re-export dataclasses and constants
FileResult = _mod.FileResult
BatchResult = _mod.BatchResult
ErrorResult = _mod.ErrorResult
UndoFileResult = _mod.UndoFileResult
UndoResult = _mod.UndoResult
UndoBatchListResult = _mod.UndoBatchListResult

# Re-export ExitCode from _utils (also available via autorename_pdf module)
from _utils import ExitCode
