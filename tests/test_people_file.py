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
from churchmgr import db, fake, i18n, lists, people, server, settings, xlsx
from churchmgr.i18n import english_left
from churchmgr.pages import people_file
from test_server import LiveServer, multipart_body

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TODAY = dt.date.today()
TOMORROW = TODAY + dt.timedelta(days=1)
TITLES_VI = ["Họ và tên", "Giới tính", "Ngày sinh", "Điện thoại", "Địa chỉ", "Ghi chú", "Trạng thái", "Ngày bắt đầu",
             "Gia đình", "Vai trò trong gia đình"]
TITLES_EN = ["Full name", "Gender", "Birth date", "Phone", "Address", "Note", "Status", "Start date", "Family",
             "Family role"]
SAVED_BEFORE_EN = "Every name in this file is already in the church. You may have saved this file before."


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
                                       "Gia đình A", "child"]],
                                     TITLES_EN[:8] + ["Ghi chú cá nhân", "FAMILY", "family role"])
        self.assertEqual(checks[0]["errors"], [])
        self.assertEqual(checks[0]["values"]["gender"], "F")
        self.assertNotIn("PN-MARKER-7", json.dumps(checks))  # a Private note column is never read
        self.assertEqual(ignored, ["Ghi chú cá nhân"])
        self.assertEqual((checks[0]["new_family"], checks[0]["values"]["family_role"]), ("Gia đình A", "Child"))

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
        self.assertEqual(sentences[2], "Row 4, Birth date: Birth date must be a real date like 31/12/1980, or a year "
                                       "from 1900 like 1980.")
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
        self.assertEqual(self.save(people_file.rows_json(checks)), (3, 0, []))  # 3 Persons, no new Family
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
        added, _families, again = self.save(json.dumps(tampered))
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
        self.assertEqual(self.save(people_file.rows_json(checks), code), (3, 0, []))
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
        added, _families, again = self.save(json.dumps(tampered), code)
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

    # A file saved before: Back after Save sends the file again and makes a new check page with a new code
    def test_a_file_saved_before_needs_a_second_yes(self):
        checks, _ = self.check(good_rows())
        self.assertFalse(people_file.all_in_church(checks))
        self.assertEqual(self.save(people_file.rows_json(checks))[0], 3)
        before = count(self.conn, "person")
        checks, _ = self.check(good_rows())  # the same file again
        self.assertTrue(people_file.all_in_church(checks))
        code = people_file.new_code()
        added, families, again = self.save(people_file.rows_json(checks), code)  # no second Yes
        self.assertEqual((added, families, [c["errors"] for c in again]), (0, 0, [[]] * 3))
        self.assertTrue(people_file.all_in_church(again))
        self.assertEqual(count(self.conn, "person"), before)
        rows = people_file.rows_json(checks)
        self.assertEqual(people_file.save_people_file(self.conn, rows, code, again=True), (3, 0, []))  # code not used up
        with self.assertRaises(i18n.TextError):  # still one Save per check page
            people_file.save_people_file(self.conn, rows, code, again=True)
        self.assertEqual(count(self.conn, "person"), before + 3)

    def test_some_names_in_the_church_keep_the_plain_save(self):
        people.add_person(self.conn, "Nguyễn Văn An")  # 1 row of 3
        checks, _ = self.check(good_rows())
        self.assertEqual([bool(c["warnings"]) for c in checks], [True, False, False])
        self.assertFalse(people_file.all_in_church(checks))
        self.assertEqual(self.save(people_file.rows_json(checks))[0], 3)
        checks, _ = self.check(good_rows()[1:2])  # one row only: a namesake, not a file saved before
        self.assertTrue(checks[0]["warnings"])
        self.assertFalse(people_file.all_in_church(checks))
        self.assertEqual(self.save(people_file.rows_json(checks))[0], 1)

    # ---- US3: Families
    def family_counts(self):
        return {t: count(self.conn, t) for t in ("person", "person_status", "family", "family_link", "private_note")}

    # T028
    def test_one_new_family_for_many_rows_and_an_existing_family_joined(self):
        old = people.add_family(self.conn, "Gia đình Lê Văn Bảy", "5 Hai Bà Trưng")
        before = self.family_counts()
        none7 = [None] * 7  # the 7 columns from Gender to Start date
        checks, ignored = self.check([
            ["Trần Văn Một", *none7[:6], "01/02/2020", "Gia đình Trần", "Chủ gia đình"],
            ["Nguyễn Thị Hai", None, None, None, "7 Lý Thường Kiệt", None, None, None, "gia dinh TRAN", "vợ/chồng"],
            ["Trần Văn Ba", None, None, None, "9 Phố Khác", None, None, None, "Gia đình Trần", "Con"],
            ["Trần Thị Bốn", *none7, "Gia   đình  Trần", "Other"],
            ["Lê Thị Năm", *none7, "gia dinh le van bay", "con"],
            ["Lê Văn Sáu", *none7, "GIA ĐÌNH LÊ VĂN BẢY", "Spouse"],
            ["Phạm Văn Bảy", *none7, None, None],  # no Family
        ])
        self.assertEqual((ignored, [c["errors"] for c in checks]), ([], [[]] * 7))
        self.assertEqual([c["new_family"] for c in checks], ["Gia đình Trần"] * 4 + [None] * 3)  # one name, as row 2
        self.assertEqual([c["family_id"] for c in checks], [None] * 4 + [old, old, None])
        self.assertEqual([c["values"]["family_role"] for c in checks],
                         ["Head", "Spouse", "Child", "Other", "Child", "Spouse", ""])
        self.assertEqual(self.family_counts(), before)  # the check saves nothing

        self.assertEqual(self.save(people_file.rows_json(checks)), (7, 1, []))
        after = self.family_counts()
        self.assertEqual({t: after[t] - before[t] for t in after},
                         {"person": 7, "person_status": 0, "family": 1, "family_link": 6, "private_note": 0})
        made = self.conn.execute("SELECT id, address FROM family WHERE name_folded = 'gia dinh tran'").fetchall()
        self.assertEqual(len(made), 1)  # one Family, also when 4 rows name it
        self.assertEqual(made[0]["address"], "7 Lý Thường Kiệt")  # the first Address among its rows
        today = TODAY.isoformat()
        self.assertEqual([(m["full_name"], m["family_role"], m["start_date"], m["end_date"])
                          for m in people.family_members(self.conn, made[0]["id"])],
                         [("Trần Văn Một", "Head", "2020-02-01", None), ("Nguyễn Thị Hai", "Spouse", today, None),
                          ("Trần Văn Ba", "Child", today, None), ("Trần Thị Bốn", "Other", today, None)])
        joined = [(m["full_name"], m["family_role"]) for m in people.family_members(self.conn, old)]
        self.assertEqual(joined, [("Lê Văn Sáu", "Spouse"), ("Lê Thị Năm", "Child")])
        self.assertEqual(people.get_family(self.conn, old)["address"], "5 Hai Bà Trưng")  # the Family is not changed

    def test_family_role_words_of_both_languages(self):
        words = {"Chủ gia đình": "Head", "chu gia dinh": "Head", "Vợ/Chồng": "Spouse", "Con": "Child",
                 "Người thân khác": "Other", "nguoi than khac": "Other", "HEAD": "Head", "spouse": "Spouse",
                 "Child": "Child", "other": "Other"}
        checks, _ = self.check([[f"Người {i}", *[None] * 7, "Gia đình Một", word] for i, word in enumerate(words)])
        self.assertEqual([c["errors"] for c in checks], [[]] * len(words))
        self.assertEqual([c["values"]["family_role"] for c in checks], list(words.values()))

    # T029
    def test_family_row_errors(self):
        people.add_family(self.conn, "Gia đình Đỗ")
        people.add_family(self.conn, "Gia dinh Do")  # the same name without diacritics: two Families
        none7 = [None] * 7
        checks, _ = self.check([
            ["Vai trò lạ", *none7, "Gia đình Mới", "Ông"],
            ["Hai Gia đình", *none7, "gia dinh do", "Con"],
            ["Không Gia đình", *none7, None, "Con"],
            ["Tên quá dài", *none7, "x" * 300, "Con"],
        ])
        self.assertEqual([[key for key, _s in c["errors"]] for c in checks],
                         [["family_role"], ["family"], ["family_role"], ["family"]])
        sentences = [c["errors"][0][1] for c in checks]
        self.assertEqual(sentences[0], "Row 2, Family role: not a Family role (Head, Spouse, Child, Other)")
        self.assertEqual(sentences[1], "Row 3, Family: Two or more Families have this name. Leave it empty here, "
                                       "then set the Family on the Person page.")
        self.assertEqual(sentences[2], "Row 4, Family role: A Family role needs a Family. Write the Family name, or "
                                       "leave Family role empty.")
        self.assertEqual(sentences[3], "Row 5, Family: Family name: use at most 120 characters.")
        self.assertEqual([c["family_id"] or c["new_family"] for c in checks], ["Gia đình Mới", None, None, None])
        i18n.set_lang_getter(lambda: "vi")
        checks, _ = self.check([["Vai trò lạ", *none7, "Gia đình Mới", "Ông"]])
        self.assertEqual(checks[0]["errors"], [
            ("family_role", "Dòng 2, Vai trò trong gia đình: không phải Vai trò trong gia đình (Chủ gia đình, "
                            "Vợ/Chồng, Con, Người thân khác)")])

    def test_a_family_error_saves_no_person_and_no_family(self):
        before = self.family_counts()
        rows = [[f"Trần Văn {i}", *[None] * 7, "Gia đình Trần", "Con"] for i in range(1, 6)]
        checks, _ = self.check(rows)
        self.assertEqual([c["errors"] for c in checks], [[]] * 5)
        tampered = json.loads(people_file.rows_json(checks))
        tampered[3]["values"]["family_role"] = "Ông"  # row 5, changed between the check page and Save
        added, families, again = self.save(json.dumps(tampered))
        self.assertEqual((added, families, [c["row"] for c in again if c["errors"]]), (0, 0, [5]))
        self.assertEqual(self.family_counts(), before)

        # a write that fails on row 5: the new Family and rows 1-4 are rolled back too
        real = people_file.people_pages.set_family_from_form
        calls = []

        def fifth_fails(conn, pid, form):
            calls.append(pid)
            if len(calls) == 5:
                raise i18n.TextError("people.err_family_role")
            return real(conn, pid, form)

        with mock.patch.object(people_file.people_pages, "set_family_from_form", side_effect=fifth_fails):
            with self.assertRaises(ValueError):
                self.save(people_file.rows_json(checks))
        self.assertEqual(len(calls), 5)
        self.assertEqual(self.family_counts(), before)

        # a second Family with this name, made between the check page and Save: the row is an error now
        people.add_family(self.conn, "Gia đình Trần")
        people.add_family(self.conn, "GIA DINH TRAN")
        before = self.family_counts()
        added, families, again = self.save(people_file.rows_json(checks))
        self.assertEqual((added, families), (0, 0))
        self.assertEqual([key for c in again for key, _s in c["errors"]], ["family"] * 5)
        self.assertEqual(self.family_counts(), before)

    def test_save_joins_a_family_made_after_the_check(self):
        """The check said "new Family"; the Family was made in another tab before Save: Save joins it."""
        checks, _ = self.check([["Trần Văn Một", *[None] * 7, "Gia đình Trần", "Head"]])
        self.assertEqual(checks[0]["new_family"], "Gia đình Trần")
        fid = people.add_family(self.conn, "Gia đình Trần")
        before = self.family_counts()
        self.assertEqual(self.save(people_file.rows_json(checks)), (1, 0, []))
        self.assertEqual([m["full_name"] for m in people.family_members(self.conn, fid)], ["Trần Văn Một"])
        self.assertEqual(count(self.conn, "family"), before["family"])

    # ---- An empty Family role comes from the Family; a Birth date may be a year only
    def test_family_role_default_head(self):
        """A Family and no Family role: Head when the Full name is the Family name (no diacritics, any case)."""
        old = people.add_family(self.conn, "Lê Văn Bảy")
        none7 = [None] * 7
        checks, _ = self.check([["Nguyễn Văn An", *none7, "nguyen van an", None],
                                ["le van  BAY", *none7, "LÊ VĂN BẢY", " "]])
        self.assertEqual([c["errors"] for c in checks], [[], []])
        self.assertEqual([(c["family_id"], c["new_family"], c["values"]["family_role"]) for c in checks],
                         [(None, "nguyen van an", "Head"), (old, None, "Head")])

    def test_family_role_default_other(self):
        none7 = [None] * 7
        checks, _ = self.check([["Trần Thị Bình", *none7, "nguyen van an", None],
                                ["Nguyễn Văn Anh", *none7, "Nguyễn Văn An", None],
                                ["Nguyễn Văn An", *none7, "Gia đình Nguyễn Văn An", None]])
        self.assertEqual([c["errors"] for c in checks], [[]] * 3)
        self.assertEqual([c["values"]["family_role"] for c in checks], ["Other"] * 3)

    def test_family_role_typed_wins(self):
        none7 = [None] * 7
        checks, _ = self.check([["Nguyễn Văn An", *none7, "Nguyễn Văn An", "Child"],
                                ["Trần Thị Bình", *none7, "nguyen van an", "chủ gia đình"],
                                ["Lê Văn Cường", *none7, "nguyen van an", "Vợ/Chồng"]])
        self.assertEqual([c["errors"] for c in checks], [[]] * 3)
        self.assertEqual([c["values"]["family_role"] for c in checks], ["Child", "Head", "Spouse"])

    def test_family_role_without_family_error(self):
        none7 = [None] * 7
        checks, _ = self.check([["Nguyễn Văn An", *none7, None, "Con"], ["Trần Thị Bình", *none7, None, None]])
        self.assertEqual(checks[0]["errors"], [("family_role", "Row 2, Family role: A Family role needs a Family. "
                                                                "Write the Family name, or leave Family role empty.")])
        self.assertEqual((checks[1]["errors"], checks[1]["values"]["family_role"]), ([], ""))  # no Family: no role

    def test_birth_year_only_text_and_number(self):
        before = self.family_counts()
        none5 = [None] * 5
        checks, _ = self.check([["Nguyễn Văn An", None, "1980", *none5, "Nguyễn Văn An", None],
                                ["Trần Thị Bình", None, 1980.0, *none5, "nguyen van an", None]])
        self.assertEqual([c["errors"] for c in checks], [[], []])
        self.assertEqual([c["values"]["birth_date"] for c in checks], ["1980-00-00", "1980-00-00"])
        self.assertEqual(self.save(people_file.rows_json(checks)), (2, 1, []))  # Save checks the rows again
        after = self.family_counts()
        self.assertEqual({t: after[t] - before[t] for t in after},
                         {"person": 2, "person_status": 0, "family": 1, "family_link": 2, "private_note": 0})
        made = self.conn.execute("SELECT id FROM family WHERE name_folded = 'nguyen van an'").fetchone()["id"]
        rows = self.conn.execute(
            "SELECT p.full_name, p.birth_date, l.family_role FROM family_link l JOIN person p ON p.id = l.person_id "
            "WHERE l.family_id = ? AND l.end_date IS NULL ORDER BY p.id", (made,)).fetchall()
        self.assertEqual([tuple(r) for r in rows], [("Nguyễn Văn An", "1980-00-00", "Head"),
                                                    ("Trần Thị Bình", "1980-00-00", "Other")])

    def test_birth_year_bad(self):
        before = self.family_counts()
        none5 = [None] * 5
        checks, _ = self.check([["Năm Sau", None, "2999", *none5, None, None],
                                ["Năm Sau Số", None, 2999.0, *none5, None, None],
                                ["Năm Xưa", None, "1850", *none5, None, None],
                                ["Năm Xưa Số", None, 1850.0, *none5, "Gia đình Xưa", None]])
        self.assertEqual([[key for key, _s in c["errors"]] for c in checks], [["birth_date"]] * 4)
        self.assertEqual([c["values"]["birth_date"] for c in checks], ["2999", "2999", "1850", "1850"])  # as typed
        sentences = [c["errors"][0][1] for c in checks]
        for row, sentence in zip((2, 3), sentences):
            self.assertTrue(sentence.startswith(f"Row {row}, Birth date: Birth date cannot be after today"), sentence)
        for row, sentence in zip((4, 5), sentences[2:]):
            self.assertEqual(sentence, f"Row {row}, Birth date: Birth date must be a real date like 31/12/1980, or "
                                       "a year from 1900 like 1980.")
        added, families, again = self.save(people_file.rows_json(checks))
        self.assertEqual((added, families, [c["row"] for c in again if c["errors"]]), (0, 0, [2, 3, 4, 5]))
        self.assertEqual(self.family_counts(), before)
        # a year changed between the check page and Save is checked again
        checks, _ = self.check([["Năm Đúng", None, "1980", *none5, None, None]])
        tampered = json.loads(people_file.rows_json(checks))
        tampered[0]["values"]["birth_date"] = "1850-00-00"
        added, families, again = self.save(json.dumps(tampered))
        self.assertEqual((added, [key for c in again for key, _s in c["errors"]]), (0, ["birth_date"]))
        self.assertEqual(self.family_counts(), before)


