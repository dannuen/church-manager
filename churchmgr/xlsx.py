"""Read the first sheet of a .xlsx file and write a simple .xlsx, standard library only. Knows nothing about people.

A .xlsx file is a zip of XML files (an open ISO standard). Reading takes only the cell values of the
first sheet: no styles, no formulas (a formula cell gives the value saved with it). Text comes back NFC.
Tags are matched by their local name, so both namespaces of the standard (transitional and strict) work.

Limits (a file comes from outside the app): the file at most ``MAX_FILE`` bytes, each XML part at most
``MAX_MEMBER`` bytes once unpacked (a zip bomb stops there), at most ``MAX_ROWS`` rows and
``MAX_COLUMNS`` columns with a value. A refused file raises ``TextError`` (a ``ValueError``).
"""

import datetime as _dt
import io
import posixpath
import re
import zipfile
import zlib
from typing import NamedTuple
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from . import text
from .i18n import TextError

MAX_FILE = 10 * 1024 * 1024  # bytes of the .xlsx file
MAX_MEMBER = 50 * 1024 * 1024  # bytes of one XML part once unpacked
MAX_ROWS = 5_001  # the title row and 5,000 rows
MAX_COLUMNS = 1_000  # the People file has 10; a value further right is refused, so a row stays small

_CELL_REF = re.compile(r"([A-Za-z]{1,3})([0-9]+)")
_DMY = re.compile(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})")
_YMD = re.compile(r"([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})")
_NOT_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")  # characters XML 1.0 cannot hold
_BROKEN = (zipfile.BadZipFile, zipfile.LargeZipFile, KeyError, IndexError, ElementTree.ParseError, StopIteration,
           NotImplementedError, RuntimeError, EOFError, OSError, zlib.error, UnicodeDecodeError)


class Sheet(NamedTuple):
    """The first sheet: ``rows[0]`` is sheet row 1. Every row has the same length; a cell is text,
    a number (``float``) or ``None`` (empty). ``date1904``: the file counts date numbers from 1904."""

    rows: list
    date1904: bool


# ---------------------------------------------------------------- reading

def _local(tag):
    """``{namespace}row`` -> ``row``."""
    return tag.rpartition("}")[2]


def _children(element, name):
    return [child for child in element if _local(child.tag) == name]


def _read(zf, name):
    """One part of the zip, at most ``MAX_MEMBER`` bytes unpacked (the size in the zip header can lie)."""
    with zf.open(name) as member:
        data = member.read(MAX_MEMBER + 1)
    if len(data) > MAX_MEMBER:
        raise TextError("people.file_err_too_big", mb=MAX_FILE // (1024 * 1024))
    return data


def _xml(zf, name):
    return ElementTree.fromstring(_read(zf, name))


def _rels(zf, path):
    """``{relation id: (type, part name)}`` of the part at ``path`` (from its ``_rels`` file);
    ``path`` ``""`` is the whole package (``_rels/.rels``)."""
    folder, file_name = posixpath.split(path)
    rels_name = posixpath.join(folder, "_rels", file_name + ".rels")
    if rels_name not in zf.namelist():
        return {}
    out = {}
    for rel in _xml(zf, rels_name).iter():
        if _local(rel.tag) == "Relationship" and rel.get("Id") and rel.get("Target"):
            target = rel.get("Target")
            name = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(folder, target))
            out[rel.get("Id")] = (rel.get("Type") or "", name)
    return out


def _run_text(element):
    """The text of a ``<si>`` or ``<is>``: every ``<t>``, rich text runs ``<r>`` too, never the
    phonetic guide ``<rPh>``."""
    parts = []
    for child in element:
        name = _local(child.tag)
        if name == "t":
            parts.append(child.text or "")
        elif name == "r":
            parts += [t.text or "" for t in _children(child, "t")]
    return "".join(parts)


def _column(name):
    """``"C"`` -> 3, ``"AA"`` -> 27."""
    number = 0
    for ch in name.upper():
        number = number * 26 + ord(ch) - 64
    return number


