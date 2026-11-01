"""Page modules. Each has ``ROUTES = [(method, pattern, handler), ...]``.

Cards C1-C3 add their modules here: import them and append them to ``PAGES``.
"""

from . import care, chi_phai, dashboard, families, people, search, setup

PAGES = [dashboard, search, setup]
PAGES += [people, families, chi_phai, care]  # card C1