def part(data, name):
    """One part of a .xlsx file (bytes) as text, such as ``xl/worksheets/sheet2.xml``."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return zf.read(name).decode("utf-8")


class EmptyFileTest(_support.CopyTestCase):
    """T024: the empty People file of story 2. Sheet 1: the row of column titles only, in the language asked.
    Sheet 2: the Help sheet, with the one example row."""

    @staticmethod
    def titles(lang):
        return [i18n.t(f"people.file_col_{key}", lang) for key in people_file.COLUMNS]

    def test_sheet_1_has_the_title_row_only(self):
        for lang, words, names in (("vi", TITLES_VI, ("Mọi người", "Hướng dẫn")), ("en", TITLES_EN, ("People", "Help"))):
            data = people_file.empty_file(self.conn, lang)
            self.assertEqual(self.titles(lang), words)
            self.assertEqual(xlsx.read_first_sheet(data).rows, [words])  # no example row, no empty row
            book = part(data, "xl/workbook.xml")
            self.assertLess(book.index(f'<sheet name="{names[0]}"'), book.index(f'<sheet name="{names[1]}"'))
            # the columns of sheet 1 are Text cells: a typed 0912345678 or 31/12/1980 stays as typed
            self.assertRegex(part(data, "xl/worksheets/sheet1.xml"), rf'<col min="1" max="{len(words)}"[^>]* style="1"')

    def test_help_sheet_names_every_column_and_the_active_status_items(self):
        lists.set_active(self.conn, self.status("visitor"), False)  # a hidden Status item is not offered
        names = [item["name"] for item in lists.get_list(self.conn, "status")]
        self.assertEqual(names, ["Member", "Attender", "Left", "Passed away"])
        for lang in i18n.LANGS:
            help_xml = part(people_file.empty_file(self.conn, lang), "xl/worksheets/sheet2.xml")
            self.assertNotIn("[[", help_xml)
            for words in self.titles(lang) + names:
                self.assertIn(words, help_xml)
            self.assertNotIn("Visitor", help_xml)
            self.assertIn("Nam, Nữ, Male, Female, M, F", help_xml)
        lines = {row[0]: row[1] for row in people_file.help_rows(self.conn, "en") if len(row) == 2}
        self.assertEqual(lines["Full name"], "Required. The name of one Person.")
        self.assertEqual(lines["Status"], "Optional. A name of the Status list: Member, Attender, Left, Passed away.")
        self.assertEqual(lines["Gender"], "Optional. One of these words: Nam, Nữ, Male, Female, M, F.")
        self.assertEqual(lines["Family role"], "Optional, and only with a Family: Chủ gia đình, Vợ/Chồng, Con, "
                                               "Người thân khác, Head, Spouse, Child, Other. Left empty with a Family: "
                                               "Head when the Full name is the Family name, else Other.")
        self.assertEqual(len(lines), len(people_file.COLUMNS) + 1)  # one line per column, under the 2 titles
        lines = {row[0]: row[1] for row in people_file.help_rows(self.conn, "vi") if len(row) == 2}
        self.assertEqual(lines["Vai trò trong gia đình"],
                         "Không bắt buộc, và chỉ điền khi có Gia đình: Chủ gia đình, Vợ/Chồng, Con, Người thân khác, "
                         "Head, Spouse, Child, Other. Để trống khi có Gia đình: Chủ gia đình nếu Họ và tên trùng với "
                         "tên Gia đình, nếu không thì Người thân khác.")

    def test_the_example_row_passes_the_check(self):
        """The example is the last row of the Help sheet, under the column titles. Put on sheet 1 it is a
        good row: the help shows a row the check accepts."""
        before = count(self.conn, "person")
        for lang, male, head in (("vi", "Nam", "Chủ gia đình"), ("en", "Male", "Head")):
            rows = people_file.help_rows(self.conn, lang)
            titles, example = rows[-2], rows[-1]
            self.assertEqual(titles, self.titles(lang))
            self.assertEqual(example[:3] + example[-2:], ["Nguyễn Văn An", male, "31/12/1980", "Gia đình Nguyễn Văn An",
                                                          head])
            checks, ignored = people_file.check_people_file(self.conn, xlsx.write([("x", [titles, example])]))
            self.assertEqual((len(checks), checks[0]["errors"], ignored), (1, [], []))
            self.assertEqual(checks[0]["status_id"], self.status("member"))  # the first active Status item
            self.assertEqual((checks[0]["new_family"], checks[0]["values"]["family_role"]),
                             ("Gia đình Nguyễn Văn An", "Head"))
        self.assertEqual(count(self.conn, "person"), before)

    def test_round_trip_three_rows_are_ok(self):
        """Get the empty file, add 3 rows under the titles, pick it: 3 rows, no error, no ignored column."""
        for lang in i18n.LANGS:
            rows = xlsx.read_first_sheet(people_file.empty_file(self.conn, lang)).rows
            checks, ignored = people_file.check_people_file(self.conn, xlsx.write([("x", rows + good_rows())]))
            self.assertEqual([c["errors"] for c in checks], [[], [], []])
            self.assertEqual(ignored, [])

    def test_family_columns_come_with_their_help_lines(self):
        """Story 3 reads Family and Family role: the empty file has the 10 titles of COLUMNS in order, each with its
        help line."""
        self.assertEqual(len(people_file.COLUMNS), 10)
        for lang in i18n.LANGS:
            data = people_file.empty_file(self.conn, lang)
            self.assertEqual(xlsx.read_first_sheet(data).rows, [self.titles(lang)])
            help_xml = part(data, "xl/worksheets/sheet2.xml")
            self.assertNotIn("[[", help_xml)
            self.assertIn("Chủ gia đình, Vợ/Chồng, Con, Người thân khác, Head, Spouse, Child, Other", help_xml)


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
        self.assertIn('Family role: <span lang="vi">Chủ gia đình, Vợ/Chồng, Con, Người thân khác</span>, '
                      '<span lang="en">Head, Spouse, Child, Other</span>. When Family is set and Family role is empty: '
                      'Head when the Full name is the Family name, else Other.', page)
        self.assertIn("Write dates like 31/12/1980; a Birth date may be a year only, like 1980.", page)
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
        self.assertIn("Row 5, Birth date: Birth date must be a real date like 31/12/1980, or a year from 1900 like "
                      "1980.", page)
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
        rows = [[f"Khúc Văn Đôi {n}", *[None] * 7] for n in ("Một", "Hai", "Ba")]  # names of its own: a shared church
        before = count(self.db(), "person")
        _status, page = self.pick(people_xlsx(rows))
        form = self.save_form(page)
        self.assertEqual(self.request("POST", "/people/file/save", form)[0], 303)
        status, _h, data = self.request("POST", "/people/file/save", form)
        self.assertEqual(status, 400)
        self.assertIn("This list was already saved. Open People to see them.", data.decode("utf-8"))
        self.assertEqual(count(self.db(), "person"), before + 3)
        _status, page2 = self.pick(people_xlsx(rows))
        self.assertNotEqual(self.save_form(page2)["code"], form["code"])  # each check page has its own code

    def test_two_saves_at_the_same_moment_add_the_rows_once(self):
        before = count(self.db(), "person")
        _status, page = self.pick(people_xlsx([[f"Khúc Văn Cùng {n}", *[None] * 7] for n in ("Một", "Hai", "Ba")]))
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

    def test_a_file_saved_before_asks_a_second_yes(self):
        """Save, Back, the browser sends the file again: a new check page with a new code. Every name is in the
        church now, so Save needs the box "Add them again anyway"."""
        rows = [[f"Khúc Văn Lặp {n}", *[None] * 7] for n in ("Một", "Hai", "Ba", "Bốn", "Năm")]
        before = count(self.db(), "person")
        _status, page = self.pick(people_xlsx(rows))
        self.assertIn("No row has an error.", page)
        self.assertNotIn('name="again"', page)
        self.assertEqual(self.request("POST", "/people/file/save", self.save_form(page))[0], 303)
        status, page = self.pick(people_xlsx(rows))
        self.assertEqual(status, 200)
        self.assertIn(SAVED_BEFORE_EN, page)
        self.assertNotIn("No row has an error.", page)
        save = re.search(r'<form class="form" action="/people/file/save".*?</form>', page, re.S).group(0)
        self.assertIn('<label for="f-again">Add them again anyway</label>', save)
        self.assertRegex(save, r'<input id="f-again" name="again" type="checkbox" value="1" required[^>]*>')
        self.assertEqual(save.count("<button"), 1)  # one Save, under the box
        self.assertLess(save.index('name="again"'), save.index("<button"))
        form = self.save_form(page)
        status, _h, data = self.request("POST", "/people/file/save", form)  # the box not ticked
        self.assertEqual(status, 400)
        self.assertIn(SAVED_BEFORE_EN, data.decode("utf-8"))
        self.assertEqual(count(self.db(), "person"), before + 5)
        self.assertEqual(self.request("POST", "/people/file/save", {**form, "again": "1"})[0], 303)
        self.assertEqual(self.request("POST", "/people/file/save", {**form, "again": "1"})[0], 400)  # once
        self.assertEqual(count(self.db(), "person"), before + 10)

    def test_one_name_of_three_in_the_church_keeps_the_plain_save(self):
        rows = [[f"Khúc Thị Một {n}", *[None] * 7] for n in ("A", "B", "C")]
        _s, page = self.pick(people_xlsx(rows[:1]))
        self.assertEqual(self.request("POST", "/people/file/save", self.save_form(page))[0], 303)
        before = count(self.db(), "person")
        _s, page = self.pick(people_xlsx(rows))
        self.assertIn("A Person with this name is already in the church.", page)
        self.assertIn("No row has an error.", page)
        self.assertNotIn('name="again"', page)
        self.assertEqual(self.request("POST", "/people/file/save", self.save_form(page))[0], 303)
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

    # T025: the empty file
    def test_empty_file(self):
        status, headers, data = self.request("GET", "/people/file/empty.xlsx")
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], XLSX_TYPE)
        self.assertEqual(headers["content-disposition"], server.content_disposition("People file.xlsx"))
        self.assertIn('filename="People file.xlsx"', headers["content-disposition"])
        self.assertEqual(xlsx.read_first_sheet(data).rows, [TITLES_EN])
        link = '<a class="btn secondary" href="/people/file/empty.xlsx">Get the empty file</a>'
        self.assertIn(link, self.get_text("/people/file")[2])
        status, page = self.pick(b"not a zip")  # the not-.xlsx page offers it too
        self.assertEqual(status, 400)
        self.assertIn(link, page)

    def test_empty_file_filled_in_then_picked(self):
        """Quickstart 1-2: get the empty file, add 3 rows under the titles, pick it: 3 OK rows and Save."""
        before = count(self.db(), "person")
        _s, _h, data = self.request("GET", "/people/file/empty.xlsx")
        status, page = self.pick(xlsx.write([("People", xlsx.read_first_sheet(data).rows + good_rows())]))
        self.assertEqual(status, 200, page[:2000])
        self.assertRegex(page, r"3 rows: 3 OK, 0 with errors, \d warnings")
        self.assertIn('action="/people/file/save"', page)
        self.assertNotIn("Ignored columns", page)
        self.assertEqual(count(self.db(), "person"), before)

    # T028-T029 through the pages
    def test_families_on_the_check_page_and_in_the_save_message(self):
        conn = self.db()
        fid, name = conn.execute("SELECT MIN(id), MIN(name) FROM family GROUP BY name_folded HAVING COUNT(*) = 1 "
                                 "ORDER BY 1 LIMIT 1").fetchone()
        before = {t: count(conn, t) for t in ("person", "family", "family_link")}
        members = len(people.family_members(conn, fid))
        none7 = [None] * 7
        rows = [["Hà Văn Một", *none7, "Gia đình Hà Mới", "Head"], ["Hà Thị Hai", *none7, "gia dinh ha moi", "vợ/chồng"],
                ["Đinh Văn Ba", *none7, name.upper(), "child"]]
        status, page = self.pick(people_xlsx(rows, TITLES_EN))
        self.assertEqual(status, 200, page[:2000])
        self.assertRegex(page, r"3 rows: 3 OK, 0 with errors, \d warnings")
        for title in ("Family", "Family role"):
            self.assertIn(f'<th scope="col">{title}</th>', page)
        new_family = '<span lang="vi">Gia đình Hà Mới</span> <span class="faint">new Family</span>'
        self.assertEqual(page.count(new_family), 2)
        self.assertIn(f'<td><span lang="vi">{html.escape(name)}</span></td><td>Child</td>', page)
        self.assertIn("<td>Spouse</td>", page)
        status, headers, data = self.request("POST", "/people/file/save", self.save_form(page))
        self.assertEqual(status, 303, data.decode("utf-8")[:2000])
        msg = urllib.parse.parse_qs(urllib.parse.urlsplit(headers["location"]).query)["msg"]
        self.assertEqual(msg, ["3 people added. 1 new Family made."])
        conn = self.db()
        after = {t: count(conn, t) for t in before}
        self.assertEqual({t: after[t] - before[t] for t in after}, {"person": 3, "family": 1, "family_link": 3})
        self.assertEqual(len(people.family_members(conn, fid)), members + 1)

    def test_a_family_error_shows_no_save_button(self):
        before = {t: count(self.db(), t) for t in ("person", "family")}
        status, page = self.pick(people_xlsx([["Hà Văn Bốn", *[None] * 7, "Gia đình Hà Bốn", "Ông"]], TITLES_EN))
        self.assertEqual(status, 200)
        self.assertNotIn('action="/people/file/save"', page)
        self.assertIn("Row 2, Family role: not a Family role (Head, Spouse, Child, Other)", page)
        self.assertEqual({t: count(self.db(), t) for t in before}, before)

    def test_check_page_shows_default_role(self):
        """An empty Family role: the check page shows the role Save will use, and a year-only Birth date as 1980."""
        none5 = [None] * 5
        rows = [["Khúc Văn Niên", None, "1980", *none5, "khuc van nien", None],
                ["Khúc Thị Niên", None, 1980.0, *none5, "Khúc Văn Niên", None]]
        status, page = self.pick(people_xlsx(rows, TITLES_EN))
        self.assertEqual(status, 200, page[:2000])
        self.assertRegex(page, r"2 rows: 2 OK, 0 with errors, \d warnings")
        self.assertIn("<td>Head</td>", page)
        self.assertIn("<td>Other</td>", page)
        self.assertEqual(len(re.findall(r'<td[^>]*><span class="num">1980</span></td>', page)), 2)
        self.assertNotIn("00/00", page)
        status, _h, data = self.request("POST", "/people/file/save", self.save_form(page))
        self.assertEqual(status, 303, data.decode("utf-8")[:2000])
        saved = self.db().execute(
            "SELECT p.full_name, p.birth_date, l.family_role FROM person p JOIN family_link l ON l.person_id = p.id "
            "WHERE p.full_name LIKE 'Khúc % Niên' AND l.end_date IS NULL ORDER BY p.id").fetchall()
        self.assertEqual([tuple(r) for r in saved], [("Khúc Văn Niên", "1980-00-00", "Head"),
                                                     ("Khúc Thị Niên", "1980-00-00", "Other")])


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
        self.assertIn("Ngày viết như 31/12/1980; Ngày sinh có thể chỉ có năm, như 1980.", page)
        self.assertIn("Khi có Gia đình mà để trống Vai trò trong gia đình: Chủ gia đình nếu Họ và tên trùng với tên "
                      "Gia đình, nếu không thì Người thân khác.", page)

    def test_check_page_shows_default_role(self):
        none5 = [None] * 5
        rows = [["Khúc Văn Niên", None, "1980", *none5, "khuc van nien", None],
                ["Khúc Thị Niên", None, 1980.0, *none5, "Khúc Văn Niên", None]]
        status, page = self.pick(people_xlsx(rows))
        self.assertEqual(status, 200, page[:2000])
        self.assertRegex(page, r"2 dòng: 2 hợp lệ, 0 có lỗi, \d cảnh báo")
        self.assertIn("<td>Chủ gia đình</td>", page)
        self.assertIn("<td>Người thân khác</td>", page)
        self.assertEqual(len(re.findall(r'<td[^>]*><span class="num">1980</span></td>', page)), 2)
        self.assertNotIn("00/00", page)
        self.assert_vietnamese(page)
        status, page = self.pick(people_xlsx([["Khúc Văn Xưa", None, "1850", *none5, None, None]]))
        self.assertIn("Dòng 2, Ngày sinh: Ngày sinh phải là một ngày có thật như 31/12/1980, hoặc một năm từ 1900 như "
                      "1980.", page)
        self.assert_vietnamese(page)

    def test_vi_families(self):
        none7 = [None] * 7
        status, page = self.pick(people_xlsx([["Hà Văn Một", *none7, "Gia đình Hà Mới", "Chủ gia đình"],
                                              ["Hà Văn Hai", *none7, None, "Con"]]))
        self.assertEqual(status, 200)
        self.assertIn('<span class="faint">Gia đình mới</span>', page)
        self.assertIn("Dòng 3, Vai trò trong gia đình: Vai trò trong gia đình cần có Gia đình. Hãy viết tên Gia đình, "
                      "hoặc để trống Vai trò trong gia đình.", page)
        self.assert_vietnamese(page)
        status, page = self.pick(people_xlsx([["Hà Văn Một", *none7, "Gia đình Hà Mới", "Chủ gia đình"]]))
        self.assertEqual(status, 200)
        self.assertIn("<td>Chủ gia đình</td>", page)
        self.assert_vietnamese(page)
        _s, headers, _d = self.request("POST", "/people/file/save", self.save_form(page))
        msg = urllib.parse.parse_qs(urllib.parse.urlsplit(headers["location"]).query)["msg"]
        self.assertEqual(msg, ["Đã thêm 1 người. Đã tạo 1 Gia đình mới."])

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

    def test_vi_file_saved_before(self):
        rows = [[f"Khúc Văn Lặp {n}", *[None] * 7] for n in ("Sáu", "Bảy")]
        _s, page = self.pick(people_xlsx(rows))
        self.assertEqual(self.request("POST", "/people/file/save", self.save_form(page))[0], 303)
        status, page = self.pick(people_xlsx(rows))
        self.assertEqual(status, 200)
        self.assertIn("Tất cả các tên trong tệp này đều đã có trong Hội Thánh. Có thể bạn đã lưu tệp này rồi.", page)
        self.assertIn('<label for="f-again">Vẫn thêm họ một lần nữa</label>', page)
        self.assert_vietnamese(page)

    def test_vi_empty_file(self):
        status, headers, data = self.request("GET", "/people/file/empty.xlsx")
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], XLSX_TYPE)
        self.assertEqual(headers["content-disposition"], server.content_disposition("Tep danh sach nguoi.xlsx"))
        self.assertEqual(xlsx.read_first_sheet(data).rows, [TITLES_VI])
        self.assertIn('<sheet name="Hướng dẫn"', part(data, "xl/workbook.xml"))
        _s, _h, page = self.get_text("/people/file")
        self.assertIn('<a class="btn secondary" href="/people/file/empty.xlsx">Lấy tệp mẫu trống</a>', page)
        self.assert_vietnamese(page)


if __name__ == "__main__":
    unittest.main()
