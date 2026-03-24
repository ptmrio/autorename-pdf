"""
AutoRename-PDF — AI-powered PDF renamer.
Extracts company name, date, and document type from PDFs using LLM,
renames to YYYYMMDD COMPANY DOCTYPE.pdf format.

Supports structured JSON output for programmatic consumption.
"""
from __future__ import annotations

import os
import sys
import json
import argparse
import logging
import traceback
from dataclasses import dataclass, field, asdict
from logging.handlers import RotatingFileHandler
from typing import Optional

from rich.console import Console

from _config_loader import load_yaml_config
from _ai_processing import extract_metadata
from _pdf_utils import extract_content
from _document_processing import (
    harmonize_company_name,
    parse_document_date,
    rename_invoice,
    undo_renames,
    generate_batch_id,
    list_undo_batches,
    write_empty_batch,
)
from _utils import ExitCode, normalize_unicode
from _version import VERSION


def _configure_stdio_utf8() -> None:
    """Force UTF-8 stdio so GUI sidecars can safely decode subprocess output."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except Exception:
                pass


_configure_stdio_utf8()

# Constants
PDF_EXTENSION = ".pdf"
UNDO_LOG_NAME = ".autorename-log.json"

console = Console()

# ---------------------------------------------------------------------------
# Dataclasses for structured output
# ---------------------------------------------------------------------------

@dataclass
class FileResult:
    """Result of processing a single PDF file."""
    file: str
    status: str  # "renamed", "skipped", "failed"
    new_name: Optional[str] = None
    new_path: Optional[str] = None
    error: Optional[str] = None
    company: Optional[str] = None
    date: Optional[str] = None
    doc_type: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BatchResult:
    """Result of a batch rename operation."""
    success: bool
    total: int
    renamed: int
    skipped: int
    failed: int
    files: list[FileResult] = field(default_factory=list)
    dry_run: bool = False
    batch_id: Optional[str] = None

    def to_json(self) -> str:
        d = {
            "success": self.success,
            "total": self.total,
            "renamed": self.renamed,
            "skipped": self.skipped,
            "failed": self.failed,
            "dry_run": self.dry_run,
            "batch_id": self.batch_id,
            "files": [f.to_dict() for f in self.files],
        }
        return json.dumps(d, indent=2, ensure_ascii=True)


@dataclass
class ErrorResult:
    """Structured error output."""
    success: bool = False
    error_type: str = "general_error"
    message: str = ""
    suggestion: Optional[str] = None

    def to_json(self) -> str:
        d = {
            "success": self.success,
            "error_type": self.error_type,
            "message": self.message,
            "suggestion": self.suggestion,
        }
        return json.dumps(d, indent=2, ensure_ascii=True)


@dataclass
class UndoFileResult:
    """Result of undoing a single file rename."""
    old_path: str
    new_path: str
    status: str  # "restored", "failed"
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class UndoResult:
    """Result of an undo operation."""
    success: bool
    restored: int
    failed: int
    files: list[UndoFileResult] = field(default_factory=list)
    batch_id: Optional[str] = None

    def to_json(self) -> str:
        d = {
            "success": self.success,
            "restored": self.restored,
            "failed": self.failed,
            "files": [f.to_dict() for f in self.files],
        }
        return json.dumps(d, indent=2, ensure_ascii=True)


@dataclass
class UndoBatchListResult:
    """Result of listing undo batches."""
    batches: list[dict] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps({"batches": self.batches}, indent=2, ensure_ascii=True)


# ---------------------------------------------------------------------------
# Output format detection
# ---------------------------------------------------------------------------

def resolve_output_format(args: argparse.Namespace) -> str:
    """Determine output format: 'json' or 'text'.

    Priority:
    1. Explicit --output flag always wins
    2. Frozen EXE (PyInstaller) defaults to text (context menu users)
    3. Non-TTY (piped) defaults to json
    4. TTY defaults to text
    """
    # Explicit flag
    if getattr(args, "output", None) is not None:
        return args.output

    # Frozen EXE (PyInstaller / context menu) → text
    if getattr(sys, "frozen", False):
        return "text"

    # Non-TTY (piped to another process) → json
    if not sys.stdout.isatty():
        return "json"

    # Interactive terminal → text
    return "text"


# ---------------------------------------------------------------------------
# Structured error exit
# ---------------------------------------------------------------------------

def error_exit(
    error_type: str,
    message: str,
    suggestion: str | None = None,
    exit_code: int = ExitCode.GENERAL_ERROR,
    output_format: str = "text",
) -> None:
    """Print a structured error and exit."""
    if output_format == "json":
        result = ErrorResult(
            error_type=error_type,
            message=message,
            suggestion=suggestion,
        )
        print(result.to_json())
    else:
        console.print(f"[red]{message}[/red]")
        if suggestion:
            console.print(f"[dim]{suggestion}[/dim]")
    sys.exit(exit_code)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(verbose: bool = False):
    """Configure logging to both console and file.

    In normal mode, console only shows warnings/errors (rich handles user output).
    In verbose mode, console shows all log messages.
    """
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.WARNING)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[console_handler]
    )

    # Silence noisy third-party loggers even in verbose mode
    for name in ["httpx", "httpcore", "openai", "anthropic", "instructor",
                 "pdfminer", "pdfplumber", "PIL", "urllib3", "charset_normalizer"]:
        logging.getLogger(name).setLevel(logging.WARNING)

    # File handler (rotating log)
    if sys.platform == "win32":
        log_base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    else:
        log_base = os.path.join(os.path.expanduser("~"), ".local", "share")
    log_dir = os.path.join(log_base, "autorename-pdf")
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "autorename.log")

        file_handler = RotatingFileHandler(
            log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(file_handler)
    except OSError as e:
        logging.warning(f"File logging disabled: {e}")


# ---------------------------------------------------------------------------
# Base directory
# ---------------------------------------------------------------------------

def get_base_directory(config_path: str | None = None):
    """Get the base directory for config files.

    If --config is provided, use its parent directory.
    Otherwise, use the directory containing the executable (frozen)
    or the script file (development).
    """
    if config_path:
        return os.path.dirname(os.path.abspath(config_path))

    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# File collection
# ---------------------------------------------------------------------------

def collect_pdf_files(input_paths: list, recursive: bool = False) -> list:
    """Collect all PDF files from input paths."""
    pdf_files = []
    for input_path in input_paths:
        # Strip trailing quotes/backslashes mangled by Windows shell escaping
        # e.g. "C:\folder\" becomes C:\folder" due to \" escape
        input_path = normalize_unicode(input_path.strip('"').rstrip('\\').rstrip('/'))
        if os.path.isfile(input_path):
            if input_path.lower().endswith(PDF_EXTENSION):
                pdf_files.append(input_path)
            else:
                logging.warning(f"Not a PDF: {input_path}")
        elif os.path.isdir(input_path):
            if recursive:
                for root, _, files in os.walk(input_path):
                    for f in files:
                        if f.lower().endswith(PDF_EXTENSION):
                            pdf_files.append(os.path.join(root, f))
            else:
                for f in os.listdir(input_path):
                    fp = os.path.join(input_path, f)
                    if os.path.isfile(fp) and f.lower().endswith(PDF_EXTENSION):
                        pdf_files.append(fp)
        else:
            logging.error(f"Not a valid file or folder: {input_path}")
    return pdf_files


# ---------------------------------------------------------------------------
# Rich output helpers
# ---------------------------------------------------------------------------

def _step(con: Console, icon: str, color: str, msg: str, detail: str = ""):
    """Print a processing step: icon + message + optional dim detail."""
    detail_str = f" [dim]{detail}[/]" if detail else ""
    con.print(f"  [{color}]{icon}[/] {msg}{detail_str}")


# ---------------------------------------------------------------------------
# Core PDF processing
# ---------------------------------------------------------------------------

def process_pdf(
    pdf_path: str,
    config: dict,
    yaml_path: str,
    undo_log_path: str,
    dry_run: bool = False,
    output: Console | None = None,
    batch_id: str = None,
) -> FileResult:
    """Process a single PDF file. Returns a FileResult with status and metadata."""
    logging.info(f"Processing {pdf_path}")
    provider = config["ai"]["provider"]
    model = config["ai"]["model"]

    result = FileResult(
        file=normalize_unicode(os.path.abspath(pdf_path).replace("\\", "/")),
        status="failed",
        provider=provider,
        model=model,
    )

    try:
        # Step 1: Extract content
        extraction = extract_content(pdf_path, config)
        logging.info(f"Sources: {extraction.sources} | Quality: {extraction.quality_score:.2f}")

        if output:
            q = f"{extraction.quality_score:.2f}"
            _step(output, "\u2713", "green", "Text extracted", f"quality {q}")
            if "ocr" in extraction.sources:
                _step(output, "\u2713", "green", "PaddleOCR")
            if "vision" in extraction.sources:
                _step(output, "\u2713", "green", "Vision", "page images")

        if not extraction.text.strip() and not extraction.images:
            logging.warning(f"No content extracted from {pdf_path}")
            if output:
                _step(output, "\u2717", "red", "No content extracted")
            result.error = "No content extracted"
            return result

        # Step 2: AI metadata extraction
        metadata = extract_metadata(extraction, config)
        if metadata is None:
            logging.warning(f"Could not extract metadata from {pdf_path}")
            if output:
                _step(output, "\u2717", "red", "AI returned no metadata")
            result.error = "AI returned no metadata"
            return result

        if output:
            _step(output, "\u2713", "green", "AI", f"{provider} / {model}")

        # Step 3: Harmonize + rename
        company_name = harmonize_company_name(metadata.company_name, yaml_path, config)
        parsed_date = parse_document_date(metadata.document_date)

        result.company = company_name
        result.date = parsed_date.isoformat() if parsed_date else None
        result.doc_type = metadata.document_type

        rename_result = rename_invoice(
            pdf_path, company_name, parsed_date, metadata.document_type,
            config, undo_log_path=undo_log_path, batch_id=batch_id, dry_run=dry_run,
        )

        if rename_result is None:
            if output:
                _step(output, "\u00b7", "dim", "Already named correctly")
            result.status = "skipped"
            return result

        new_name = os.path.basename(rename_result)
        result.status = "renamed"
        result.new_name = new_name
        result.new_path = os.path.abspath(rename_result).replace("\\", "/")

        if output:
            arrow = "~" if dry_run else "\u2192"
            _step(output, arrow, "cyan", new_name)
        return result

    except Exception as e:
        logging.error(f"Error processing {pdf_path}: {e}")
        logging.debug(traceback.format_exc())
        if output:
            _step(output, "\u2717", "red", str(e))
        result.error = str(e)
        return result


# ---------------------------------------------------------------------------
# Argument parser with subcommands
# ---------------------------------------------------------------------------

_KNOWN_SUBCOMMANDS = {"rename", "undo", "config"}

EPILOG = """\
examples:
  autorename-pdf invoice.pdf                Rename a single PDF
  autorename-pdf *.pdf --dry-run            Preview renames without changes
  autorename-pdf ./invoices -r              Recursively process a folder
  autorename-pdf -o json *.pdf              JSON output (for scripting)
  autorename-pdf undo                       Reverse last rename in current dir
  autorename-pdf config show                Show current config (keys redacted)
  autorename-pdf config validate            Validate config file
