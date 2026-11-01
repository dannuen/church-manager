import datetime
import unicodedata
import unittest

import _support  # noqa: F401  (puts the repo on sys.path)
from churchmgr import text


def nfd(s):
    return unicodedata.normalize("NFD", s)


class FoldTest(unittest.TestCase):
    def test_fold_vietnamese_name(self):
        self.assertEqual(text.fold("Nguyễn Hải Đăng"), "nguyen hai dang")

    def test_fold_nfd_input_gives_same_result(self):
        name = nfd("Nguyễn Hải Đăng")
        self.assertNotEqual(name, "Nguyễn Hải Đăng")  # really NFD
        self.assertEqual(text.fold(name), "nguyen hai dang")

    def test_fold_d_with_stroke(self):
        self.assertEqual(text.fold("Đ"), "d")
        self.assertEqual(text.fold("đ"), "d")
        self.assertEqual(text.fold("ĐẶNG VĂN ĐỨC"), "dang van duc")
        self.assertEqual(text.fold(nfd("ĐẶNG VĂN ĐỨC")), "dang van duc")

    def test_fold_hoi_thanh(self):
        self.assertEqual(text.fold("Hội Thánh"), "hoi thanh")

    def test_fold_spaces(self):
        self.assertEqual(text.fold("  Trần \t Thị\u00a0 Mỹ\nDung  "), "tran thi my dung")
        self.assertEqual(text.fold(""), "")
        self.assertEqual(text.fold(None), "")

    def test_every_vietnamese_vowel_and_d_folds_to_ascii(self):
        tones = ["", "\u0300", "\u0301", "\u0309", "\u0303", "\u0323"]
        chars = [text.nfc(base + tone) for base in "aăâeêioôơuưy" for tone in tones] + ["đ"]
        self.assertEqual(len(chars), 73)
        for char in chars:
            for case in (char, char.upper()):
                folded = text.fold(case)
                self.assertTrue(folded.isascii() and len(folded) == 1, (case, folded))

    def test_nfc(self):
        self.assertEqual(text.nfc(nfd("Hội Thánh")), "Hội Thánh")
        self.assertIsNone(text.nfc(None))

    def test_slugify(self):
        self.assertEqual(text.slugify("Hội Thánh Tin Lành Đà Lạt"), "hoi-thanh-tin-lanh-da-lat")
        self.assertEqual(text.slugify("  --Hội   Thánh!! "), "hoi-thanh")
        self.assertEqual(text.slugify("!!!"), "church")
        self.assertEqual(text.slugify(""), "church")


class CleanTest(unittest.TestCase):
    def test_clean_name(self):
        self.assertEqual(text.clean_name(nfd("  Nguyễn   Hải  Đăng ")), "Nguyễn Hải Đăng")
        for bad in ("", "   ", None):
            with self.assertRaises(ValueError):
                text.clean_name(bad)

    def test_clean_name_at_most_120_characters(self):
        """B3: 120 characters after cleaning are kept; 121 are refused with one sentence."""
        name = "Nguyễn " + "a" * 113
        self.assertEqual(len(name), 120)
        self.assertEqual(text.clean_name("  " + nfd(name) + "  ", "Full name"), name)  # counted after NFC and strip
        with self.assertRaises(ValueError) as ctx:
            text.clean_name(name + "b", "Family name")
        self.assertEqual(str(ctx.exception), "Family name: use at most 120 characters.")

    def test_clean_text(self):
        self.assertEqual(text.clean_text(nfd(" Hội Thánh ")), "Hội Thánh")
        self.assertIsNone(text.clean_text("   "))
        self.assertIsNone(text.clean_text(None))

    def test_check_date(self):
        self.assertEqual(text.check_date("2026-05-31"), "2026-05-31")
        self.assertEqual(text.check_date(datetime.date(2026, 1, 2)), "2026-01-02")
        for bad in ("2026-02-30", "2026-5-31", "20260531", "31/05/2026", "", None, 20260531):
            with self.assertRaises(ValueError, msg=bad):
                text.check_date(bad)

    def test_check_datetime(self):
        self.assertEqual(text.check_datetime("2026-05-31 09:30"), "2026-05-31 09:30")
        self.assertEqual(text.check_datetime(datetime.datetime(2026, 5, 31, 9, 30, 15)), "2026-05-31 09:30")
        for bad in ("2026-05-31", "2026-05-31 24:00", "2026-05-31 9:30", "2026-05-31T09:30"):
            with self.assertRaises(ValueError, msg=bad):
                text.check_datetime(bad)

    def test_now_and_today_format(self):
        now = text.now_text()
        self.assertEqual(text.check_datetime(now), now)
        today = text.today_text()
        self.assertEqual(text.check_date(today), today)

    def test_to_id(self):
        self.assertEqual(text.to_id(5), 5)
        self.assertEqual(text.to_id(" 12 "), 12)
        for bad in (0, -1, True, "abc", "1.5", 1.0, None, "٣"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                text.to_id(bad)

    def test_to_id_above_max_id(self):
        """B23: SQLite has no INTEGER above 2**63-1, so a bigger id is "no such row", not a crash."""
        self.assertEqual(text.MAX_ID, 9223372036854775807)
        self.assertEqual(text.to_id(str(text.MAX_ID)), text.MAX_ID)
        self.assertEqual(text.to_id(" 000000000000000000000042 "), 42)  # leading zeros are not "too big"
        for big in (text.MAX_ID + 1, 10**30, "9223372036854775808", "99999999999999999999", "9" * 5000):
            with self.assertRaisesRegex(ValueError, r"^No Person with that id\.$", msg=str(big)[:30]):
                text.to_id(big, "Person")

    def test_digits_to_int(self):
        self.assertEqual(text.digits_to_int("0"), 0)
        self.assertEqual(text.digits_to_int("007"), 7)
        self.assertEqual(text.digits_to_int("9223372036854775807"), text.MAX_ID)
        self.assertEqual(text.digits_to_int("9999999999999999999"), 9999999999999999999)  # 19 digits: exact
        self.assertEqual(text.digits_to_int("99999999999999999999"), text.MAX_ID + 1)
        self.assertEqual(text.digits_to_int("1" * 5000), text.MAX_ID + 1)  # int() would refuse 5000 digits

    def test_check_date_years(self):
        """B24: the date of an Offering, Expense or Sent document has a year from 1900 to 9999."""
        for day, want in (("1900-01-01", "1900-01-01"), (" 9999-12-31 ", "9999-12-31"),
                          (datetime.date(2026, 5, 31), "2026-05-31")):
            self.assertEqual(text.check_date_years(day), want)
        for day in ("1899-12-31", "0001-01-01", datetime.date(1, 1, 1)):
            with self.assertRaisesRegex(ValueError, r"^Date: use a year from 1900 to 9999\.$", msg=str(day)):
                text.check_date_years(day)
        with self.assertRaisesRegex(ValueError, r"^Date must be a real date"):
            text.check_date_years("2026-02-30")


if __name__ == "__main__":
    unittest.main()
