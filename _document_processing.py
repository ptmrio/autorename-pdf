"""
Document processing utilities for company name harmonization and file operations.
Uses rapidfuzz for fuzzy matching. All functions accept config dict explicitly.
"""
from __future__ import annotations

import os
import json
import logging
import datetime
import time

import dateparser
from rapidfuzz.distance import JaroWinkler

from _utils import UNKNOWN_VALUE, DEFAULT_DATE, sanitize_filename, normalize_unicode
from _config_loader import load_company_names
from _profiles import iter_template_tokens

# Constants
CONFIDENCE_THRESHOLD = 0.85


def harmonize_company_name(company_name: str, yaml_path: str, config: dict | None = None) -> str:
    """Harmonize company name based on predefined mappings using rapidfuzz."""
    company_name = normalize_unicode(company_name.strip())
    if not os.path.exists(yaml_path):
        logging.warning(f'{yaml_path} not found, using original name: {company_name}')
        return company_name

    harmonized_names = load_company_names(yaml_path)
    if not harmonized_names:
        logging.warning(f'No company names loaded from {yaml_path}, using original name: {company_name}')
        return company_name

    best_match = max(
        (
            (harmonized_name, max(
                JaroWinkler.similarity(company_name.lower(), synonym.lower())
                for synonym in synonyms
            ))
            for harmonized_name, synonyms in harmonized_names.items()
        ),
        key=lambda x: x[1]
    )

    if best_match[1] > CONFIDENCE_THRESHOLD:
        logging.info(f'Using harmonized company name: {best_match[0]} (score: {best_match[1]:.3f})')
        return normalize_unicode(best_match[0])

    logging.info(f'No harmonized company name found, using original name: {company_name}')
    return company_name


def parse_document_date(date_str: str) -> datetime.date | None:
    """Parse a date string using dateparser with DMY order."""
    parsed = dateparser.parse(date_str, settings={'DATE_ORDER': 'DMY'})
    if parsed:
        return parsed.date() if hasattr(parsed, 'date') else parsed
    return None


def _rename_with_retry(src: str, dst: str, retries: int = 3, delay: float = 1.0) -> None:
    """Rename with retry on PermissionError. Raises on final failure."""
    for attempt in range(retries):
        try:
            os.rename(src, dst)
            return
        except PermissionError:
            if attempt < retries - 1:
                logging.warning(f"File in use, retrying in {delay}s... ({attempt + 1}/{retries})")
                time.sleep(delay)
            else:
                raise PermissionError(
                    f"Cannot rename: file is in use after {retries} attempts. "
                    f"Close the file and try again: {src}"
                )


_MAX_BASE = 244
_SEP_CHARS = frozenset(" \t\n\r-_")


def _is_separator_run(text: str) -> bool:
    return bool(text) and all(ch in _SEP_CHARS for ch in text)


def _collapse_separator_run(text: str) -> str:
    if "-" in text:
        if any(ch.isspace() for ch in text):
            return " - "
        return "-"
    if "_" in text:
        return "_"
    return " "


def _prepare_values(profile_id: str, profile: dict, fields: dict[str, str], config: dict) -> dict[str, str]:
    date_format = config.get("output", {}).get("date_format", "%Y%m%d")
    working = {}
    for name in profile["fields"]:
        raw = fields.get(name, "")
        if not isinstance(raw, str):
            raw = ""
        if name == "document_date":
            parsed = parse_document_date(raw) if raw.strip() else None
            working[name] = parsed.strftime(date_format) if parsed else DEFAULT_DATE
            continue
        cleaned = sanitize_filename(normalize_unicode(raw))
        if cleaned.strip():
            working[name] = cleaned
        elif profile_id == "business" and name in ("company_name", "document_type"):
            working[name] = UNKNOWN_VALUE
        else:
            working[name] = ""
    return working


