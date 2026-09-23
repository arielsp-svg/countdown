"""Download and read the RO table (R4).

The table is fetched from the anonymous SharePoint direct link and read into
Row objects. A row whose RO date cell is empty or free text is skipped and
recorded, never alerted on (R4 edge cases).
"""
import csv
import io
import logging
import os
import re
import urllib.parse
import urllib.request
from datetime import date, datetime

from . import paths

log = logging.getLogger(__name__)

# Spec column list. Each entry is (field, list of accepted header spellings).
COLUMNS = [
    ("department", ["department", "dept"]),
    ("type_of_system", ["type of system", "system type", "type"]),
    ("platform", ["platform"]),
    ("nav_system", ["nav system", "navigation system", "nav"]),
    ("receiver_model", ["receiver model", "receiver"]),
    ("using_tod", ["using tod", "tod"]),
    ("comments", ["comments", "comment", "remarks"]),
    ("ro_date", ["ro date", "ro", "ro_date", "expiry", "expiry date"]),
]

REQUIRED = ("department", "ro_date")

# Day first. The table is maintained in a day-first locale; mm/dd is tried last
# and only when the leading field cannot be a day.
DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d",
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%d/%m/%y", "%d-%m-%y", "%d.%m.%y",
    "%m/%d/%Y", "%m-%d-%Y",
]


class TableError(Exception):
    """The link was unreachable, or the layout no longer holds the columns."""


class Row:
    __slots__ = [f for f, _ in COLUMNS] + ["row_number"]

    def __init__(self, row_number, values):
        self.row_number = row_number
        for field, _ in COLUMNS:
            setattr(self, field, values.get(field, ""))

    @property
    def key(self) -> str:
        """Stable identity for a system across reads.

        The RO date is deliberately excluded: when the table owner moves an RO
        date, the row is still the same system and keeps its snooze and its
        alert history (R11 edge case).
        """
        parts = [
            str(getattr(self, f) or "").strip().lower()
            for f in ("department", "type_of_system", "platform", "nav_system", "receiver_model")
        ]
        return "|".join(parts)

    @property
    def label(self) -> str:
        return str(self.platform or self.type_of_system or self.nav_system or "system").strip()

    def __repr__(self):
        return f"<Row {self.row_number} {self.label} {self.ro_date}>"


def _normalise(text) -> str:
    return re.sub(r"[\s_\-]+", " ", str(text or "").strip().lower())


def _map_headers(header_cells) -> dict:
    """Column index per field. Tolerates reordering and extra columns (R4)."""
    seen = {_normalise(cell): idx for idx, cell in enumerate(header_cells) if str(cell or "").strip()}
    mapping = {}
    for field, spellings in COLUMNS:
        for spelling in spellings:
            if spelling in seen:
                mapping[field] = seen[spelling]
                break
    missing = [f for f in REQUIRED if f not in mapping]
    if missing:
        raise TableError(
            "table is missing required column(s): " + ", ".join(missing)
            + "; headers found: " + ", ".join(sorted(seen)) 
        )
    return mapping


def parse_ro_date(value):
    """Return a date, or None when the cell is empty or holds free text."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = text.split(" ")[0]
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _rows_from_xlsx(payload: bytes):
    import openpyxl  # bundled into the .exe at build time

    book = openpyxl.load_workbook(io.BytesIO(payload), data_only=True, read_only=True)
    sheet = book[book.sheetnames[0]]
    for row in sheet.iter_rows(values_only=True):
        yield list(row)
    book.close()


def _rows_from_csv(payload: bytes):
    for encoding in ("utf-8-sig", "cp1255", "latin-1"):
        try:
            text = payload.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = payload.decode("utf-8", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    for row in csv.reader(io.StringIO(text), dialect):
        yield row


def parse(payload: bytes):
    """Return (rows, skipped). `skipped` lists rows with an unreadable RO date."""
    reader = _rows_from_xlsx if payload[:2] == b"PK" else _rows_from_csv
    raw_rows = list(reader(payload))

    header_index, mapping, last_error = None, None, None
    for idx, cells in enumerate(raw_rows):
        if not any(str(c or "").strip() for c in cells):
            continue
        try:
            mapping = _map_headers(cells)
        except TableError as exc:
            # Tolerate title rows above the real header, but only a few.
            if last_error is None:
                last_error = exc  # the first candidate is the likeliest header
            if idx < 10:
                continue
            raise
        header_index = idx
        break
    if mapping is None:
        # R4 edge case: a column was renamed, reordered away or removed.
        raise last_error or TableError("the file holds no header row")

    rows, skipped = [], []
    for offset, cells in enumerate(raw_rows[header_index + 1:], start=header_index + 2):
        if not any(str(c or "").strip() for c in cells):
            continue
        values = {}
        for field, col in mapping.items():
            values[field] = cells[col] if col < len(cells) else ""
        ro = parse_ro_date(values.get("ro_date"))
        if ro is None:
            skipped.append({
                "row": offset,
                "department": str(values.get("department") or "").strip(),
                "platform": str(values.get("platform") or "").strip(),
                "value": str(values.get("ro_date") or "").strip(),
            })
            continue
        values["ro_date"] = ro
        for field, _ in COLUMNS:
            if field != "ro_date":
                values[field] = str(values.get(field) or "").strip()
        rows.append(Row(offset, values))
    return rows, skipped


def _direct_link(url: str) -> str:
    """SharePoint share links serve a viewer page unless asked to download."""
    parts = urllib.parse.urlsplit(url)
    query = dict(urllib.parse.parse_qsl(parts.query))
    is_share_link = any(token in parts.path for token in ("/:x:/", "/:f:/", "/:u:/"))
    if is_share_link and "download" not in query:
        query["download"] = "1"
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


def _looks_like_a_url(source: str) -> bool:
    scheme = urllib.parse.urlsplit(source).scheme.lower()
    return scheme in ("http", "https", "file")


def _read_local(source: str) -> bytes:
    """Read the table from a folder, a mapped drive or a UNC share.

    An airgapped machine cannot reach SharePoint, so the table arrives some
    other way: a file server on the closed network, or a copy placed in the
    app's own folder. Both are ordinary paths from here.
    """
    path = os.path.expandvars(os.path.expanduser(source))
    if not os.path.isabs(path):
        # Relative to the .exe, so a table sitting beside it just works.
        path = os.path.join(paths.app_dir(), path)
    if not os.path.exists(path):
        raise TableError(f"the table was not found at {path}")
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError as exc:
        raise TableError(f"could not read the table at {path}: {exc}") from exc


def _read_remote(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(
        _direct_link(url),
        headers={"User-Agent": "Countdown/1.0", "Accept": "*/*"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except Exception as exc:  # urllib raises a wide family of errors
        raise TableError(f"could not reach the table link: {exc}") from exc


def download(source: str, timeout: int = 60) -> bytes:
    """Fetch the table bytes from wherever the configuration points.

    Accepts an http(s) link, a file:// URL, a Windows path, a UNC share such as
    \\\\server\\share\\ro.xlsx, or a name relative to the .exe.
    """
    if not source:
        raise TableError("no table source is configured in countdown.txt")
    source = source.strip().strip('"')
    if _looks_like_a_url(source):
        payload = _read_remote(source, timeout)
    else:
        payload = _read_local(source)
    if not payload:
        raise TableError("the table is empty")
    head = payload[:15].lower()
    if head.startswith(b"<!doctype html") or head[:6] == b"<html>":
        raise TableError("that link returned a web page, not the table; "
                         "it may have moved or been revoked")
    return payload


def fetch(url: str):
    return parse(download(url))
