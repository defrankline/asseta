"""CSV and PDF rendering of a `ReportDefinition`'s rows.

CSV: UTF-8 with BOM (Excel), RFC 4180 quoting and CRLF line ends, and spreadsheet formula-injection protection: a
text cell starting with `=`, `+`, `-`, `@`, TAB or CR is prefixed with `'`. Numeric cells are rendered from typed
Decimals/ints by the server and are left as numbers. A truncated export ends with a note row.

PDF (fpdf2, built-in Helvetica): titled, paginated table with the header row repeated on every page, owner name,
applied filters, generation time in the tenant timezone and "Page X of N" footers. Built-in PDF fonts cover
Latin-1 only, so other characters are transliterated or replaced with "?" (the CSV keeps full Unicode).
"""

import csv
import io
import unicodedata
from collections.abc import Iterator

from fpdf import FPDF
from fpdf.fonts import FontFace

from asseta.modules.reports.definitions import (
    NUMERIC,
    ReportDefinition,
    ReportEnv,
    ReportRows,
    format_value,
)

BOM = chr(0xFEFF)
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
_TRANSLIT = str.maketrans(  # by code point: dashes/minus, ellipsis, curly quotes, no-break space, arrows, <= >=
    {
        0x2014: "-",
        0x2013: "-",
        0x2212: "-",
        0x2026: "...",
        0x2018: "'",
        0x2019: "'",
        0x201C: '"',
        0x201D: '"',
        0x00A0: " ",
        0x2192: "->",
        0x2264: "<=",
        0x2265: ">=",
    }
)


def truncation_note(cap: int) -> str:
    return f"TRUNCATED: only the first {cap:,} rows are included - narrow the filters to export the rest."


def safe_csv_cell(text: str, numeric: bool) -> str:
    """Neutralise spreadsheet formulas in text cells (OWASP CSV injection)."""
    if not numeric and text.startswith(_FORMULA_START):
        return "'" + text
    return text


def csv_chunks(defn: ReportDefinition, data: ReportRows, env: ReportEnv, cap: int) -> Iterator[bytes]:
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")

    def flush() -> bytes:
        chunk = buffer.getvalue().encode("utf-8")
        buffer.seek(0)
        buffer.truncate(0)
        return chunk

    buffer.write(BOM)
    writer.writerow([safe_csv_cell(c.label, False) for c in defn.columns])
    for i, row in enumerate(data.rows, start=1):
        writer.writerow(
            [safe_csv_cell(format_value(row.get(c.key), c.kind, env.timezone), c.kind in NUMERIC) for c in defn.columns]
        )
        if i % 500 == 0:
            yield flush()
    if data.truncated:
        writer.writerow([truncation_note(cap)])
    yield flush()


def latin1(text: str) -> str:
    text = unicodedata.normalize("NFKC", text.translate(_TRANSLIT))
    return text.encode("latin-1", "replace").decode("latin-1")


class _ReportPdf(FPDF):
    def __init__(self, title: str, footer_text: str, landscape: bool):
        super().__init__(orientation="L" if landscape else "P", unit="mm", format="A4")
        self._title, self._footer_text = latin1(title), latin1(footer_text)
        self.set_auto_page_break(auto=True, margin=14)
        self.set_margins(10, 10, 10)

    def footer(self) -> None:
        self.set_y(-10)
        self.set_font("Helvetica", size=7)
        self.set_text_color(110, 110, 110)
        self.cell(0, 5, self._footer_text, align="L")
        self.set_x(self.l_margin)
        self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="R")


def pdf_bytes(defn: ReportDefinition, data: ReportRows, env: ReportEnv, filters: dict[str, str], cap: int) -> bytes:
    generated = format_value(env.generated_at, "instant", env.timezone, human=True)
    footer = f"Asseta - {defn.title} - {env.owner_name} - generated {generated} ({env.timezone})"
    pdf = _ReportPdf(defn.title, footer, defn.landscape)
    pdf.set_title(latin1(f"{defn.title} - {env.owner_name}"))
    pdf.set_creator("Asseta")
    pdf.add_page()
    pdf.set_font("Helvetica", style="B", size=15)
    pdf.cell(0, 8, latin1(defn.title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=9)
    meta = [
        env.owner_name,
        f"Generated {generated} ({env.timezone}) by {env.generated_by}",
        "Filters: " + (", ".join(f"{k}={v}" for k, v in filters.items()) or "none"),
        f"Rows: {len(data.rows):,}",
        *defn.notes,
    ]
    for line in meta:
        pdf.multi_cell(0, 4.6, latin1(line), new_x="LMARGIN", new_y="NEXT")
    if data.truncated:
        _note(pdf, truncation_note(cap))
    pdf.ln(2)
    pdf.set_font("Helvetica", size=7)
    total = sum(c.width for c in defn.columns)
    widths = tuple(c.width / total * pdf.epw for c in defn.columns)
    aligns = tuple("RIGHT" if c.kind in NUMERIC else "LEFT" for c in defn.columns)
    headings = FontFace(emphasis="BOLD", fill_color=(232, 236, 241))
    with pdf.table(
        col_widths=widths,
        text_align=aligns,
        line_height=3.6,
        headings_style=headings,
        repeat_headings=1,
        borders_layout="HORIZONTAL_LINES",
        padding=0.8,
    ) as table:
        header = table.row()
        for c in defn.columns:
            header.cell(latin1(c.label))
        for row in data.rows:
            cells = table.row()
            for c in defn.columns:
                cells.cell(latin1(format_value(row.get(c.key), c.kind, env.timezone, human=True)))
    if not data.rows:
        pdf.set_font("Helvetica", style="I", size=9)
        pdf.cell(0, 8, "No rows match the filters.", new_x="LMARGIN", new_y="NEXT")
    if data.truncated:
        _note(pdf, truncation_note(cap))
    return bytes(pdf.output())


def _note(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", style="B", size=9)
    pdf.set_text_color(170, 40, 30)
    pdf.multi_cell(0, 5, latin1(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", size=7)