def _join_tokens(tokens, values: dict[str, str]) -> str:
    pieces: list[str] = []
    pending_sep = ""
    started = False
    for kind, payload in tokens:
        if kind == "field":
            value = values.get(payload, "")
            if not value:
                continue
            if started:
                if pending_sep:
                    if _is_separator_run(pending_sep):
                        pieces.append(_collapse_separator_run(pending_sep))
                    else:
                        pieces.append(pending_sep)
                pending_sep = ""
            pieces.append(value)
            started = True
            continue
        if not started:
            if _is_separator_run(payload):
                continue
            pieces.append(payload)
            started = True
            pending_sep = ""
            continue
        if _is_separator_run(payload):
            pending_sep += payload
        else:
            if pending_sep:
                if _is_separator_run(pending_sep):
                    pieces.append(_collapse_separator_run(pending_sep))
                else:
                    pieces.append(pending_sep)
                pending_sep = ""
            pieces.append(payload)
    base = "".join(pieces)
    base = sanitize_filename(normalize_unicode(base))
    base = " ".join(base.split())
    return base


def render_filename(profile_id: str, profile: dict, fields: dict[str, str], config: dict) -> str:
    """Pure basename+.pdf renderer. Does not mutate fields."""
    tokens = iter_template_tokens(profile["template"])
    values = _prepare_values(profile_id, profile, fields, config)
    truncate = profile["truncate_field"]

    base = _join_tokens(tokens, values)
    target = values.get(truncate, "")
    while len(base) > _MAX_BASE and target:
        target = target[:-1]
        values[truncate] = target
        base = _join_tokens(tokens, values)
        target = values.get(truncate, "")
    if len(base) > _MAX_BASE:
        base = base[:_MAX_BASE].rstrip(". ")
    if not base:
        base = UNKNOWN_VALUE
    return normalize_unicode(f"{base}.pdf")


def rename_document(
    pdf_path: str,
    new_name: str,
    undo_log_path: str = None,
    batch_id: str = None,
    dry_run: bool = False,
) -> str | None:
    """Rename a PDF to an already-rendered .pdf name. Collision, dry-run, undo."""
    pdf_path = normalize_unicode(pdf_path)
    new_name = normalize_unicode(new_name)
    if not new_name.lower().endswith(".pdf"):
        new_name = f"{new_name}.pdf"
    base_name = new_name[:-4]
    new_path = os.path.join(os.path.dirname(pdf_path), new_name)

    if pdf_path == new_path:
        logging.info(f'File "{new_name}" is already correctly named.')
        return None

    counter = 0
    while os.path.exists(new_path):
        counter += 1
        new_name = f"{base_name}_({counter}).pdf"
        new_path = os.path.join(os.path.dirname(pdf_path), new_name)

    if dry_run:
        return new_path

    _rename_with_retry(pdf_path, new_path)
    logging.info(f'Document renamed to: {new_name}')

    if undo_log_path:
        _write_undo_log(undo_log_path, pdf_path, new_path, batch_id=batch_id)

    return new_path


def generate_batch_id() -> str:
    """Generate a unique batch ID: YYYYMMDDTHHMMSS-<6hex> in UTC."""
    now = datetime.datetime.now(datetime.timezone.utc)
    hex_suffix = os.urandom(3).hex()
    return f"{now.strftime('%Y%m%dT%H%M%S')}-{hex_suffix}"


def _read_undo_log(log_path: str) -> dict:
    """Read undo log, migrating v1 (bare array) to v2 format in memory."""
    if not os.path.exists(log_path):
        return {"version": 2, "batches": []}

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logging.warning(f"Could not read undo log {log_path}: {e}")
        return {"version": 2, "batches": []}

    # v1 format: bare array of entries
    if isinstance(data, list):
        return {
            "version": 2,
            "batches": [{
                "batch_id": "migrated-v1",
                "timestamp": data[0].get("timestamp", "") if data else "",
                "source": "cli",
                "undone": False,
                "files": data,
            }] if data else [],
        }

    # Already v2
    return data


def _write_undo_log_v2(log_path: str, log_data: dict) -> None:
    """Write v2 undo log, pruning batches older than 30 days."""
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=30)).isoformat()

    pruned_batches = []
    for batch in log_data.get("batches", []):
        ts = batch.get("timestamp", "")
        # Keep batches newer than cutoff or without parseable timestamp
        if not ts or ts >= cutoff:
            pruned_batches.append(batch)

    log_data["batches"] = pruned_batches
    log_data["version"] = 2

    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)


