"""Tests for _document_processing.py."""

import os
import sys
import json
import datetime
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _document_processing import (
    harmonize_company_name,
    parse_document_date,
    rename_invoice,
    undo_renames,
    _write_undo_log,
    _read_undo_log,
    _write_undo_log_v2,
    generate_batch_id,
    list_undo_batches,
    write_empty_batch,
    _rename_with_retry,
)


class TestHarmonizeCompanyName:
    def test_exact_match(self, harmonized_names_file):
        result = harmonize_company_name("ACME Corporation", harmonized_names_file)
        assert result == "ACME"

    def test_close_match(self, harmonized_names_file):
        result = harmonize_company_name("Acme Corp.", harmonized_names_file)
        assert result == "ACME"

    def test_no_match(self, harmonized_names_file):
        result = harmonize_company_name("Completely Different Company", harmonized_names_file)
        assert result == "Completely Different Company"

    def test_missing_file(self):
        result = harmonize_company_name("ACME", "/nonexistent/names.yaml")
        assert result == "ACME"

    def test_strips_whitespace(self, harmonized_names_file):
        result = harmonize_company_name("  ACME Corporation  ", harmonized_names_file)
        assert result == "ACME"

    def test_case_insensitive(self, harmonized_names_file):
        result = harmonize_company_name("acme corporation", harmonized_names_file)
        assert result == "ACME"


class TestParseDocumentDate:
    def test_german_format(self):
        result = parse_document_date("15.03.2024")
        assert result is not None
        assert result.day == 15
        assert result.month == 3
        assert result.year == 2024

    def test_written_date(self):
        result = parse_document_date("15 March 2024")
        assert result is not None

    def test_invalid_date(self):
        result = parse_document_date("not a date")
        assert result is None

    def test_empty_string(self):
        result = parse_document_date("")
        assert result is None


class TestRenameInvoice:
    def test_basic_rename(self, tmp_path, sample_config):
        pdf_path = str(tmp_path / "original.pdf")
        with open(pdf_path, 'w') as f:
            f.write("fake pdf")

        result = rename_invoice(
            pdf_path, "ACME", datetime.date(2024, 3, 15), "ER", sample_config
        )
        assert result is not None
        assert "20240315 ACME ER.pdf" in result
        assert os.path.exists(result)

    def test_dry_run(self, tmp_path, sample_config):
        pdf_path = str(tmp_path / "original.pdf")
        with open(pdf_path, 'w') as f:
            f.write("fake pdf")

        result = rename_invoice(
            pdf_path, "ACME", datetime.date(2024, 3, 15), "ER",
            sample_config, dry_run=True
        )
        assert result is not None
        assert "20240315 ACME ER.pdf" in result
        # Original should still exist (dry run)
        assert os.path.exists(pdf_path)

    def test_already_named(self, tmp_path, sample_config):
        pdf_path = str(tmp_path / "20240315 ACME ER.pdf")
        with open(pdf_path, 'w') as f:
            f.write("fake pdf")

        result = rename_invoice(
            pdf_path, "ACME", datetime.date(2024, 3, 15), "ER", sample_config
        )
        assert result is None  # skipped

    def test_duplicate_handling(self, tmp_path, sample_config):
        # Create original and existing target
        pdf_path = str(tmp_path / "original.pdf")
        existing = str(tmp_path / "20240315 ACME ER.pdf")
        with open(pdf_path, 'w') as f:
            f.write("fake pdf 1")
        with open(existing, 'w') as f:
            f.write("fake pdf 2")

        result = rename_invoice(
            pdf_path, "ACME", datetime.date(2024, 3, 15), "ER", sample_config
        )
        assert result is not None
        assert "_(1)" in result

    def test_invalid_company_name(self, tmp_path, sample_config):
        pdf_path = str(tmp_path / "original.pdf")
        with open(pdf_path, 'w') as f:
            f.write("fake pdf")

        result = rename_invoice(
            pdf_path, 'Invalid<>Name', datetime.date(2024, 3, 15), "ER", sample_config
        )
        assert result is not None
        assert "Unknown" in result

    def test_no_date(self, tmp_path, sample_config):
        pdf_path = str(tmp_path / "original.pdf")
        with open(pdf_path, 'w') as f:
            f.write("fake pdf")

        result = rename_invoice(
            pdf_path, "ACME", None, "ER", sample_config
        )
        assert result is not None
        assert "00000000" in result

    def test_undo_log_written(self, tmp_path, sample_config):
        pdf_path = str(tmp_path / "original.pdf")
        with open(pdf_path, 'w') as f:
            f.write("fake pdf")
        log_path = str(tmp_path / ".autorename-log.json")

        rename_invoice(
            pdf_path, "ACME", datetime.date(2024, 3, 15), "ER",
            sample_config, undo_log_path=log_path, batch_id="test-batch-001"
        )

        assert os.path.exists(log_path)
        with open(log_path, 'r') as f:
            data = json.load(f)
        assert data["version"] == 2
        assert len(data["batches"]) == 1
        assert data["batches"][0]["batch_id"] == "test-batch-001"
        assert len(data["batches"][0]["files"]) == 1
        assert data["batches"][0]["files"][0]["old_path"] == pdf_path

    def test_custom_date_format(self, tmp_path, sample_config):
        sample_config["output"]["date_format"] = "%d-%m-%Y"
        pdf_path = str(tmp_path / "original.pdf")
        with open(pdf_path, 'w') as f:
            f.write("fake pdf")

        result = rename_invoice(
            pdf_path, "ACME", datetime.date(2024, 3, 15), "ER", sample_config
        )
        assert "15-03-2024" in result

    def test_unicode_filename_is_normalized_to_nfc(self, tmp_path, sample_config):
        pdf_path = str(tmp_path / "original.pdf")
        with open(pdf_path, 'w') as f:
            f.write("fake pdf")

        result = rename_invoice(
            pdf_path, "RO\u0308HRS", datetime.date(2024, 3, 15), "ER", sample_config
        )
        assert result is not None
        assert "R\u00d6HRS" in result


