import csv
import json
import os
import tempfile

import pytest
from promptguard import Tracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tracker():
    """Return a Tracker pointing at a fresh temp file."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.remove(path)          # Tracker must create the file itself
    return Tracker(filepath=path), path


def _log_sample(tracker, model="gpt-4o"):
    tracker.log(
        model=model,
        template="Translate: {text}",
        params={"text": "Hello"},
        rendered="Translate: Hello",
        output="Ciao",
    )


# ---------------------------------------------------------------------------
# TestTrackerInit
# ---------------------------------------------------------------------------

class TestTrackerInit:
    def test_creates_file_if_missing(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(path)
        t = Tracker(filepath=path)
        assert os.path.exists(path)
        os.remove(path)

    def test_initial_file_contains_empty_list(self):
        t, path = _make_tracker()
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data == []
        os.remove(path)

    def test_accepts_existing_valid_file(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f)
        t = Tracker(filepath=path)          # should not raise
        os.remove(path)

    def test_resets_corrupted_file(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write("NOT JSON {{{{")
        t = Tracker(filepath=path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data == []
        os.remove(path)

    def test_resets_file_with_wrong_root_type(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"key": "value"}, f)
        t = Tracker(filepath=path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data == []
        os.remove(path)


# ---------------------------------------------------------------------------
# TestTrackerLog
# ---------------------------------------------------------------------------

class TestTrackerLog:
    def test_log_returns_none(self):
        t, path = _make_tracker()
        result = t.log("gpt-4o", "tmpl", {}, "rendered", "out")
        assert result is None
        os.remove(path)

    def test_log_appends_one_record(self):
        t, path = _make_tracker()
        _log_sample(t)
        records = t.query()
        assert len(records) == 1
        os.remove(path)

    def test_log_appends_multiple_records_in_order(self):
        t, path = _make_tracker()
        for model in ("gpt-4o", "claude-3-opus", "mistral-7b"):
            _log_sample(t, model=model)
        records = t.query()
        assert len(records) == 3
        assert [r["model"] for r in records] == ["gpt-4o", "claude-3-opus", "mistral-7b"]
        os.remove(path)

    def test_log_record_has_required_keys(self):
        t, path = _make_tracker()
        _log_sample(t)
        r = t.query()[0]
        for key in ("id", "timestamp", "model", "template", "params", "rendered", "output"):
            assert key in r
        os.remove(path)

    def test_log_id_is_uuid_string(self):
        import uuid
        t, path = _make_tracker()
        _log_sample(t)
        r = t.query()[0]
        uuid.UUID(r["id"])          # raises ValueError if not a valid UUID
        os.remove(path)

    def test_log_ids_are_unique(self):
        t, path = _make_tracker()
        for _ in range(5):
            _log_sample(t)
        ids = [r["id"] for r in t.query()]
        assert len(set(ids)) == 5
        os.remove(path)

    def test_log_stores_correct_model(self):
        t, path = _make_tracker()
        t.log("my-model", "tmpl", {}, "rendered", "out")
        assert t.query()[0]["model"] == "my-model"
        os.remove(path)

    def test_log_stores_correct_params(self):
        t, path = _make_tracker()
        params = {"a": 1, "b": "two"}
        t.log("m", "tmpl", params, "rendered", "out")
        assert t.query()[0]["params"] == params
        os.remove(path)

    def test_log_persists_across_instances(self):
        t, path = _make_tracker()
        _log_sample(t)
        t2 = Tracker(filepath=path)
        assert len(t2.query()) == 1
        os.remove(path)


# ---------------------------------------------------------------------------
# TestTrackerQuery
# ---------------------------------------------------------------------------

class TestTrackerQuery:
    def test_query_returns_list(self):
        t, path = _make_tracker()
        assert isinstance(t.query(), list)
        os.remove(path)

    def test_query_empty_when_no_logs(self):
        t, path = _make_tracker()
        assert t.query() == []
        os.remove(path)

    def test_query_all_no_filters(self):
        t, path = _make_tracker()
        for m in ("a", "b", "c"):
            _log_sample(t, model=m)
        assert len(t.query()) == 3
        os.remove(path)

    def test_query_filter_by_model(self):
        t, path = _make_tracker()
        _log_sample(t, model="gpt-4o")
        _log_sample(t, model="gpt-4o")
        _log_sample(t, model="claude")
        result = t.query(model="gpt-4o")
        assert len(result) == 2
        assert all(r["model"] == "gpt-4o" for r in result)
        os.remove(path)

    def test_query_model_no_match_returns_empty(self):
        t, path = _make_tracker()
        _log_sample(t, model="gpt-4o")
        assert t.query(model="nonexistent") == []
        os.remove(path)

    def test_query_date_from_excludes_older(self):
        t, path = _make_tracker()
        _log_sample(t)
        result = t.query(date_from="2999-01-01T00:00:00")
        assert result == []
        os.remove(path)

    def test_query_date_from_includes_all(self):
        t, path = _make_tracker()
        _log_sample(t)
        _log_sample(t)
        result = t.query(date_from="2000-01-01T00:00:00")
        assert len(result) == 2
        os.remove(path)

    def test_query_date_to_excludes_newer(self):
        t, path = _make_tracker()
        _log_sample(t)
        result = t.query(date_to="2000-01-01T00:00:00")
        assert result == []
        os.remove(path)

    def test_query_date_to_includes_all(self):
        t, path = _make_tracker()
        _log_sample(t)
        result = t.query(date_to="2999-12-31T23:59:59")
        assert len(result) == 1
        os.remove(path)

    def test_query_combined_model_and_date_from(self):
        t, path = _make_tracker()
        _log_sample(t, model="gpt-4o")
        _log_sample(t, model="claude")
        result = t.query(model="gpt-4o", date_from="2000-01-01")
        assert len(result) == 1
        assert result[0]["model"] == "gpt-4o"
        os.remove(path)


# ---------------------------------------------------------------------------
# TestTrackerExport
# ---------------------------------------------------------------------------

class TestTrackerExport:
    def _setup(self):
        t, log_path = _make_tracker()
        _log_sample(t, model="gpt-4o")
        _log_sample(t, model="claude")
        fd, out_path = tempfile.mkstemp()
        os.close(fd)
        return t, log_path, out_path

    def test_export_json_creates_file(self):
        t, log_path, out_path = self._setup()
        t.export(out_path, format="json")
        assert os.path.exists(out_path)
        os.remove(log_path); os.remove(out_path)

    def test_export_json_valid_content(self):
        t, log_path, out_path = self._setup()
        t.export(out_path, format="json")
        with open(out_path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 2
        os.remove(log_path); os.remove(out_path)

    def test_export_json_record_structure(self):
        t, log_path, out_path = self._setup()
        t.export(out_path, format="json")
        with open(out_path, encoding="utf-8") as f:
            data = json.load(f)
        for r in data:
            assert "id" in r and "model" in r and "params" in r
        os.remove(log_path); os.remove(out_path)

    def test_export_csv_creates_file(self):
        t, log_path, out_path = self._setup()
        t.export(out_path, format="csv")
        assert os.path.exists(out_path)
        os.remove(log_path); os.remove(out_path)

    def test_export_csv_has_header(self):
        t, log_path, out_path = self._setup()
        t.export(out_path, format="csv")
        with open(out_path, encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
        assert "id" in header
        assert "model" in header
        assert "params" in header
        os.remove(log_path); os.remove(out_path)

    def test_export_csv_row_count(self):
        t, log_path, out_path = self._setup()
        t.export(out_path, format="csv")
        with open(out_path, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        assert len(rows) == 3          # 1 header + 2 records
        os.remove(log_path); os.remove(out_path)

    def test_export_csv_params_is_json_string(self):
        t, log_path, out_path = self._setup()
        t.export(out_path, format="csv")
        with open(out_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        params_field = rows[0]["params"]
        parsed = json.loads(params_field)
        assert isinstance(parsed, dict)
        os.remove(log_path); os.remove(out_path)

    def test_export_default_format_is_json(self):
        t, log_path, out_path = self._setup()
        t.export(out_path)              # no format= argument
        with open(out_path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        os.remove(log_path); os.remove(out_path)

    def test_export_invalid_format_raises_value_error(self):
        t, log_path, out_path = self._setup()
        with pytest.raises(ValueError):
            t.export(out_path, format="xml")
        os.remove(log_path); os.remove(out_path)

    def test_export_invalid_format_error_message(self):
        t, log_path, out_path = self._setup()
        with pytest.raises(ValueError, match="xml"):
            t.export(out_path, format="xml")
        os.remove(log_path); os.remove(out_path)

