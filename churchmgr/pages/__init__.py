"""Page modules. Each has ``ROUTES = [(method, pattern, handler), ...]``.

Cards C1-C3 add their modules here: import them and append them to ``PAGES``.
"""

from . import dashboard, search, setup

PAGES = [dashboard, search, setup]
