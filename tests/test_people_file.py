"""People file: read and write .xlsx (``churchmgr/xlsx.py``) and add many Persons from one file
(``churchmgr/pages/people_file.py``). Every test works in a temp folder only."""

import datetime as dt
import html
import io
import json
import pathlib
import re
import tempfile
import threading
import unicodedata
import unittest
import urllib.parse
import zipfile
from unittest import mock

import _support
from churchmgr import db, fake, i18n, people, settings, xlsx
from churchmgr.i18n import english_left
from churchmgr.pages import people_file
from test_server import LiveServer, multipart_body

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
TODAY = dt.date.today()
TOMORROW = TODAY + dt.timedelta(days=1)
TITLES_VI = ["Họ và tên", "Giới tính", "Ngày sinh", "Điện thoại", "Địa chỉ", "Ghi chú", "Trạng thái", "Ngày bắt đầu"]
TITLES_EN = ["Full name", "Gender", "Birth date", "Phone", "Address", "Note", "Status", "Start date"]


def people_xlsx(rows, titles=TITLES_VI):
    """A People file (bytes): the title row, then ``rows``."""
    return xlsx.write([("Mọi người", [titles] + rows)])


def good_rows():
    """Three good rows: each Status typed another way (no diacritics, the English word); dates as text and as
    a date cell; a phone as a number cell."""
    return [
        ["Nguyễn Văn An", "Nam", "31/12/1980", "0912345678", "12 Lê Lợi", "Ghi chú thường", "tin huu", "01/01/2020"],
        ["Trần Thị Bình", "Nữ", 29221.0, 912345678.0, None, None, "Member", None],
        ["Lê Văn Cường", "M", None, None, None, None, "khach", "2024-05-06"],
    ]


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def zip_of(members):
    """A zip file (bytes) with ``{name: text}`` members."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def hand_made(sheet_data, shared=None, workbook_pr=""):
    """A small .xlsx made by hand, as another spreadsheet program could write it: the sheet sits in
    ``xl/worksheets/data.xml`` under the relation id ``rId7``."""
    members = {
        "xl/workbook.xml": (f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="{MAIN_NS}" '
                            f'xmlns:r="{REL_NS}">{workbook_pr}<sheets><sheet name="Mọi người" sheetId="1" '
                            'r:id="rId7"/></sheets></workbook>'),
        "xl/_rels/workbook.xml.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId7" Type="{REL_NS}/worksheet" Target="worksheets/data.xml"/></Relationships>'),
        "xl/worksheets/data.xml": f'<worksheet xmlns="{MAIN_NS}"><sheetData>{sheet_data}</sheetData></worksheet>',
    }
    if shared is not None:
        members["xl/sharedStrings.xml"] = f'<sst xmlns="{MAIN_NS}">{shared}</sst>'
    return zip_of(members)


class XlsxTest(unittest.TestCase):
    def assert_refused(self, data, key):
        with self.assertRaises(i18n.TextError) as cm:
            xlsx.read_first_sheet(data)
        self.assertIsInstance(cm.exception, ValueError)
        self.assertEqual(cm.exception.key, key)

    # ---- T006: round trip
    def test_round_trip_reads_only_the_first_sheet(self):
        nfd = unicodedata.normalize("NFD", "Nguyễn Văn Đức")
        rows = [["Họ và tên", "Điện thoại", "Ghi chú"], [nfd, None, "đầu"], [None, None, None],
                ["Trần Thị B", "0912345678", None]]
        data = xlsx.write([("Mọi người", rows), ("Hướng dẫn", [["không đọc"], ["trang 2"]])])
        sheet = xlsx.read_first_sheet(data)
        self.assertEqual(sheet.rows, [["Họ và tên", "Điện thoại", "Ghi chú"],
                                      ["Nguyễn Văn Đức", None, "đầu"],
                                      [None, None, None],
                                      ["Trần Thị B", "0912345678", None]])
        self.assertEqual(sheet.rows[1][0], unicodedata.normalize("NFC", nfd))  # NFC
        self.assertFalse(sheet.date1904)

    def test_written_file_is_a_real_xlsx(self):
        data = xlsx.write([("Mọi người", [["Họ và tên", "Ngày sinh"]]), ("Hướng dẫn", [["một", 2]])])
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = set(zf.namelist())
            sheet1 = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
            sheet2 = zf.read("xl/worksheets/sheet2.xml").decode("utf-8")
            styles = zf.read("xl/styles.xml").decode("utf-8")
        self.assertTrue({"[Content_Types].xml", "_rels/.rels", "xl/workbook.xml", "xl/_rels/workbook.xml.rels",
                         "xl/styles.xml"} <= names)
        self.assertIn('numFmtId="49"', styles)  # the Text cell format
        self.assertIn('style="1"', sheet1)  # the columns of sheet 1 are Text cells
        self.assertNotIn('style="1"', sheet2)
        self.assertIn("<v>2</v>", sheet2)  # a number stays a number
        self.assertEqual(data, xlsx.write([("Mọi người", [["Họ và tên", "Ngày sinh"]]), ("Hướng dẫn", [["một", 2]])]))

    # ---- T007: a file made by another program
    def test_shared_strings_rich_text_cell_kinds_and_places(self):
        shared = ('<si><t>Họ và tên</t></si>'
                  '<si><r><t xml:space="preserve">Nguyễn </t></r><r><rPr><b/></rPr><t>Văn A</t></r></si>')
        sheet = ('<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="inlineStr"><is><t>Điện thoại</t></is></c>'
                 '<c r="C1" t="str"><v>Ngày sinh</v></c></row>'
                 '<row r="3"><c r="A3" t="s"><v>1</v></c><c r="B3"><v>912345678</v></c><c r="C3"><v>29221</v></c>'
                 '</row>'
                 '<row r="7"><c r="C7" t="inlineStr"><is><r><t>cuối</t></r></is></c></row>')
        result = xlsx.read_first_sheet(hand_made(sheet, shared))
        self.assertEqual(result.rows, [
            ["Họ và tên", "Điện thoại", "Ngày sinh"],
            [None, None, None],
            ["Nguyễn Văn A", 912345678.0, 29221.0],
            [None, None, None], [None, None, None], [None, None, None],
            [None, None, "cuối"],
        ])
        self.assertFalse(result.date1904)

    def test_cells_without_a_place_follow_the_one_before(self):
        sheet = '<row><c><v>1</v></c><c><v>2</v></c></row><row><c r="B2" t="b"><v>1</v></c></row>'
        self.assertEqual(xlsx.read_first_sheet(hand_made(sheet)).rows, [[1.0, 2.0], [None, "TRUE"]])

    def test_date1904_flag(self):
        sheet = '<row r="1"><c r="A1"><v>1</v></c></row>'
        self.assertTrue(xlsx.read_first_sheet(hand_made(sheet, workbook_pr='<workbookPr date1904="1"/>')).date1904)
        self.assertFalse(xlsx.read_first_sheet(hand_made(sheet, workbook_pr='<workbookPr/>')).date1904)

    # ---- T008: refused files
    def test_not_a_xlsx_file(self):
        self.assert_refused(b"not a zip", "people.file_err_not_xlsx")
        self.assert_refused(b"", "people.file_err_not_xlsx")
        self.assert_refused(zip_of({"word/document.xml": "<w/>"}), "people.file_err_not_xlsx")  # no workbook
        bad = hand_made('<row r="1"><c r="A1"><v>1</v></c></row>')
        with zipfile.ZipFile(io.BytesIO(bad)) as zf:
            members = {n: zf.read(n) for n in zf.namelist()}
        members["xl/workbook.xml"] = b"<workbook"  # cut short: bad XML
        self.assert_refused(zip_of(members), "people.file_err_not_xlsx")
        self.assert_refused(hand_made('<row r="1"><c r="A1"><v>abc</v></c></row>'), "people.file_err_not_xlsx")
        self.assert_refused(hand_made('<row r="1"><c r="A1" t="s"><v>4</v></c></row>', "<si><t>a</t></si>"),
                            "people.file_err_not_xlsx")  # no shared string 4

    def test_too_big(self):
        data = xlsx.write([("A", [["Họ và tên"], ["Nguyễn Văn A"]])])
        with mock.patch.object(xlsx, "MAX_FILE", len(data) - 1):
            self.assert_refused(data, "people.file_err_too_big")
        with mock.patch.object(xlsx, "MAX_MEMBER", 200):  # the workbook and sheet XML unpack to more than 200 bytes
            self.assert_refused(data, "people.file_err_too_big")
        wide = hand_made('<row r="1"><c r="A1"><v>1</v></c><c r="AAA1"><v>2</v></c></row>')  # AAA = column 703
        with mock.patch.object(xlsx, "MAX_COLUMNS", 702):
            self.assert_refused(wide, "people.file_err_too_big")
        self.assertEqual(len(xlsx.read_first_sheet(wide).rows[0]), 703)

    def test_too_many_rows(self):
        rows = [["Họ và tên"]] + [[f"Người {i}"] for i in range(5_000)]
        self.assertEqual(len(xlsx.read_first_sheet(xlsx.write([("A", rows)])).rows), 5_001)
        self.assert_refused(xlsx.write([("A", rows + [["Người cuối"]])]), "people.file_err_too_many_rows")
        far = hand_made('<row r="1"><c r="A1"><v>1</v></c></row><row r="5002"><c r="A5002"><v>2</v></c></row>')
        self.assert_refused(far, "people.file_err_too_many_rows")
        # an empty cell far down (formatting only, no value) counts for nothing
        styled = hand_made('<row r="1"><c r="A1"><v>1</v></c></row><row r="900000"><c r="A900000" s="1"/></row>')
        self.assertEqual(xlsx.read_first_sheet(styled).rows, [[1.0]])

    # ---- T011: cell values
    def test_cell_date(self):
        self.assertEqual(xlsx.cell_date(29221.0, False), "1980-01-01")
        self.assertEqual(xlsx.cell_date(29221.75, False), "1980-01-01")  # a time of day is dropped
        self.assertEqual(xlsx.cell_date(27759.0, True), "1980-01-01")  # the 1904 date system
        self.assertEqual(xlsx.cell_date("31/12/1980", False), "1980-12-31")
        self.assertEqual(xlsx.cell_date(" 1/2/1980 ", False), "1980-02-01")
        self.assertEqual(xlsx.cell_date("1980-12-31", False), "1980-12-31")
        for bad in ("31/02/1990", "12/31/1980x", "1980/12/31", "hôm qua", "", None, 0.0, -5.0, 1e12):
            self.assertIsNone(xlsx.cell_date(bad, False), bad)

    def test_cell_text(self):
        self.assertEqual(xlsx.cell_text(912345678.0), "912345678")
        self.assertEqual(xlsx.cell_text(1.5), "1.5")
        self.assertEqual(xlsx.cell_text("  0912 345 678 "), "0912 345 678")
        self.assertEqual(xlsx.cell_text(None), "")


class PeopleFileTest(_support.CopyTestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(i18n.set_lang_getter, i18n._lang_getter)
        i18n.set_lang_getter(lambda: "en")  # the sentences of the check, as on an English page

    def check(self, rows, titles=TITLES_VI):
        return people_file.check_people_file(self.conn, people_xlsx(rows, titles))

    # ---- T013: column titles
    def test_map_titles_both_languages_without_diacritics(self):
        index, ignored = people_file.map_titles(
            ["Ho va ten", "ngay sinh", "Ghi chú cá nhân", None, "PHONE", "  trạng   THÁI ", "Start date", "full_name"])
        self.assertEqual(index, {"full_name": 0, "birth_date": 1, "phone": 4, "status": 5, "start_date": 6})
        self.assertEqual(ignored, ["Ghi chú cá nhân", "full_name"])  # a Private note is never read; a 2nd name column
        self.assertEqual(people_file.map_titles(["full_name"])[0], {"full_name": 0})

    def test_map_titles_needs_the_full_name_column(self):
        with self.assertRaises(i18n.TextError) as cm:
            people_file.map_titles(["Giới tính", "Điện thoại"])
        self.assertEqual(cm.exception.key, "people.file_err_no_name_column")
        self.assertIn("Full name", str(cm.exception))
        self.assertIn("Họ và tên", i18n.error_text(cm.exception, "vi"))

    # ---- US1
    # T014
    def test_check_good_rows_saves_nothing(self):
        before = count(self.conn, "person")
        rows = good_rows()
        rows.insert(2, [None] * 8)  # an empty row between people: skipped
        rows.append(["Phạm Thị Dung", "female", None, None, None, None, None, None])
        rows.append(["Đỗ Văn Em", "male", None, None, None, None, "Tín hữu", None])
        checks, ignored = self.check(rows)
        self.assertEqual(ignored, [])
        self.assertEqual([c["row"] for c in checks], [2, 3, 5, 6, 7])  # sheet rows; row 4 was empty
        self.assertEqual([c["errors"] for c in checks], [[]] * 5)
        self.assertEqual([c["values"]["gender"] for c in checks], ["M", "F", "M", "F", "M"])
        self.assertEqual([c["values"]["birth_date"] for c in checks], ["1980-12-31", "1980-01-01", "", "", ""])
        self.assertEqual([c["values"]["start_date"] for c in checks], ["2020-01-01", "", "2024-05-06", "", ""])
        self.assertEqual(checks[1]["values"]["phone"], "912345678")  # a number cell: no ".0", digits kept
        member = self.status("member")
        self.assertEqual([c["status_id"] for c in checks],
                         [member, member, self.status("visitor"), None, member])
        self.assertEqual(count(self.conn, "person"), before)

    def test_check_reads_english_titles_and_ignores_unknown_ones(self):
        checks, ignored = self.check([["Nguyễn Văn An", "F", None, None, None, None, None, None, "PN-MARKER-7",
                                       "Gia đình A"]],
                                     TITLES_EN + ["Ghi chú cá nhân", "Family"])
        self.assertEqual(checks[0]["errors"], [])
        self.assertEqual(checks[0]["values"]["gender"], "F")
        self.assertNotIn("PN-MARKER-7", json.dumps(checks))  # a Private note column is never read
        # Family comes with story 3 of spec 001: until then it is named as ignored, never dropped without a word
        self.assertEqual(ignored, ["Ghi chú cá nhân", "Family"])

    def test_check_refuses_a_file_with_no_people(self):
        for data in (people_xlsx([]), people_xlsx([[None] * 8, ["", " ", None, None, None, None, None, None]]),
                     xlsx.write([("Mọi người", [])])):
            with self.assertRaises(i18n.TextError) as cm:
                people_file.check_people_file(self.conn, data)
            self.assertEqual(cm.exception.key, "people.file_err_empty")

    # T015
    def test_row_errors_name_the_row_and_the_column(self):
        tomorrow = TOMORROW.strftime("%d/%m/%Y")
        checks, _ = self.check([
            [None, "Nam", "31/12/1980", "0912", None, None, None, None],  # row 2: no full name
            ["Gender X", "X", None, None, None, None, None, None],
            ["Bad day", None, "31/02/1990", None, None, None, None, None],
            ["Born tomorrow", None, tomorrow, None, None, None, None, None],
            ["Bad status", None, None, None, None, None, "Tin huuu", None],
            ["Starts tomorrow", None, None, None, None, None, "Member", tomorrow],
            ["Bad start", None, None, None, None, None, None, "hôm qua"],
        ])
        errors = [c["errors"] for c in checks]
        self.assertEqual([[key for key, _s in e] for e in errors],
                         [["full_name"], ["gender"], ["birth_date"], ["birth_date"], ["status"], ["start_date"],
                          ["start_date"]])
        sentences = [e[0][1] for e in errors]
        self.assertEqual(sentences[0], "Row 2, Full name: Full name is required.")
        self.assertEqual(sentences[1], "Row 3, Gender: Gender must be M or F, or empty.")
        self.assertEqual(sentences[2], "Row 4, Birth date: write the date as 31/12/1980")
        self.assertTrue(sentences[3].startswith("Row 5, Birth date: Birth date cannot be after today"), sentences[3])
        self.assertEqual(sentences[4], "Row 6, Status: not in the Status list (Member, Attender, Visitor, Left, "
                                       "Passed away)")
        self.assertTrue(sentences[5].startswith("Row 7, Start date: Start date cannot be after today"), sentences[5])
        self.assertEqual(sentences[6], "Row 8, Start date: write the date as 31/12/1980")
        self.assertEqual(checks[2]["values"]["birth_date"], "31/02/1990")  # shown as typed

    def test_row_error_in_vietnamese(self):
        i18n.set_lang_getter(lambda: "vi")
        checks, _ = self.check([[None, "Nam", None, None, None, None, None, None]])
        self.assertEqual(checks[0]["errors"], [("full_name", "Dòng 2, Họ và tên: Cần nhập Họ và tên.")])

    # T016
    def test_same_name_is_a_warning_not_an_error(self):
        people.add_person(self.conn, "Nguyễn Văn An")
        checks, _ = self.check([
            ["nguyen van  AN", None, None, None, None, None, None, None],
            ["Trần Bình", None, None, None, None, None, None, None],
            ["Lê Cường", None, None, None, None, None, None, None],
            ["TRAN BINH", None, None, None, None, None, None, None],
        ])
        self.assertEqual([c["errors"] for c in checks], [[]] * 4)
        self.assertEqual([c["warnings"] for c in checks], [
            ["A Person with this name is already in the church."],
            ["Same name as row 5."], [], ["Same name as row 3."]])

    # T017
    def save(self, rows_json_text, code=None):
        return people_file.save_people_file(self.conn, rows_json_text, code or people_file.new_code())

    def test_save_adds_every_row_with_its_status(self):
        before = {t: count(self.conn, t) for t in ("person", "person_status", "private_note")}
        checks, _ = self.check(good_rows())
        added, again = self.save(people_file.rows_json(checks))
        self.assertEqual((added, again), (3, []))
        self.assertEqual(count(self.conn, "person"), before["person"] + 3)
        self.assertEqual(count(self.conn, "person_status"), before["person_status"] + 3)
        self.assertEqual(count(self.conn, "private_note"), before["private_note"])
        rows = self.conn.execute(
            "SELECT p.full_name, p.gender, p.birth_date, p.phone, p.address, p.note, s.status_id, s.start_date, "
            "s.end_date FROM person p JOIN person_status s ON s.person_id = p.id ORDER BY p.id DESC LIMIT 3").fetchall()
        self.assertEqual([tuple(r) for r in reversed(rows)], [
            ("Nguyễn Văn An", "M", "1980-12-31", "0912345678", "12 Lê Lợi", "Ghi chú thường", self.status("member"),
             "2020-01-01", None),
            ("Trần Thị Bình", "F", "1980-01-01", "912345678", None, None, self.status("member"), TODAY.isoformat(),
             None),
            ("Lê Văn Cường", "M", None, None, None, None, self.status("visitor"), "2024-05-06", None),
        ])

    def test_save_is_all_or_nothing(self):
        before = {t: count(self.conn, t) for t in ("person", "person_status", "private_note")}
        checks, _ = self.check(good_rows())
        tampered = json.loads(people_file.rows_json(checks))
        tampered[2]["values"]["birth_date"] = "1990-02-31"  # changed between the check page and Save
        added, again = self.save(json.dumps(tampered))
        self.assertEqual(added, 0)
        self.assertEqual([c["row"] for c in again if c["errors"]], [4])
        self.assertEqual({t: count(self.conn, t) for t in before}, before)

        real = people_file.people_pages.add_person_from_form
        calls = []

        def third_fails(conn, form):
            calls.append(form["full_name"])
            if len(calls) == 3:
                raise i18n.TextError("errors.required", label="people.full_name")
            return real(conn, form)

        code = people_file.new_code()
        with mock.patch.object(people_file.people_pages, "add_person_from_form", side_effect=third_fails):
            with self.assertRaises(ValueError):
                self.save(people_file.rows_json(checks), code)
        self.assertEqual(len(calls), 3)
        self.assertEqual({t: count(self.conn, t) for t in before}, before)  # rows 1 and 2 were rolled back
        self.assertEqual(self.save(people_file.rows_json(checks), code)[0], 3)  # the code was rolled back too

    def test_save_refuses_a_bad_hidden_field(self):
        before = count(self.conn, "person")
        for bad in ("", "not json", "{}", "[]", '[{"row": "2", "values": {}}]', '[{"row": 2, "values": []}]', None):
            with self.assertRaises(i18n.TextError, msg=bad) as cm:
                self.save(bad)
            self.assertEqual(cm.exception.key, "people.file_err_pick_again")
        items = [{"row": n, "values": {"full_name": f"Người {n}"}} for n in range(2, 6)]
        with mock.patch.object(xlsx, "MAX_ROWS", 4):  # the title row and 3 rows (in the app: 5,001 and 5,000)
            with self.assertRaises(i18n.TextError) as cm:
                self.save(json.dumps(items))
            self.assertEqual(cm.exception.key, "people.file_err_too_many_rows")
            self.assertEqual(count(self.conn, "person"), before)
            self.assertEqual(self.save(json.dumps(items[:3]))[0], 3)

    # One check page = one Save
    def test_the_same_save_twice_adds_the_rows_once(self):
        before = count(self.conn, "person")
        checks, _ = self.check(good_rows())
        code = people_file.new_code()
        self.assertEqual(self.save(people_file.rows_json(checks), code), (3, []))
        with self.assertRaises(i18n.TextError) as cm:  # a double click, or Back and Save
            self.save(people_file.rows_json(checks), code)
        self.assertEqual(cm.exception.key, "people.file_err_saved_already")
        self.assertEqual(str(cm.exception), "This list was already saved. Open People to see them.")
        # after a restart: another connection to the church copy still knows the code
        other = db.connect(self.folder / db.DB_NAME)
        self.addCleanup(other.close)
        with self.assertRaises(i18n.TextError):
            people_file.save_people_file(other, people_file.rows_json(checks), code)
        self.assertEqual(count(self.conn, "person"), before + 3)

    def test_a_missing_code_saves_nothing(self):
        before = count(self.conn, "person")
        checks, _ = self.check(good_rows())
        for bad in (None, "", "short", "x" * 22 + "y", "<script>alert(1)</script>xx", 22):
            with self.assertRaises(i18n.TextError, msg=bad) as cm:
                people_file.save_people_file(self.conn, people_file.rows_json(checks), bad)
            self.assertEqual(cm.exception.key, "people.file_err_pick_again")
        self.assertEqual(count(self.conn, "person"), before)

    def test_a_save_with_row_errors_keeps_its_code(self):
        before = count(self.conn, "person")
        checks, _ = self.check(good_rows())
        code = people_file.new_code()
        tampered = json.loads(people_file.rows_json(checks))
        tampered[0]["values"]["full_name"] = " "
        added, again = self.save(json.dumps(tampered), code)
        self.assertEqual((added, [c["row"] for c in again if c["errors"]]), (0, [2]))
        self.assertEqual(count(self.conn, "person"), before)
        self.assertEqual(self.save(people_file.rows_json(checks), code)[0], 3)  # the code still works once
        self.assertEqual(count(self.conn, "person"), before + 3)

    def test_only_the_newest_codes_are_kept(self):
        checks, _ = self.check(good_rows()[:1])
        codes = [people_file.new_code() for _ in range(4)]
        self.assertEqual(len(set(codes)), 4)
        with mock.patch.object(people_file, "KEEP_CODES", 3):
            for code in codes:
                self.assertEqual(self.save(people_file.rows_json(checks), code)[0], 1)
        self.assertEqual(json.loads(settings.get_setting(self.conn, people_file.USED_CODES)), codes[1:])


class PagesBase(LiveServer):
    """One fake church in ``LANG`` and one live server per test class. The pages tests share the church:
    a test that saves adds people, so the others never count warnings exactly."""

    LANG = "en"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        cls.root = pathlib.Path(cls.tmp.name)
        assert "onedrive" not in str(cls.root.resolve()).lower()
        cls.copy = cls.root / "fake"
        fake.build_fake_church(cls.copy, people=20, lang=cls.LANG)
        cls.start(cls.copy, cls.root, remember=False)

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.tmp.cleanup()

    def db(self):
        conn = db.connect(self.copy / db.DB_NAME)
        self.addCleanup(conn.close)
        return conn

    def pick(self, data, name="nguoi.xlsx"):
        """POST the pick form. ``data`` ``None``: no file chosen (a browser sends an empty file part)."""
        body, ctype = multipart_body({}, {"file": (name, data) if data is not None else ("", b"")})
        status, _headers, page = self.request("POST", "/people/file", body, headers={"Content-Type": ctype})
        return status, page.decode("utf-8")

    @staticmethod
    def save_form(page):
        """The hidden fields of the Save form of a check page: ``rows`` and ``code``."""
        return {name: html.unescape(re.search(rf'name="{name}" value="([^"]*)"', page).group(1))
                for name in ("rows", "code")}


class PeopleFilePagesTest(PagesBase, unittest.TestCase):
    """T018: the pages through the real server, over an English fake church in a temp folder."""

    def test_people_page_links_to_the_people_file(self):
        status, _h, page = self.get_text("/people")
        self.assertEqual(status, 200)
        self.assertIn('<a class="btn secondary" href="/people/file">Add from .xlsx file</a>', page)

    def test_pick_page(self):
        status, _h, page = self.get_text("/people/file")
        self.assertEqual(status, 200)
        self.assertIn('<form class="form" action="/people/file" method="post" enctype="multipart/form-data">', page)
        self.assertRegex(page, r'<input class="input" id="f-file" name="file"[^>]* type="file"[^>]* accept="\.xlsx')
        self.assertIn("Full name", page)  # the help names the columns
        # the gender words of both languages, each marked with its language
        self.assertIn('Gender: <span lang="vi">Nam, Nữ</span>, <span lang="en">Male, Female</span>, M, F.', page)
        self.assertNotIn("[[", page)

    def test_check_then_save(self):
        before = count(self.db(), "person")
        status, page = self.pick(people_xlsx(good_rows()))
        self.assertEqual(status, 200, page[:2000])
        self.assertIn('action="/people/file/save"', page)
        self.assertRegex(page, r"3 rows: 3 OK, 0 with errors, \d warnings")
        self.assertIn('<span lang="vi">Nguyễn Văn An</span>', page)
        self.assertIn('href="/people/file"', page)  # Cancel
        self.assertEqual(count(self.db(), "person"), before)  # nothing saved by the check
        self.assertIn('<form class="form" action="/people/file/save" method="post" data-once>', page)
        status, headers, data = self.request("POST", "/people/file/save", self.save_form(page))
        self.assertEqual(status, 303, data.decode("utf-8")[:2000])
        location = headers["location"]
        self.assertTrue(location.startswith("/people?msg="), location)
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(location).query)["msg"], ["3 people added."])
        self.assertEqual(count(self.db(), "person"), before + 3)
        self.assertIn("3 people added.", self.get_text(location)[2])

    def test_error_row_shows_no_save_button(self):
        rows = good_rows() + [[None, "Nam", "31/02/1990", None, None, None, None, None]]
        status, page = self.pick(people_xlsx(rows))
        self.assertEqual(status, 200)
        self.assertNotIn('action="/people/file/save"', page)
        self.assertRegex(page, r"4 rows: 3 OK, 1 with errors, \d warnings")
        self.assertIn("Row 5, Full name: Full name is required.", page)
        self.assertIn("Row 5, Birth date: write the date as 31/12/1980", page)
        self.assertIn("Fix these rows in the file, then pick it again.", page)
        self.assertIn('<form class="form" action="/people/file" method="post" enctype="multipart/form-data">', page)

    def test_bad_file_and_no_file(self):
        before = count(self.db(), "person")
        status, page = self.pick(b"not a zip", "nguoi.xls")
        self.assertEqual(status, 400)
        self.assertIn("This is not a .xlsx file. Open it and save it as .xlsx.", page)
        self.assertIn('name="file"', page)  # the pick form again
        status, page = self.pick(None)
        self.assertEqual(status, 400)
        self.assertIn("Choose a .xlsx file first.", page)
        status, page = self.pick(people_xlsx([], ["Giới tính"]))
        self.assertEqual(status, 400)
        self.assertIn("No column has the title “Full name”.", page)
        status, _h, data = self.request("POST", "/people/file/save", {"rows": "not json"})
        self.assertEqual(status, 400)
        page = data.decode("utf-8")
        self.assertIn("The list on this page cannot be read. Pick the file again.", page)
        self.assertNotIn("not a .xlsx file", page)
        self.assertEqual(count(self.db(), "person"), before)

    def test_the_same_save_twice_adds_the_rows_once(self):
        """A double click, or Back and Save: the second Save adds nothing and says so."""
        before = count(self.db(), "person")
        _status, page = self.pick(people_xlsx(good_rows()))
        form = self.save_form(page)
        self.assertEqual(self.request("POST", "/people/file/save", form)[0], 303)
        status, _h, data = self.request("POST", "/people/file/save", form)
        self.assertEqual(status, 400)
        self.assertIn("This list was already saved. Open People to see them.", data.decode("utf-8"))
        self.assertEqual(count(self.db(), "person"), before + 3)
        _status, page2 = self.pick(people_xlsx(good_rows()))
        self.assertNotEqual(self.save_form(page2)["code"], form["code"])  # each check page has its own code

    def test_two_saves_at_the_same_moment_add_the_rows_once(self):
        before = count(self.db(), "person")
        _status, page = self.pick(people_xlsx(good_rows()))
        form = self.save_form(page)
        go = threading.Barrier(2)
        statuses = []

        def send():
            go.wait()
            statuses.append(self.request("POST", "/people/file/save", form)[0])

        threads = [threading.Thread(target=send) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(statuses), [303, 400])
        self.assertEqual(count(self.db(), "person"), before + 3)

    def test_save_rechecks_the_rows(self):
        before = count(self.db(), "person")
        _status, page = self.pick(people_xlsx(good_rows()))
        form = self.save_form(page)
        rows = json.loads(form["rows"])
        rows[0]["values"]["full_name"] = " "  # changed between the check page and Save
        status, _h, data = self.request("POST", "/people/file/save", {**form, "rows": json.dumps(rows)})
        page = data.decode("utf-8")
        self.assertEqual(status, 400)
        self.assertIn("Row 2, Full name: Full name is required.", page)
        self.assertNotIn('action="/people/file/save"', page)
        self.assertEqual(count(self.db(), "person"), before)


class PeopleFileVietnamesePagesTest(PagesBase, unittest.TestCase):
    """The same pages over a Vietnamese fake church: Vietnamese words only, no ``[[key]]``."""

    LANG = "vi"

    def assert_vietnamese(self, page):
        self.assertIn('<html lang="vi">', page)
        self.assertNotIn("[[", page)
        self.assertEqual(english_left(page), [])

    def test_vi_people_page_and_pick_page(self):
        _s, _h, page = self.get_text("/people")
        self.assertIn('<a class="btn secondary" href="/people/file">Thêm từ tệp .xlsx</a>', page)
        status, _h, page = self.get_text("/people/file")
        self.assertEqual(status, 200)
        self.assert_vietnamese(page)
        self.assertIn("Họ và tên", page)
        self.assertIn('Giới tính: <span lang="vi">Nam, Nữ</span>, <span lang="en">Male, Female</span>, M, F.', page)

    def test_vi_check_page(self):
        status, page = self.pick(people_xlsx(good_rows() + [["Lê Văn Cường", None, None, None, None, None, None,
                                                              "hôm qua"]]))
        self.assertEqual(status, 200)
        self.assertRegex(page, r"4 dòng: 3 hợp lệ, 1 có lỗi, \d cảnh báo")
        self.assertIn("Dòng 5, Ngày bắt đầu: hãy viết ngày như 31/12/1980", page)
        self.assertIn("Trùng tên với dòng 4.", page)
        self.assert_vietnamese(page)

    def test_vi_refused_files(self):
        status, page = self.pick(b"not a zip")
        self.assertEqual(status, 400)
        self.assertIn("Đây không phải tệp .xlsx.", page)
        self.assert_vietnamese(page)
        status, page = self.pick(None)
        self.assertEqual(status, 400)
        self.assertIn("Hãy chọn một tệp .xlsx trước.", page)

    def test_vi_save_message(self):
        _status, page = self.pick(people_xlsx(good_rows()[:1]))
        form = self.save_form(page)
        _s, headers, _d = self.request("POST", "/people/file/save", form)
        msg = urllib.parse.parse_qs(urllib.parse.urlsplit(headers["location"]).query)["msg"]
        self.assertEqual(msg, ["Đã thêm 1 người."])
        status, _h, data = self.request("POST", "/people/file/save", form)
        page = data.decode("utf-8")
        self.assertEqual(status, 400)
        self.assertIn("Danh sách này đã được lưu rồi. Hãy mở Mọi người để xem.", page)
        self.assert_vietnamese(page)
        status, _h, data = self.request("POST", "/people/file/save", {"rows": "[]", "code": form["code"]})
        self.assertIn("Không đọc được danh sách trên trang này. Hãy chọn lại tệp.", data.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
