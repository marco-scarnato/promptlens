import csv
import json
import os
import uuid
from datetime import datetime


class Tracker:
    """Logs LLM interactions to a JSON file and supports querying and exporting."""

    def __init__(self, filepath: str) -> None:
        """Initialise the tracker.

        Args:
            filepath: Path to the JSON log file.  Created with an empty array
                      if it does not exist or is corrupted.
        """
        self.filepath = filepath

        if not os.path.exists(filepath):
            self._write([])
            return

        # File exists — validate it; reset to [] if corrupted or empty
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("root element is not a list")
        except (json.JSONDecodeError, ValueError):
            self._write([])

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _read(self) -> list:
        """Read and return the current log array from disk."""
        with open(self.filepath, encoding="utf-8") as f:
            return json.load(f)

    def _write(self, records: list) -> None:
        """Write *records* to the log file with 2-space indentation."""
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

    # ── Public API ────────────────────────────────────────────────────────────

    def log(
        self,
        model: str,
        template: str,
        params: dict,
        rendered: str,
        output: str,
    ) -> None:
        """Append a new interaction record to the log file.

        Args:
            model:    Name of the LLM used (e.g. ``"gpt-4o"``).
            template: The prompt template with placeholders.
            params:   Dictionary of values substituted into the template.
            rendered: The fully rendered prompt sent to the model.
            output:   The model's response.
        """
        record = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "model": model,
            "template": template,
            "params": params,
            "rendered": rendered,
            "output": output,
        }
        records = self._read()
        records.append(record)
        self._write(records)

    def query(
        self,
        model: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list:
        """Return log records filtered by the given criteria.

        Args:
            model:     If set, keep only records whose ``model`` matches exactly.
            date_from: ISO 8601 string; keep only records with
                       ``timestamp >= date_from``.
            date_to:   ISO 8601 string; keep only records with
                       ``timestamp <= date_to``.

        Returns:
            List of matching record dicts, in insertion order.
        """
        records = self._read()

        if model is not None:
            records = [r for r in records if r.get("model") == model]

        if date_from is not None:
            records = [r for r in records if r.get("timestamp", "") >= date_from]

        if date_to is not None:
            records = [r for r in records if r.get("timestamp", "") <= date_to]

        return records

    def export(self, output_path: str, format: str = "json") -> None:
        """Export all log records to *output_path*.

        Args:
            output_path: Destination file path.
            format:      ``"json"`` (default) or ``"csv"``.

        Raises:
            ValueError: If *format* is not ``"json"`` or ``"csv"``.
        """
        records = self.query()

        if format == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)

        elif format == "csv":
            fieldnames = ["id", "timestamp", "model", "template", "params", "rendered", "output"]
            with open(output_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for record in records:
                    row = {**record, "params": json.dumps(record.get("params", {}), ensure_ascii=False)}
                    writer.writerow(row)

        else:
            raise ValueError(
                f"Unsupported export format '{format}'. Use 'json' or 'csv'."
            )