class TestUndoRenames:
    def _write_v2_log(self, log_path, batches):
        """Helper to write a v2 undo log."""
        with open(log_path, 'w') as f:
            json.dump({"version": 2, "batches": batches}, f)

    def test_undo_success(self, tmp_path):
        old_path = str(tmp_path / "original.pdf")
        new_path = str(tmp_path / "20240315 ACME ER.pdf")
        with open(new_path, 'w') as f:
            f.write("fake pdf")

        recent_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        log_path = str(tmp_path / ".autorename-log.json")
        self._write_v2_log(log_path, [{
            "batch_id": "batch-001",
            "timestamp": recent_ts,
            "source": "cli",
            "undone": False,
            "files": [{"old_path": old_path, "new_path": new_path, "timestamp": "2024-03-15T10:00:00"}],
        }])

        success, fail, results = undo_renames(log_path)
        assert success == 1
        assert fail == 0
        assert len(results) == 1
        assert results[0]["status"] == "restored"
        assert os.path.exists(old_path)
        assert not os.path.exists(new_path)
        # Log should still exist (not deleted)
        assert os.path.exists(log_path)
        # Batch should be marked as undone
        with open(log_path, 'r') as f:
            data = json.load(f)
        assert data["batches"][0]["undone"] is True

    def test_undo_no_log(self, tmp_path):
        success, fail, results = undo_renames(str(tmp_path / "nonexistent.json"))
        assert success == 0
        assert fail == 0
        assert results == []

    def test_undo_missing_file(self, tmp_path):
        log_path = str(tmp_path / ".autorename-log.json")
        self._write_v2_log(log_path, [{
            "batch_id": "batch-001",
            "timestamp": "2024-03-15T10:00:00+00:00",
            "source": "cli",
            "undone": False,
            "files": [{"old_path": "x.pdf", "new_path": "y.pdf", "timestamp": "now"}],
        }])

        success, fail, results = undo_renames(log_path)
        assert success == 0
        assert fail == 1
        assert results[0]["status"] == "failed"

    def test_undo_last_batch_only(self, tmp_path):
        """Default undo only reverts the last non-undone batch."""
        old1 = str(tmp_path / "orig1.pdf")
        new1 = str(tmp_path / "renamed1.pdf")
        old2 = str(tmp_path / "orig2.pdf")
        new2 = str(tmp_path / "renamed2.pdf")
        with open(new1, 'w') as f:
            f.write("pdf1")
        with open(new2, 'w') as f:
            f.write("pdf2")

        log_path = str(tmp_path / ".autorename-log.json")
        self._write_v2_log(log_path, [
            {
                "batch_id": "batch-001",
                "timestamp": "2024-03-15T10:00:00+00:00",
                "source": "cli",
                "undone": False,
                "files": [{"old_path": old1, "new_path": new1, "timestamp": "t1"}],
            },
            {
                "batch_id": "batch-002",
                "timestamp": "2024-03-15T11:00:00+00:00",
                "source": "cli",
                "undone": False,
                "files": [{"old_path": old2, "new_path": new2, "timestamp": "t2"}],
            },
        ])

        success, fail, _ = undo_renames(log_path)
        assert success == 1
        assert fail == 0
        # Only batch-002 was undone
        assert os.path.exists(old2)
        assert not os.path.exists(new2)
        # batch-001 file should be untouched
        assert os.path.exists(new1)
        assert not os.path.exists(old1)

    def test_undo_specific_batch(self, tmp_path):
        old1 = str(tmp_path / "orig1.pdf")
        new1 = str(tmp_path / "renamed1.pdf")
        with open(new1, 'w') as f:
            f.write("pdf1")

        log_path = str(tmp_path / ".autorename-log.json")
        self._write_v2_log(log_path, [{
            "batch_id": "batch-001",
            "timestamp": "2024-03-15T10:00:00+00:00",
            "source": "cli",
            "undone": False,
            "files": [{"old_path": old1, "new_path": new1, "timestamp": "t1"}],
        }])

        success, fail, _ = undo_renames(log_path, batch_id="batch-001")
        assert success == 1
        assert fail == 0

    def test_undo_all(self, tmp_path):
        old1 = str(tmp_path / "orig1.pdf")
        new1 = str(tmp_path / "renamed1.pdf")
        old2 = str(tmp_path / "orig2.pdf")
        new2 = str(tmp_path / "renamed2.pdf")
        with open(new1, 'w') as f:
            f.write("pdf1")
        with open(new2, 'w') as f:
            f.write("pdf2")

        log_path = str(tmp_path / ".autorename-log.json")
        self._write_v2_log(log_path, [
            {"batch_id": "b1", "timestamp": "t", "source": "cli", "undone": False,
             "files": [{"old_path": old1, "new_path": new1, "timestamp": "t1"}]},
            {"batch_id": "b2", "timestamp": "t", "source": "cli", "undone": False,
             "files": [{"old_path": old2, "new_path": new2, "timestamp": "t2"}]},
        ])

        success, fail, _ = undo_renames(log_path, undo_all=True)
        assert success == 2
        assert fail == 0
        assert os.path.exists(old1) and os.path.exists(old2)

    def test_undo_skips_already_undone(self, tmp_path):
        old1 = str(tmp_path / "orig1.pdf")
        new1 = str(tmp_path / "renamed1.pdf")

        log_path = str(tmp_path / ".autorename-log.json")
        self._write_v2_log(log_path, [{
            "batch_id": "b1", "timestamp": "t", "source": "cli", "undone": True,
            "files": [{"old_path": old1, "new_path": new1, "timestamp": "t1"}],
        }])

        success, fail, results = undo_renames(log_path)
        assert success == 0
        assert fail == 0
        assert results == []

    def test_undo_log_not_deleted(self, tmp_path):
        """Log file persists after undo (batches marked undone, not deleted)."""
        old_path = str(tmp_path / "original.pdf")
        new_path = str(tmp_path / "renamed.pdf")
        with open(new_path, 'w') as f:
            f.write("pdf")

        log_path = str(tmp_path / ".autorename-log.json")
        self._write_v2_log(log_path, [{
            "batch_id": "b1", "timestamp": "t", "source": "cli", "undone": False,
            "files": [{"old_path": old_path, "new_path": new_path, "timestamp": "t"}],
        }])

        undo_renames(log_path)
        assert os.path.exists(log_path)

    def test_v1_log_backward_compat(self, tmp_path):
        """v1 format (bare array) should work via in-memory migration."""
        old_path = str(tmp_path / "original.pdf")
        new_path = str(tmp_path / "renamed.pdf")
        with open(new_path, 'w') as f:
            f.write("pdf")

        log_path = str(tmp_path / ".autorename-log.json")
        with open(log_path, 'w') as f:
            json.dump([{"old_path": old_path, "new_path": new_path, "timestamp": "t"}], f)

        success, fail, results = undo_renames(log_path)
        assert success == 1
        assert fail == 0
        assert os.path.exists(old_path)