def _value(cell, shared):
    """The value of one ``<c>``: text, ``float`` or ``None``."""
    kind = cell.get("t") or "n"
    if kind == "inlineStr":
        found = _children(cell, "is")
        value = _run_text(found[0]) if found else ""
    else:
        found = _children(cell, "v")
        raw = found[0].text if found else None
        if raw is None or raw == "":
            return None
        if kind == "s":
            value = shared[int(raw)]
        elif kind == "b":
            value = "TRUE" if raw.strip() in ("1", "true") else "FALSE"
        elif kind == "d":  # a date written as text (strict files): keep the day
            value = raw.strip().partition("T")[0]
        elif kind in ("str", "e"):  # a formula's text, an error such as #N/A
            value = raw
        else:
            return float(raw)  # "abc" raises ValueError: not a real .xlsx file
    value = text.nfc(value)
    return value if value != "" else None


def _cells(sheet_xml, shared):
    """``{row number: {column number: value}}`` of the cells that have a value."""
    rows, row_number = {}, 0
    for row in sheet_xml.iter():
        if _local(row.tag) != "row":
            continue
        row_number = int(row.get("r") or row_number + 1)
        col_number = 0
        for cell in _children(row, "c"):
            ref = _CELL_REF.fullmatch(cell.get("r") or "")
            col_number = _column(ref.group(1)) if ref else col_number + 1
            value = _value(cell, shared)
            if value is None:
                continue
            if row_number > MAX_ROWS:
                raise TextError("people.file_err_too_many_rows")
            if col_number > MAX_COLUMNS:
                raise TextError("people.file_err_too_big", mb=MAX_FILE // (1024 * 1024))
            rows.setdefault(row_number, {})[col_number] = value
    return rows


def read_first_sheet(data):
    """Read the first sheet of the .xlsx file in ``data`` (bytes). Returns a :class:`Sheet`.

    ``people.file_err_not_xlsx`` when it is not a .xlsx file (an old .xls, a .docx, a broken file),
    ``people.file_err_too_big`` or ``people.file_err_too_many_rows`` over the limits.
    """
    if len(data) > MAX_FILE:
        raise TextError("people.file_err_too_big", mb=MAX_FILE // (1024 * 1024))
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            book_name = next((name for kind, name in _rels(zf, "").values() if kind.endswith("/officeDocument")),
                             "xl/workbook.xml")
            book = _xml(zf, book_name)
            date1904 = any(_local(e.tag) == "workbookPr" and (e.get("date1904") or "").lower() in ("1", "true")
                           for e in book.iter())
            first = next(e for e in book.iter() if _local(e.tag) == "sheet")
            rid = next(v for k, v in first.attrib.items() if _local(k) == "id")
            rels = _rels(zf, book_name)
            sheet_name = rels[rid][1]
            strings_name = next((name for kind, name in rels.values() if kind.endswith("/sharedStrings")),
                                "xl/sharedStrings.xml")
            shared = []
            if strings_name in zf.namelist():
                shared = [_run_text(si) for si in _children(_xml(zf, strings_name), "si")]
            cells = _cells(_xml(zf, sheet_name), shared)
    except TextError:
        raise
    except (ValueError, *_BROKEN) as exc:
        raise TextError("people.file_err_not_xlsx") from exc
    last_row = max(cells, default=0)
    width = max((col for row in cells.values() for col in row), default=0)
    rows = [[cells.get(r, {}).get(c) for c in range(1, width + 1)] for r in range(1, last_row + 1)]
    return Sheet(rows, date1904)


# ---------------------------------------------------------------- cell values

def cell_text(value):
    """A cell as text: a whole number without ``.0`` (``912345678.0`` -> ``"912345678"``, digits kept),
    other values stripped, an empty cell ``""``."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def cell_date(value, date1904):
    """A cell of a date column as ``YYYY-MM-DD``, or ``None`` when it is not a real date.

    A number is a spreadsheet date: days after 1899-12-30 (after 1904-01-01 when ``date1904``); a time
    of day is dropped. Text is read as ``dd/mm/yyyy``, ``d/m/yyyy`` or ``yyyy-mm-dd``.
    """
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if value < 1:
                return None
            start = _dt.date(1904, 1, 1) if date1904 else _dt.date(1899, 12, 30)
            return (start + _dt.timedelta(days=int(value))).isoformat()
        if isinstance(value, str):
            v = value.strip()
            if m := _DMY.fullmatch(v):
                return _dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
            if m := _YMD.fullmatch(v):
                return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except (ValueError, OverflowError):  # 31/02, a year past 9999
        return None
    return None


# ---------------------------------------------------------------- writing

_RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_DOC_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml"
_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
# One Text cell format (numFmtId 49, "@"): what is typed in it stays as typed (a leading 0, a date).
_STYLES = (
    f'<styleSheet xmlns="{_MAIN_NS}">'
    '<fonts count="1"><font><sz val="11"/></font></fonts>'
    '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/>'
    '</fill></fills>'
    '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>'
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
    '</styleSheet>'
)


def _x(value, quote=False):
    """Text for XML: no character XML cannot hold, ``&<>`` escaped (and ``"`` in an attribute)."""
    return escape(_NOT_XML.sub("", text.nfc(str(value))), {'"': "&quot;"} if quote else {})


def _column_name(col):
    """3 -> ``"C"``, 27 -> ``"AA"``."""
    out = ""
    while col:
        col, rest = divmod(col - 1, 26)
        out = chr(65 + rest) + out
    return out


def _sheet_xml(rows, text_columns):
    """One worksheet. With ``text_columns`` every used column has the Text format (``style="1"``), for
    the cells of the title row and for every cell typed into those columns later."""
    width = max((len(r) for r in rows), default=0)
    style = ' s="1"' if text_columns else ""
    cols = (f'<cols><col min="1" max="{width}" width="24" style="1" customWidth="1"/></cols>'
            if text_columns and width else "")
    lines = []
    for r, row in enumerate(rows, start=1):
        cells = []
        for c, value in enumerate(row, start=1):
            ref = f"{_column_name(c)}{r}"
            if value is None:
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">{_x(value)}</t></is></c>')
        lines.append(f'<row r="{r}">{"".join(cells)}</row>')
    return f'{_HEAD}<worksheet xmlns="{_MAIN_NS}">{cols}<sheetData>{"".join(lines)}</sheetData></worksheet>'


def write(sheets, text_columns=True):
    """A .xlsx file (bytes). ``sheets``: ``[(sheet name, rows)]``, each row a list of text, numbers or
    ``None``. With ``text_columns`` the columns of the first sheet are Text cells. The same input gives
    the same bytes."""
    n = len(sheets)
    overrides = "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="{_TYPE}.worksheet+xml"/>'
                        for i in range(1, n + 1))
    parts = {
        "[Content_Types].xml": (
            f'{_HEAD}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            f'<Override PartName="/xl/workbook.xml" ContentType="{_TYPE}.sheet.main+xml"/>'
            f'<Override PartName="/xl/styles.xml" ContentType="{_TYPE}.styles+xml"/>{overrides}</Types>'),
        "_rels/.rels": (f'{_HEAD}<Relationships xmlns="{_RELS_NS}"><Relationship Id="rId1" '
                        f'Type="{_DOC_NS}/officeDocument" Target="xl/workbook.xml"/></Relationships>'),
        "xl/workbook.xml": (
            f'{_HEAD}<workbook xmlns="{_MAIN_NS}" xmlns:r="{_DOC_NS}"><sheets>'
            + "".join(f'<sheet name="{_x(name[:31], quote=True)}" sheetId="{i}" r:id="rId{i}"/>'
                      for i, (name, _rows) in enumerate(sheets, start=1))
            + "</sheets></workbook>"),
        "xl/_rels/workbook.xml.rels": (
            f'{_HEAD}<Relationships xmlns="{_RELS_NS}">'
            + "".join(f'<Relationship Id="rId{i}" Type="{_DOC_NS}/worksheet" Target="worksheets/sheet{i}.xml"/>'
                      for i in range(1, n + 1))
            + f'<Relationship Id="rId{n + 1}" Type="{_DOC_NS}/styles" Target="styles.xml"/></Relationships>'),
        "xl/styles.xml": _HEAD + _STYLES,
    }
    for i, (_name, rows) in enumerate(sheets, start=1):
        parts[f"xl/worksheets/sheet{i}.xml"] = _sheet_xml(rows, text_columns and i == 1)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in parts.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))  # fixed: the same bytes every time
            zf.writestr(info, content.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
    return buf.getvalue()