"""


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="autorename-pdf",
        description=(
            "AI-powered PDF auto-renamer. Extracts company name, date, and "
            "document type from PDFs using an LLM, renames files to "
            "YYYYMMDD COMPANY DOCTYPE.pdf format.\n\n"
            "Supports --output json for structured output suitable for "
            "scripting and GUI integration."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')

    # Global options
    parser.add_argument(
        "--output", "-o", choices=["text", "json"], default=None,
        help="Output format (default: auto-detect based on TTY)"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress non-essential output"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show detailed processing info"
    )
    parser.add_argument(
        "--config", dest="config_path", type=str, default=None,
        help="Path to config.yaml (default: auto-detect from exe/script dir)"
    )
    # Legacy --undo flag (deprecated, use `undo` subcommand)
    parser.add_argument(
        "--undo", action="store_true", default=False,
        help=argparse.SUPPRESS,  # hidden, deprecated
    )

    # Shared options that can appear before OR after the subcommand.
    # argparse only parses parent-level flags before the subcommand,
    # so we add them to each subparser too for flexibility.
    _shared = argparse.ArgumentParser(add_help=False)
    _shared.add_argument(
        "--output", "-o", choices=["text", "json"], default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    _shared.add_argument("--quiet", "-q", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    _shared.add_argument("--verbose", "-v", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    _shared.add_argument("--config", dest="config_path", type=str, default=argparse.SUPPRESS, help=argparse.SUPPRESS)

    subparsers = parser.add_subparsers(dest="subcommand")

    # --- rename subcommand ---
    rename_parser = subparsers.add_parser(
        "rename",
        parents=[_shared],
        help="Rename PDF files (default subcommand)",
        description="Rename PDF files using AI-extracted metadata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    rename_parser.add_argument(
        "paths", nargs="*", default=[],
        help="PDF files or folders to process"
    )
    rename_parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be renamed without doing it"
    )
    rename_parser.add_argument(
        "--recursive", "-r", action="store_true",
        help="Process folders recursively"
    )
    rename_parser.add_argument(
        "--provider", type=str, default=None,
        help="Override AI provider from config"
    )
    rename_parser.add_argument(
        "--model", type=str, default=None,
        help="Override model from config"
    )
    rename_parser.add_argument(
        "--vision", action="store_true",
        help="Enable vision (send page images to LLM alongside text)"
    )
    rename_parser.add_argument(
        "--text-only", action="store_true",
        help="Disable OCR and vision (text extraction only)"
    )
    rename_parser.add_argument(
        "--ocr", action="store_true",
        help="Enable PaddleOCR (requires installation via setup.ps1)"
    )

    # --- undo subcommand ---
    undo_parser = subparsers.add_parser(
        "undo",
        parents=[_shared],
        help="Reverse the last rename operation",
        description="Reverse file renames using the undo log in the current directory.",
    )
    undo_parser.add_argument(
        "directory", nargs="?", default=None,
        help="Directory containing the undo log (default: current directory)"
    )
    undo_parser.add_argument(
        "--list", action="store_true", dest="list_batches",
        help="List available undo batches without undoing"
    )
    undo_parser.add_argument(
        "--batch", type=str, default=None,
        help="Undo a specific batch by ID"
    )
    undo_parser.add_argument(
        "--all", action="store_true", dest="undo_all",
        help="Undo all batches (not just the last one)"
    )

    # --- config subcommand ---
    config_parser = subparsers.add_parser(
        "config",
        parents=[_shared],
        help="Show or validate configuration",
        description="Inspect and validate the configuration file.",
    )
    config_sub = config_parser.add_subparsers(dest="config_action")

    config_sub.add_parser(
        "show",
        parents=[_shared],
        help="Display current configuration (API keys redacted)",
    )
    config_sub.add_parser(
        "validate",
        parents=[_shared],
        help="Validate configuration and report issues",
    )

    return parser


def _preprocess_argv(argv: list[str] | None = None) -> list[str]:
    """Preprocess sys.argv to inject 'rename' subcommand when needed.

    If no known subcommand is found among the arguments, prepend 'rename'
    so that `autorename-pdf file.pdf` and `autorename-pdf -o json file.pdf`
    both work as expected.
    """
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        return argv

    # Check if any argument is a known subcommand
    # We need to skip flags and their values to find positional args
    _FLAGS_WITH_VALUE = {"--output", "-o", "--config"}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in _FLAGS_WITH_VALUE:
            i += 2  # skip flag and its value
            continue
        if arg.startswith("-"):
            i += 1  # skip boolean flags
            continue
        # Found a positional argument
        if arg in _KNOWN_SUBCOMMANDS:
            return argv  # subcommand already present
        else:
            # First positional is not a subcommand — inject 'rename'
            return argv[:i] + ["rename"] + argv[i:]

    # All args were flags (e.g. --undo, --verbose) — pass through
    return argv


# ---------------------------------------------------------------------------
# Config subcommand handlers
# ---------------------------------------------------------------------------

def _redact_config(config: dict) -> dict:
    """Deep-copy config with sensitive values redacted."""
    import copy
    redacted = copy.deepcopy(config)
    ai = redacted.get("ai", {})
    if ai.get("api_key"):
        key = ai["api_key"]
        if len(key) > 8:
            ai["api_key"] = key[:4] + "..." + key[-4:]
        else:
            ai["api_key"] = "***"
    return redacted


def _validate_config(config: dict | None, config_path: str) -> dict:
    """Validate config and return a dict with issues."""
    issues = []

    if config is None:
        issues.append({
            "field": "config_file",
            "level": "error",
            "message": f"Config file not found: {config_path}",
        })
        return {"valid": False, "issues": issues}

    # Check required fields
    ai = config.get("ai", {})
    provider = ai.get("provider", "")
    api_key = ai.get("api_key", "")

    if not provider:
        issues.append({
            "field": "ai.provider",
            "level": "error",
            "message": "AI provider not set",
        })

    if provider != "ollama" and not api_key:
        issues.append({
            "field": "ai.api_key",
            "level": "error",
            "message": "API key required for non-ollama providers",
        })

    if not ai.get("model"):
        issues.append({
            "field": "ai.model",
            "level": "warning",
            "message": "No model specified, will use provider default",
        })

    company_name = config.get("company", {}).get("name", "")
    if not company_name or company_name == "Your Company Name":
        issues.append({
            "field": "company.name",
            "level": "warning",
            "message": "Company name not configured. AI cannot distinguish incoming vs outgoing invoices.",
        })

    valid = not any(i["level"] == "error" for i in issues)
    return {"valid": valid, "issues": issues}


def _handle_config(args: argparse.Namespace, output_format: str) -> None:
    """Handle `config show` and `config validate` subcommands."""
    base_dir = get_base_directory(getattr(args, "config_path", None))
    config_path = os.path.join(base_dir, "config.yaml")

    if getattr(args, "config_path", None):
        config_path = args.config_path

    config = load_yaml_config(config_path)

    action = getattr(args, "config_action", None)

    if action == "show":
        if config is None:
            error_exit(
                "config_error",
                f"Config file not found: {config_path}",
                suggestion="Copy config.yaml.example to config.yaml",
                exit_code=ExitCode.CONFIG_ERROR,
                output_format=output_format,
            )
        redacted = _redact_config(config)
        if output_format == "json":
            redacted["config_path"] = os.path.abspath(config_path)
            print(json.dumps(redacted, indent=2, ensure_ascii=True))
        else:
            import yaml
            console.print(yaml.dump(redacted, default_flow_style=False, allow_unicode=True))
        sys.exit(ExitCode.SUCCESS)

    elif action == "validate":
        result = _validate_config(config, config_path)
        if output_format == "json":
            print(json.dumps(result, indent=2, ensure_ascii=True))
        else:
            if result["valid"]:
                console.print("[green]Configuration is valid.[/green]")
            else:
                console.print("[red]Configuration has errors:[/red]")
            for issue in result["issues"]:
                level = issue["level"]
                color = "red" if level == "error" else "yellow"
                console.print(f"  [{color}]{level}[/{color}]: {issue['field']} — {issue['message']}")
        sys.exit(ExitCode.SUCCESS if result["valid"] else ExitCode.CONFIG_ERROR)

    else:
        # No action specified — show help
        error_exit(
            "usage_error",
            "Missing config action. Use: config show | config validate",
            exit_code=ExitCode.USAGE_ERROR,
            output_format=output_format,
        )


# ---------------------------------------------------------------------------
# Undo handler
# ---------------------------------------------------------------------------

def _handle_undo(args: argparse.Namespace, output_format: str) -> None:
    """Handle the undo subcommand."""
    directory = getattr(args, "directory", None) or os.getcwd()
    undo_log = os.path.join(directory, UNDO_LOG_NAME)

    if not os.path.exists(undo_log):
        error_exit(
            "no_files",
            f"No undo log found in {directory}",
            suggestion="Run a rename operation first, then undo.",
            exit_code=ExitCode.NO_FILES,
            output_format=output_format,
        )

    # --list mode: show batches and exit
    if getattr(args, "list_batches", False):
        batches = list_undo_batches(undo_log)
        result = UndoBatchListResult(batches=batches)
        if output_format == "json":
            print(result.to_json())
        else:
            if not batches:
                console.print("No undo batches found.")
            else:
                for b in batches:
                    status = "[dim]undone[/]" if b["undone"] else "[green]active[/]"
                    console.print(
                        f"  {b['batch_id']}  {b['timestamp']}  "
                        f"{b['file_count']} file(s)  {status}"
                    )
        sys.exit(ExitCode.SUCCESS)

    # Determine undo scope
    batch_id_arg = getattr(args, "batch", None)
    undo_all = getattr(args, "undo_all", False)

    success, fail, per_file_results = undo_renames(
        undo_log, batch_id=batch_id_arg, undo_all=undo_all
    )

    undo_files = [
        UndoFileResult(
            old_path=fr["old_path"].replace("\\", "/"),
            new_path=fr["new_path"].replace("\\", "/"),
            status=fr["status"],
        )
        for fr in per_file_results
    ]

    undo_result = UndoResult(
        success=(fail == 0),
        restored=success,
        failed=fail,
        files=undo_files,
        batch_id=batch_id_arg,
    )

    if output_format == "json":
        print(undo_result.to_json())
    else:
        console.print(f"Undo complete: {success} restored, {fail} failed")

    sys.exit(ExitCode.SUCCESS if fail == 0 else ExitCode.PARTIAL_FAILURE)


# ---------------------------------------------------------------------------
# Rename handler
# ---------------------------------------------------------------------------

def _handle_rename(args: argparse.Namespace, output_format: str) -> None:
    """Handle the rename subcommand (default)."""
    quiet = getattr(args, "quiet", False)
    dry_run = getattr(args, "dry_run", False)

    base_dir = get_base_directory(getattr(args, "config_path", None))
    config_path = os.path.join(base_dir, "config.yaml")
    yaml_path = os.path.join(base_dir, "harmonized-company-names.yaml")

    if getattr(args, "config_path", None):
        config_path = args.config_path

    # Load config
    config = load_yaml_config(config_path)
    if not config:
        error_exit(
            "config_error",
            "Could not load config.yaml. See config.yaml.example for setup.",
            suggestion="Copy config.yaml.example to config.yaml and add your API key.",
            exit_code=ExitCode.CONFIG_ERROR,
            output_format=output_format,
        )

    # Apply CLI overrides
    if getattr(args, "provider", None):
        config["ai"]["provider"] = args.provider
    if getattr(args, "model", None):
        config["ai"]["model"] = args.model
    if getattr(args, "vision", False):
        config["pdf"]["vision"] = True
    if getattr(args, "text_only", False):
        config["pdf"]["ocr"] = False
        config["pdf"]["vision"] = False
    if getattr(args, "ocr", False):
        config["pdf"]["ocr"] = True

    # Collect PDF files
    paths = getattr(args, "paths", [])
    if not paths:
        error_exit(
            "usage_error",
            "No files or folders specified.",
            suggestion="Usage: autorename-pdf [options] <files_or_folders...>",
            exit_code=ExitCode.USAGE_ERROR,
            output_format=output_format,
        )

    recursive = getattr(args, "recursive", False)
    pdf_files = collect_pdf_files(paths, recursive=recursive)
    if not pdf_files:
        error_exit(
            "no_files",
            "No PDF files found in the specified paths.",
            exit_code=ExitCode.NO_FILES,
            output_format=output_format,
        )

    # Determine undo log path (in the directory of the first PDF)
    first_pdf_dir = os.path.dirname(os.path.abspath(pdf_files[0]))
    undo_log_path = os.path.join(first_pdf_dir, UNDO_LOG_NAME) if not dry_run else None

    # Generate batch ID for this rename operation
    batch_id = generate_batch_id() if not dry_run else None

    # Process PDFs
    file_results: list[FileResult] = []
    renamed = 0
    skipped = 0
    failed = 0

    # For text mode, show progress via console. For JSON, use stderr for progress.
    show_text = (output_format == "text" and not quiet)
    progress_con = console if show_text else None

    if show_text and dry_run:
        console.print("[bold]Dry run[/bold] [dim]no files will be renamed[/]\n")

    total = len(pdf_files)
    for i, pdf_path in enumerate(pdf_files, 1):
        filename = normalize_unicode(os.path.basename(pdf_path))
        if show_text:
            console.print(f"[bold dim]\\[{i}/{total}][/] [bold]{filename}[/]")
        elif output_format == "json" and not quiet:
            # Progress to stderr so it doesn't pollute JSON stdout
            print(f"Processing [{i}/{total}] {filename}", file=sys.stderr)

        file_result = process_pdf(
            pdf_path, config, yaml_path, undo_log_path,
            dry_run=dry_run, output=progress_con, batch_id=batch_id,
        )
        file_results.append(file_result)

        if file_result.status == "renamed":
            renamed += 1
        elif file_result.status == "skipped":
            skipped += 1
        else:
            failed += 1

    # When every file was skipped (already correctly named), write an empty
    # batch so that a subsequent "undo" targets this no-op batch instead of
    # silently reverting an earlier rename run.
    if renamed == 0 and skipped > 0 and undo_log_path and batch_id:
        write_empty_batch(undo_log_path, batch_id)

    batch = BatchResult(
        success=(failed == 0),
        total=total,
        renamed=renamed,
        skipped=skipped,
        failed=failed,
        files=file_results,
        dry_run=dry_run,
        batch_id=batch_id,
    )

    if output_format == "json":
        print(batch.to_json())
    elif not quiet:
        # Text summary — friendly message when everything was already correct
        if renamed == 0 and failed == 0 and skipped > 0:
            label = "file" if skipped == 1 else "files"
            console.print(f"\n[bold]Done:[/bold] All {skipped} {label} already correctly named")
        else:
            parts = []
            if renamed:
                parts.append(f"[green]{renamed} renamed[/]")
            if skipped:
                parts.append(f"[yellow]{skipped} skipped[/]")
            if failed:
                parts.append(f"[red]{failed} failed[/]")
            console.print(f"\n[bold]Done:[/bold] {', '.join(parts)}")

    if failed > 0 and failed < total:
        sys.exit(ExitCode.PARTIAL_FAILURE)
    elif failed == total:
        sys.exit(ExitCode.GENERAL_ERROR)
    sys.exit(ExitCode.SUCCESS)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    parser = build_parser()
    argv = _preprocess_argv()
    args = parser.parse_args(argv)

    setup_logging(verbose=getattr(args, "verbose", False))

    output_format = resolve_output_format(args)

    # Legacy --undo flag detection
    if getattr(args, "undo", False):
        if output_format == "text":
            console.print(
                "[yellow]Warning:[/yellow] --undo is deprecated. "
                "Use [bold]autorename-pdf undo[/bold] instead."
            )
        else:
            print(json.dumps({
                "warning": "--undo is deprecated. Use 'autorename-pdf undo' instead."
            }), file=sys.stderr)
        _handle_undo(args, output_format)
        return

    subcommand = getattr(args, "subcommand", None)

    if subcommand == "undo":
        _handle_undo(args, output_format)
    elif subcommand == "config":
        _handle_config(args, output_format)
    elif subcommand == "rename":
        _handle_rename(args, output_format)
    else:
        # No subcommand and no paths — show help
        parser.print_help()
        sys.exit(ExitCode.USAGE_ERROR)


if __name__ == "__main__":
    main()