class TestUndoLogV2Schema:
    def test_batch_id_unique(self):
        ids = {generate_batch_id() for _ in range(100)}
        assert len(ids) == 100

    def test_batch_id_format(self):
        bid = generate_batch_id()
        assert len(bid) == 22  # YYYYMMDDTHHMMSS-6hex
        assert bid[8] == 'T'
        assert bid[15] == '-'

    def test_v2_structure(self, tmp_path):
        log_path = str(tmp_path / "log.json")
        _write_undo_log(log_path, "/old.pdf", "/new.pdf", batch_id="test-batch")
        with open(log_path, 'r') as f:
            data = json.load(f)
        assert data["version"] == 2
        assert isinstance(data["batches"], list)
        batch = data["batches"][0]
        assert batch["batch_id"] == "test-batch"
        assert isinstance(batch["files"], list)
        assert "undone" in batch

    def test_multi_file_append_same_batch(self, tmp_path):
        log_path = str(tmp_path / "log.json")
        _write_undo_log(log_path, "/old1.pdf", "/new1.pdf", batch_id="batch-x")
        _write_undo_log(log_path, "/old2.pdf", "/new2.pdf", batch_id="batch-x")
        with open(log_path, 'r') as f:
            data = json.load(f)
        assert len(data["batches"]) == 1
        assert len(data["batches"][0]["files"]) == 2


