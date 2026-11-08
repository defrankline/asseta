"""Builds one tenant's export ZIP in a single consistent snapshot (one REPEATABLE READ transaction, tenant RLS scope).
Rows stream to a temporary file so an export never has to fit in memory. The ZIP holds no credentials (see
export_tables): it is safe to keep on encrypted storage and to hand to the tenant."""

import csv
import hashlib
import io
import json
import uuid
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import IO, Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from asseta.modules.dataprotection.export_tables import EXCLUDED, export_tables, table_columns
from asseta.modules.dataprotection.models import ExportFormat

BATCH = 2000
EVIDENCE_COLUMNS = (
    "source",
    "id",
    "sha256",
    "size_bytes",
    "content_type",
    "purpose",
    "uploaded_at",
    "fetch_path",
)


def evidence_path(source: str, row_id: str) -> str:
    return f"/api/v1/tenant/data-exports/evidence/{source}/{row_id}/url"


def _scalar(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal | uuid.UUID):
        return str(value)
    if isinstance(value, bytes | memoryview):
        return bytes(value).hex()
    if isinstance(value, list | dict):
        return value  # CSV: rendered as JSON below
    return value


def _csv_cell(value: Any) -> Any:
    out = _scalar(value)
    if isinstance(out, list | dict):
        return json.dumps(out, default=str, ensure_ascii=False)
    # A cell starting with a formula character runs when the file is opened in a spreadsheet.
    if isinstance(value, str) and out[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + out
    return out


@dataclass
class TableResult:
    file: str
    rows: int
    sha256: str
    columns: list[str]


@dataclass
class BuildResult:
    tables: list[TableResult]
    row_count: int
    evidence_count: int
    alembic_version: str | None


def _rows(session: Session, table: str, columns: list[str]) -> Iterator[dict[str, Any]]:
    cols = ", ".join(f'"{c}"' for c in columns)
    # Table and column names come from the catalog, never from a request.
    stmt = text(f'SELECT {cols} FROM "{table}" WHERE tenant_id = :t')  # noqa: S608 - names from pg_catalog
    result = session.execute(stmt, {"t": session.info["export_tenant"]}, execution_options={"yield_per": BATCH})
    for batch in result.mappings().partitions():
        yield from (dict(row) for row in batch)


class _HashingWriter(io.RawIOBase):
    """Text-to-bytes sink hashing what passes into the ZIP member."""

    def __init__(self, inner: IO[bytes]):
        self._inner, self.digest = inner, hashlib.sha256()

    def writable(self) -> bool:
        return True

    def write(self, data: Any) -> int:
        raw = bytes(data)
        self.digest.update(raw)
        self._inner.write(raw)
        return len(raw)


def _write_csv(sink: _HashingWriter, columns: list[str], rows: Iterable[dict[str, Any]]) -> int:
    text_out = io.TextIOWrapper(io.BufferedWriter(sink), encoding="utf-8", newline="", write_through=True)
    writer = csv.writer(text_out)
    writer.writerow(columns)
    count = 0
    for row in rows:
        writer.writerow([_csv_cell(row[c]) for c in columns])
        count += 1
    text_out.flush()
    text_out.detach()
    return count


def _write_json(sink: _HashingWriter, rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    sink.write(b"[")
    for row in rows:
        chunk = json.dumps({k: _scalar(v) for k, v in row.items()}, default=str, ensure_ascii=False)
        sink.write((b"," if count else b"") + b"\n" + chunk.encode())
        count += 1
    sink.write(b"\n]\n")
    return count


EVIDENCE_SQL = """
SELECT 'capture_attachment' AS source, id, sha256, size_bytes, content_type, purpose, uploaded_at
  FROM capture_attachment WHERE tenant_id = :t
UNION ALL
SELECT 'machine_photo', id, sha256, size_bytes, content_type, 'MACHINE_PHOTO', uploaded_at
  FROM machine_photo WHERE tenant_id = :t
ORDER BY uploaded_at, id
"""


def _write_evidence(session: Session, archive: zipfile.ZipFile) -> int:
    count = 0
    with archive.open("evidence/manifest.csv", "w", force_zip64=True) as member:
        sink = _HashingWriter(member)
        text_out = io.TextIOWrapper(io.BufferedWriter(sink), encoding="utf-8", newline="", write_through=True)
        writer = csv.writer(text_out)
        writer.writerow(EVIDENCE_COLUMNS)
        result = session.execute(text(EVIDENCE_SQL), {"t": session.info["export_tenant"]})
        for row in result.mappings():
            writer.writerow(
                [
                    row["source"],
                    row["id"],
                    row["sha256"],
                    row["size_bytes"],
                    row["content_type"],
                    row["purpose"],
                    row["uploaded_at"].isoformat(),
                    evidence_path(str(row["source"]), str(row["id"])),
                ]
            )
            count += 1
        text_out.flush()
        text_out.detach()
    return count


README = """Asseta tenant data export
=========================
manifest.json          what this export contains: every file, its row count and SHA-256
data/<table>.{ext}     one file per table of the company's records, all ledgers included
evidence/manifest.csv  every evidence file (photos, receipts, signatures) with its SHA-256

Evidence files are not inside this archive. Each line of evidence/manifest.csv gives the `fetch_path` to request a
short-lived download link, with the same permission that created this export. Compare the SHA-256 of a downloaded
file with the manifest to prove it is unchanged.

Passwords, device tokens and tracker credentials are never exported. Keep this file on encrypted storage: it holds
the company's complete business records.
"""


def build_zip(
    session: Session, tenant_id: uuid.UUID, fmt: ExportFormat, target: Path, meta: dict[str, Any]
) -> BuildResult:
    """Writes the archive to `target`. The caller owns the transaction and its isolation level."""
    session.info["export_tenant"] = str(tenant_id)
    results: list[TableResult] = []
    ext = fmt.value.lower()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        archive.writestr("README.txt", README)
        for table in export_tables(session):
            columns = table_columns(session, table)
            name = f"data/{table}.{ext}"
            with archive.open(name, "w", force_zip64=True) as member:
                sink = _HashingWriter(member)
                rows = _rows(session, table, columns)
                count = _write_csv(sink, columns, rows) if fmt is ExportFormat.CSV else _write_json(sink, rows)
            results.append(TableResult(name, count, sink.digest.hexdigest(), columns))
        evidence = _write_evidence(session, archive)
        alembic = session.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
        manifest = {
            **meta,
            "format": fmt.value,
            "schema_revision": alembic,
            "tables": [{"file": t.file, "rows": t.rows, "sha256": t.sha256, "columns": t.columns} for t in results],
            "evidence_manifest": {"file": "evidence/manifest.csv", "files": evidence},
            "not_exported": EXCLUDED,
        }
        archive.writestr("manifest.json", json.dumps(manifest, indent=1, ensure_ascii=False))
    return BuildResult(results, sum(t.rows for t in results), evidence, alembic)
