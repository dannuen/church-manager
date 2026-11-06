"""Page modules. Each has ``ROUTES = [(method, pattern, handler), ...]``.

Cards C1-C3 add their modules here: import them and append them to ``PAGES``.
"""

from . import care, chi_phai, dashboard, families, people, people_file, search, setup

PAGES = [dashboard, search, setup]
PAGES += [people, people_file, families, chi_phai, care]  # card C1 (people_file: the People file, spec 001)

from . import calendar, money  # noqa: E402 - card C2

PAGES += [calendar, money]  # card C2

from . import copies, documents, lists, sent, settings  # noqa: E402 - card C3

PAGES += [documents, sent, lists, copies, settings]  # card C3