class TestUndoLogMigration:
    def test_v1_to_v2(self, tmp_path):
        log_path = str(tmp_path / "log.json")
        with open(log_path, 'w') as f:
            json.dump([{"old_path": "a", "new_path": "b", "timestamp": "t"}], f)
        data = _read_undo_log(log_path)
        assert data["version"] == 2
        assert data["batches"][0]["batch_id"] == "migrated-v1"
        assert len(data["batches"][0]["files"]) == 1

    def test_corrupt_json(self, tmp_path):
        log_path = str(tmp_path / "log.json")
        with open(log_path, 'w') as f:
            f.write("{corrupt")
        data = _read_undo_log(log_path)
        assert data == {"version": 2, "batches": []}

    def test_missing_file(self, tmp_path):
        data = _read_undo_log(str(tmp_path / "nonexistent.json"))
        assert data == {"version": 2, "batches": []}


class TestAutoExpiry:
    def test_old_batches_pruned(self, tmp_path):
        log_path = str(tmp_path / "log.json")
        old_ts = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(days=31)).isoformat()
        recent_ts = (datetime.datetime.now(datetime.timezone.utc)
                     - datetime.timedelta(days=29)).isoformat()
        data = {
            "version": 2,
            "batches": [
                {"batch_id": "old", "timestamp": old_ts, "source": "cli",
                 "undone": False, "files": []},
                {"batch_id": "recent", "timestamp": recent_ts, "source": "cli",
                 "undone": False, "files": []},
            ],
        }
        _write_undo_log_v2(log_path, data)
        with open(log_path, 'r') as f:
            result = json.load(f)
        assert len(result["batches"]) == 1
        assert result["batches"][0]["batch_id"] == "recent"


class TestListUndoBatches:
    def test_empty_log(self, tmp_path):
        batches = list_undo_batches(str(tmp_path / "nonexistent.json"))
        assert batches == []

    def test_multiple_batches(self, tmp_path):
        log_path = str(tmp_path / "log.json")
        with open(log_path, 'w') as f:
            json.dump({
                "version": 2,
                "batches": [
                    {"batch_id": "b1", "timestamp": "t1", "source": "cli",
                     "undone": False, "files": [{"old_path": "a", "new_path": "b", "timestamp": "t"}]},
                    {"batch_id": "b2", "timestamp": "t2", "source": "gui",
                     "undone": True, "files": [{"old_path": "c", "new_path": "d", "timestamp": "t"}]},
                ],
            }, f)
        batches = list_undo_batches(log_path)
        assert len(batches) == 2
        assert batches[0]["batch_id"] == "b1"
        assert batches[0]["undone"] is False
        assert batches[0]["file_count"] == 1
        assert batches[1]["undone"] is True


class TestFilenameLength:
    def test_long_company_name_truncated(self, tmp_path, sample_config):
        pdf_path = str(tmp_path / "original.pdf")
        with open(pdf_path, 'w') as f:
            f.write("fake pdf")

        long_name = "A" * 250
        result = rename_invoice(
            pdf_path, long_name, datetime.date(2024, 3, 15), "ER", sample_config
        )
        assert result is not None
        filename = os.path.basename(result)
        assert len(filename) <= 255


