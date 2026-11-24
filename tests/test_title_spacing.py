"""Round 4 "Pearl", part 6 (docs/redesign-pearl-for-hermes.md): the page titles and the card titles are spaced
2.5px, the pastor's tweak value. He said yes on 2026-11-24 (card PP-ASK) to allow the CSS property name for this
one rule. The Avoid-word tests allow only that property name: the word alone is still an Avoid word, in code, in
tests and in ``web/``.

This file never writes the Avoid word alone: it takes it from the property name (``WORD``).
"""

import unittest

import _support
import test_db

PROPERTY = "letter-spacing"  # the CSS property name: allowed by CodeRulesTest.OUTSIDE_NAMES
WORD = PROPERTY.split("-")[0]  # the Avoid word alone
RULE = ".title-row h1, .panel h2 { letter-spacing: 2.5px; }"
READY = "/* ---------- round 4: ready for later pages"
STYLE = _support.ROOT / "web" / "style.css"


class TitleSpacingTest(unittest.TestCase):
    def test_the_rule_is_the_last_line_of_the_round_4_ready_block(self):
        css = STYLE.read_text(encoding="utf-8")
        self.assertEqual(css.count(READY), 1)
        block = css.split(READY, 1)[1]
        self.assertEqual(block.strip().splitlines()[-1], RULE)
        self.assertEqual(css.count(PROPERTY), 1)  # the one rule: nothing else is spaced

    def test_only_the_css_property_name_is_allowed(self):
        hits = test_db.CodeRulesTest.avoid_hits
        self.assertIn(WORD, test_db.CodeRulesTest.AVOID)  # the word stays on the Avoid list
        self.assertEqual(hits(RULE), [])
        self.assertEqual(hits(STYLE.read_text(encoding="utf-8")), [])
        for text in (WORD, f"a {WORD} to the church", f"{WORD}s", f"{WORD}_spacing = 1", f"spacing-{WORD}",
                     f"{PROPERTY}s", f"sent_{WORD}", f"{WORD}-head"):
            self.assertNotEqual(hits(text), [], text)

    def test_the_avoid_word_tests_still_find_the_word_alone_in_web(self):
        hits = test_db.CodeRulesTest.avoid_hits
        css = STYLE.read_text(encoding="utf-8")
        self.assertEqual(hits(css + f"\n/* a {WORD} */\n"), [WORD])
        self.assertEqual(hits(css.replace(PROPERTY, f"{WORD}-gap")), [WORD])


if __name__ == "__main__":
    unittest.main()