def write_empty_batch(log_path: str, batch_id: str) -> None:
    """Write a no-op batch to the undo log.

    Called when all files in a rename run were skipped (already correctly
    named).  The empty batch prevents a subsequent ``undo`` from silently
    reverting an *earlier* run — the empty batch is picked up as the most
    recent non-undone batch instead.
    """
    log_data = _read_undo_log(log_path)
    log_data["batches"].append({
        "batch_id": batch_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "cli",
        "undone": False,
        "files": [],
    })
    _write_undo_log_v2(log_path, log_data)


def _write_undo_log(log_path: str, old_path: str, new_path: str, batch_id: str = None) -> None:
    """Append a rename entry to the undo log (v2 batch format)."""
    log_data = _read_undo_log(log_path)

    entry = {
        "old_path": old_path,
        "new_path": new_path,
        "timestamp": datetime.datetime.now().isoformat(),
    }

    if batch_id:
        # Find or create the batch
        target_batch = None
        for batch in log_data["batches"]:
            if batch["batch_id"] == batch_id:
                target_batch = batch
                break
        if target_batch is None:
            target_batch = {
                "batch_id": batch_id,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "source": "cli",
                "undone": False,
                "files": [],
            }
            log_data["batches"].append(target_batch)
        target_batch["files"].append(entry)
    else:
        # Legacy mode: create a new batch per call
        log_data["batches"].append({
            "batch_id": generate_batch_id(),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source": "cli",
            "undone": False,
            "files": [entry],
        })

    _write_undo_log_v2(log_path, log_data)


def list_undo_batches(log_path: str) -> list[dict]:
    """Return batch summaries for listing. Each dict has batch_id, timestamp, file_count, undone."""
    log_data = _read_undo_log(log_path)
    summaries = []
    for batch in log_data.get("batches", []):
        summaries.append({
            "batch_id": batch["batch_id"],
            "timestamp": batch.get("timestamp", ""),
            "file_count": len(batch.get("files", [])),
            "undone": batch.get("undone", False),
        })
    return summaries


def undo_renames(
    log_path: str,
    batch_id: str = None,
    undo_all: bool = False,
) -> tuple[int, int, list[dict]]:
    """Reverse renames from the undo log.

    Returns (success_count, fail_count, per_file_results).
    per_file_results: [{"old_path": ..., "new_path": ..., "status": "restored"|"failed"}]

    Default: undo last non-undone batch only.
    batch_id: undo a specific batch.
    undo_all: undo all non-undone batches.
    """
    log_data = _read_undo_log(log_path)
    batches = log_data.get("batches", [])

    if not batches:
        logging.warning("No undo log found.")
        return 0, 0, []

    # Select which batches to undo
    if undo_all:
        targets = [b for b in batches if not b.get("undone", False)]
    elif batch_id:
        targets = [b for b in batches if b["batch_id"] == batch_id and not b.get("undone", False)]
        if not targets:
            logging.warning(f"Batch '{batch_id}' not found or already undone.")
            return 0, 0, []
    else:
        # Default: last non-undone batch
        non_undone = [b for b in batches if not b.get("undone", False)]
        targets = [non_undone[-1]] if non_undone else []

    if not targets:
        logging.warning("No batches to undo.")
        return 0, 0, []

    success = 0
    fail = 0
    file_results = []

    for batch in targets:
        for entry in reversed(batch.get("files", [])):
            new_path = entry["new_path"]
            old_path = entry["old_path"]
            if os.path.exists(new_path):
                try:
                    _rename_with_retry(new_path, old_path)
                    logging.info(f'Undone: {os.path.basename(new_path)} \u2192 {os.path.basename(old_path)}')
                    success += 1
                    file_results.append({"old_path": new_path, "new_path": old_path, "status": "restored"})
                except Exception as e:
                    logging.error(f'Failed to undo {new_path}: {e}')
                    fail += 1
                    file_results.append({"old_path": new_path, "new_path": old_path, "status": "failed"})
            else:
                logging.warning(f'File not found for undo: {new_path}')
                fail += 1
                file_results.append({"old_path": new_path, "new_path": old_path, "status": "failed"})

        # Mark batch as undone (don't delete the log)
        batch["undone"] = True

    _write_undo_log_v2(log_path, log_data)
    return success, fail, file_results