class TestRenameWithRetry:
    def test_retry_on_permission_error(self, tmp_path):
        src = str(tmp_path / "src.pdf")
        dst = str(tmp_path / "dst.pdf")
        with open(src, 'w') as f:
            f.write("content")

        call_count = 0
        original_rename = os.rename

        def mock_rename(s, d):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise PermissionError("file in use")
            original_rename(s, d)

        with pytest.MonkeyPatch.context() as m:
            m.setattr(os, "rename", mock_rename)
            _rename_with_retry(src, dst, retries=3, delay=0.01)

        assert os.path.exists(dst)
        assert call_count == 3

    def test_final_failure_raises(self, tmp_path):
        src = str(tmp_path / "src.pdf")
        dst = str(tmp_path / "dst.pdf")
        with open(src, 'w') as f:
            f.write("content")

        def always_fail(s, d):
            raise PermissionError("locked")

        with pytest.MonkeyPatch.context() as m:
            m.setattr(os, "rename", always_fail)
            with pytest.raises(PermissionError, match="file is in use after 3 attempts"):
                _rename_with_retry(src, dst, retries=3, delay=0.01)


class TestWriteEmptyBatch:
    """Tests for write_empty_batch() — the all-skipped undo safety fix."""

    def _write_v2_log(self, log_path, batches):
        with open(log_path, 'w') as f:
            json.dump({"version": 2, "batches": batches}, f)

    def test_creates_log_with_empty_batch(self, tmp_path):
        log_path = str(tmp_path / ".autorename-log.json")
        write_empty_batch(log_path, "skip-batch-001")

        with open(log_path) as f:
            data = json.load(f)
        assert data["version"] == 2
        assert len(data["batches"]) == 1
        b = data["batches"][0]
        assert b["batch_id"] == "skip-batch-001"
        assert b["files"] == []
        assert b["undone"] is False

    def test_appends_to_existing_log(self, tmp_path):
        log_path = str(tmp_path / ".autorename-log.json")
        recent_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self._write_v2_log(log_path, [{
            "batch_id": "prev-batch",
            "timestamp": recent_ts,
            "source": "cli",
            "undone": False,
            "files": [{"old_path": "a.pdf", "new_path": "b.pdf", "timestamp": recent_ts}],
        }])

        write_empty_batch(log_path, "skip-batch-002")

        with open(log_path) as f:
            data = json.load(f)
        assert len(data["batches"]) == 2
        assert data["batches"][0]["batch_id"] == "prev-batch"
        assert data["batches"][1]["batch_id"] == "skip-batch-002"
        assert data["batches"][1]["files"] == []

    def test_undo_targets_empty_batch_not_previous(self, tmp_path):
        """Critical: undo after all-skipped must NOT revert the prior run."""
        old_path = str(tmp_path / "original.pdf")
        new_path = str(tmp_path / "20240315 ACME ER.pdf")
        with open(new_path, 'w') as f:
            f.write("fake pdf")

        log_path = str(tmp_path / ".autorename-log.json")
        recent_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Batch 1: a real rename from a previous run
        self._write_v2_log(log_path, [{
            "batch_id": "real-batch",
            "timestamp": recent_ts,
            "source": "cli",
            "undone": False,
            "files": [{"old_path": old_path, "new_path": new_path, "timestamp": recent_ts}],
        }])

        # Batch 2: empty batch from an all-skipped run
        write_empty_batch(log_path, "skip-batch")

        # Default undo (no batch_id) should pick the empty batch
        success, fail, results = undo_renames(log_path)
        assert success == 0
        assert fail == 0
        assert results == []

        # The real file should still be in its renamed location
        assert os.path.exists(new_path)

        # The empty batch should be marked undone, real batch untouched
        with open(log_path) as f:
            data = json.load(f)
        assert data["batches"][0]["undone"] is False  # real-batch
        assert data["batches"][1]["undone"] is True    # skip-batch

    def test_undo_empty_batch_is_noop(self, tmp_path):
        log_path = str(tmp_path / ".autorename-log.json")
        write_empty_batch(log_path, "skip-batch")

        success, fail, results = undo_renames(log_path)
        assert success == 0
        assert fail == 0
        assert results == []

        with open(log_path) as f:
            data = json.load(f)
        assert data["batches"][0]["undone"] is True
