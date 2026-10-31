"""Church Manager: an offline database that helps one senior pastor run one church.

Data layer only (no UI here). Every function takes an explicit folder path or an
open ``sqlite3.Connection`` made by :func:`churchmgr.db.connect`.
"""

__version__ = "0.1.0"
