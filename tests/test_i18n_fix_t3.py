"""I18N-FIX-T r3: the Person Story says the group word once (L6).

The stored name of a Family, a Chi phái or a Ministry already holds its group word ("Gia đình …",
"Chi phái …", "Ban …"). Start lines keep "Label: name"; end lines and names inside a sentence give the
stored name alone, so a line never says "Left Family Gia đình X" or "Trưởng Chi phái of Chi phái Y".

The Person page shows the Story in the language of the page; the Hermes door (``agent person``) shows it
in English. Fake churches in temp folders only.
"""

import contextlib
import html
import io
import json
import pathlib
import re
import tempfile
import unittest

import _support
from churchmgr import agent, db, fake, lists, people, settings, story
from churchmgr.i18n import TEXT, english_left
from test_i18n_core import html_lang, switch
from test_server import LiveServer

FAMILY = "Gia đình Thử Ba"
CHI_PHAI = "Chi phái Thử Ba"
MINISTRY = "Ban Âm nhạc"
PERSON = "Trần Văn Thử Ba"

DECIDED = {
    "vi": {"people.story_family_end": "Rời {name}",
           "people.story_chi_phai": "Chi phái: {name} (của {family})",
           "people.story_truong": "Trưởng Chi phái: {name}",
           "people.story_truong_end": "Thôi làm Trưởng Chi phái: {name}",
           "people.story_ministry_end": "Thôi phục vụ trong {name}"},
    "en": {"people.story_family_end": "Left {name}",
           "people.story_chi_phai": "Chi phái: {name} ({family})",
           "people.story_truong": "Trưởng Chi phái: {name}",
           "people.story_truong_end": "No longer Trưởng Chi phái: {name}",
           "people.story_ministry_end": "Stopped serving in {name}"},
}

# The Story of the Person of add_story_person, oldest first: (date, kind, line). "{status}" is the name of
# the Member Status in the copy (data: "Tín hữu" in a Tiếng Việt copy, "Member" in an English one).
STORY = {
    "vi": [("2020-01-01", "status", "Trạng thái: {status}"),
           ("2020-01-01", "family", f"Gia đình: {FAMILY} (Chủ gia đình)"),
           ("2020-01-01", "chi_phai", f"Chi phái: {CHI_PHAI} (của {FAMILY})"),
           ("2020-01-01", "ministry", f"Ban ngành: {MINISTRY} (Trưởng ban)"),
           ("2021-01-01", "truong_chi_phai", f"Trưởng Chi phái: {CHI_PHAI}"),
           ("2022-01-01", "truong_chi_phai_end", f"Thôi làm Trưởng Chi phái: {CHI_PHAI}"),
           ("2023-01-01", "ministry_end", f"Thôi phục vụ trong {MINISTRY}"),
           ("2024-01-01", "family_end", f"Rời {FAMILY}")],
    "en": [("2020-01-01", "status", "Status: {status}"),
           ("2020-01-01", "family", f"Family: {FAMILY} (Head)"),
           ("2020-01-01", "chi_phai", f"Chi phái: {CHI_PHAI} ({FAMILY})"),
           ("2020-01-01", "ministry", f"Ministry: {MINISTRY} (Leader)"),
           ("2021-01-01", "truong_chi_phai", f"Trưởng Chi phái: {CHI_PHAI}"),
           ("2022-01-01", "truong_chi_phai_end", f"No longer Trưởng Chi phái: {CHI_PHAI}"),
           ("2023-01-01", "ministry_end", f"Stopped serving in {MINISTRY}"),
           ("2024-01-01", "family_end", f"Left {FAMILY}")],
}
# The group word twice (the bug L6), in any line.
TWICE = ("Family Gia đình", "Ministry Ban", "Trưởng Chi phái of Chi phái", "Trưởng Chi phái của Chi phái",
         "Rời Gia đình: Gia đình", "Gia đình Gia đình")
END_KINDS = ("family_end", "truong_chi_phai_end", "ministry_end")
TAGS = re.compile(r"<[^>]+>")


def add_story_person(conn):
    """A Person in FAMILY (in CHI_PHAI) from 2020: Trưởng Chi phái of CHI_PHAI in 2021, no longer in 2022;
    Leader in MINISTRY from 2020, stopped in 2023; left FAMILY in 2024. Returns the Person id."""
    member = lists.find_item(conn, "status", code="member")["id"]
    pid = people.add_person(conn, PERSON, status_id=member, start_date="2020-01-01")
    fid = people.add_family(conn, FAMILY)
    people.set_family(conn, pid, fid, "Head", "2020-01-01")
    cid = people.add_chi_phai(conn, CHI_PHAI)
    people.set_family_chi_phai(conn, fid, cid, "2020-01-01")
    people.set_truong_chi_phai(conn, cid, pid, "2021-01-01")
    people.set_truong_chi_phai(conn, cid, None, "2022-01-01")
    row = lists.find_item(conn, "ministry", name=MINISTRY)  # a default item of a Tiếng Việt copy only
    mid = row["id"] if row is not None else lists.add_item(conn, "ministry", MINISTRY)
    people.set_ministry(conn, pid, mid, "Leader", "2020-01-01")
    people.set_ministry(conn, pid, mid, None, "2023-01-01")
    people.set_family(conn, pid, None, None, "2024-01-01")
    return pid


def expected(conn, lang):
    """STORY[lang] with the name of the Member Status of this copy."""
    status = lists.find_item(conn, "status", code="member")["name"]
    return [(d, k, line.format(status=status) if k == "status" else line) for d, k, line in STORY[lang]]


def visible(fragment):
    return html.unescape(TAGS.sub("", fragment))


def shown(day):
    """``YYYY-MM-DD`` -> ``dd/mm/yyyy`` (D5: both languages)."""
    return f"{day[8:]}/{day[5:7]}/{day[:4]}"


class DecidedValuesTest(unittest.TestCase):
    def test_the_five_values_are_the_decided_ones(self):
        for lang, values in DECIDED.items():
            for key, value in values.items():
                self.assertEqual(TEXT[lang][key], value, (lang, key))

    def test_start_lines_keep_label_and_name(self):
        for lang, values in {"vi": ("Trạng thái: {name}", "Gia đình: {name} ({role})", "Ban ngành: {name} ({role})"),
                             "en": ("Status: {name}", "Family: {name} ({role})", "Ministry: {name} ({role})")}.items():
            keys = ("people.story_status", "people.story_family", "people.story_ministry")
            self.assertEqual(tuple(TEXT[lang][k] for k in keys), values, lang)


class _StoryLines(_support.CopyTestCase):
    """The Story function on one copy. Deleted at the end of this file: only its two subclasses run."""

    def setUp(self):
        super().setUp()
        self.pid = add_story_person(self.conn)

    def lines(self, lang=None):
        events = (story.person_story(self.conn, self.pid) if lang is None
                  else story.person_story(self.conn, self.pid, lang=lang))
        return [(e["date"], e["kind"], e["text"]) for e in events]

    def test_each_line_in_both_languages(self):
        for lang in ("vi", "en"):
            with self.subTest(lang=lang):
                self.assertEqual(self.lines(lang), expected(self.conn, lang))
        self.assertEqual(self.lines(), expected(self.conn, "en"))  # the Hermes door: English

    def test_the_group_word_is_said_once(self):
        for lang in ("vi", "en"):
            for _day, kind, line in self.lines(lang):
                for twice in TWICE:
                    self.assertNotIn(twice, line, (lang, kind))
                if kind in END_KINDS:
                    self.assertNotIn("Ban ngành: Ban Âm nhạc", line, (lang, kind))
            ends = {kind: line for _day, kind, line in self.lines(lang) if kind in END_KINDS}
            self.assertEqual(ends["family_end"].count("Gia đình"), 1, lang)
            self.assertEqual(ends["ministry_end"].count("Ban"), 1, lang)
            self.assertEqual(ends["truong_chi_phai_end"].count(CHI_PHAI), 1, lang)


class VietnameseCopyStoryTest(_StoryLines):
    LANG = "vi"


class EnglishCopyStoryTest(_StoryLines):
    LANG = "en"


class _Page(LiveServer, unittest.TestCase):
    """One fake church in ``LANG``, the Person of add_story_person and one live server per test class.
    Deleted at the end of this file: only its two subclasses (Tiếng Việt, English) run."""

    LANG = "vi"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="cm-test-")
        cls.root = pathlib.Path(cls.tmp.name)
        assert "onedrive" not in str(cls.root.resolve()).lower(), "temp folder must be outside OneDrive"
        cls.copy = cls.root / "fake"
        fake.build_fake_church(cls.copy, people=20, lang=cls.LANG)
        conn = db.connect(cls.copy / db.DB_NAME)
        try:
            cls.pid = add_story_person(conn)
            cls.want = {lang: expected(conn, lang) for lang in ("vi", "en")}
            settings.set_setting(conn, settings.HERMES_DOOR, "on")
        finally:
            conn.close()
        cls.start(cls.copy, cls.root, remember=False)

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.tmp.cleanup()

    def story_box(self, page):
        m = re.search(r'data-panel="story".*?</section>', page, re.S)
        assert m is not None, "no Story panel"
        return m.group(0)

    def story_rows(self, page):
        rows = re.findall(r"<tr data-row>(.*?)</tr>", self.story_box(page), re.S)
        return [tuple(visible(c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)) for r in rows]

    def test_the_person_page_story_says_the_group_word_once(self):
        path = f"/people/{self.pid}"
        status, _h, page = self.get_text(path)
        self.assertEqual(status, 200, page[:1500])
        self.assertEqual(html_lang(page), self.LANG)
        self.assertEqual(switch(page)[1:], ("true", "false") if self.LANG == "vi" else ("false", "true"))
        self.assertNotIn("[[", page)
        if self.LANG == "vi":
            self.assertEqual(english_left(page), [])
        # The page: newest first; lines of the same day keep the order of the Story.
        newest_first = sorted(self.want[self.LANG], key=lambda w: w[0], reverse=True)
        self.assertEqual(self.story_rows(page), [(shown(d), line) for d, _k, line in newest_first])
        box = visible(self.story_box(page))
        for twice in TWICE:
            self.assertNotIn(twice, box)

    def test_the_hermes_door_story_is_english(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = agent.main(["person", str(self.pid), "--copy", str(self.copy), "--copies-root", str(self.root)])
        answer = json.loads(out.getvalue())
        self.assertEqual((code, answer["ok"], answer["command"]), (0, True, "person"), answer)
        self.assertEqual([(e["date"], e["kind"], e["text"]) for e in answer["story"]], self.want["en"])


class VietnameseFixT3Test(_Page):
    LANG = "vi"


class EnglishFixT3Test(_Page):
    LANG = "en"


del _StoryLines, _Page

if __name__ == "__main__":
    unittest.main()
