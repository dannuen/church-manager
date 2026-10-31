"""Where the church copy lives.

A church copy is one folder with ``church.db`` and ``documents/``. It must stay
OUTSIDE OneDrive: any copy folder or copies root whose path contains
``onedrive`` (any case) is refused.

This is the only module that knows the default ``%LOCALAPPDATA%\\ChurchManager``.
"""

import os
from pathlib import Path

ENV_COPY = "CHURCH_MANAGER_COPY"
ENV_HOME = "CHURCH_MANAGER_HOME"
CURRENT_FILE = "current.txt"
DEFAULT_DIR_NAME = "ChurchManager"


class CopyPathError(ValueError):
    """The folder cannot hold a church copy (for example it is inside OneDrive)."""


def check_not_onedrive(path):
    """Return the resolved ``Path``. Raise ``CopyPathError`` if it is inside OneDrive."""
    if path is None or str(path).strip() == "":
        raise CopyPathError("A folder is required for the church copy.")
    raw = Path(path)
    resolved = raw.resolve()
    for candidate in (str(raw), str(raw.absolute()), str(resolved)):
        if "onedrive" in candidate.lower():
            raise CopyPathError(
                f"The church copy must not be inside OneDrive: {resolved}. "
                "Choose a folder outside OneDrive, for example under %LOCALAPPDATA%."
            )
    return resolved


def default_copies_root(env=None):
    """``%LOCALAPPDATA%\\ChurchManager`` (read from ``env``; nothing is created)."""
    env = os.environ if env is None else env
    base = env.get("LOCALAPPDATA")
    base_path = Path(base) if base else Path.home() / "AppData" / "Local"
    return base_path / DEFAULT_DIR_NAME


def read_current(copies_root):
    """Return the copy folder named in ``<copies_root>/current.txt``, or ``None``.

    A relative name is read as a folder inside ``copies_root``. The folder is
    returned even if it no longer exists, so the app can say so.
    """
    current = Path(copies_root) / CURRENT_FILE
    if not current.is_file():
        return None
    name = current.read_text(encoding="utf-8").strip()
    if not name:
        return None
    folder = Path(name)
    if not folder.is_absolute():
        folder = Path(copies_root) / folder
    return folder


def write_current(copies_root, folder):
    """Remember ``folder`` as the current church copy in ``<copies_root>/current.txt``."""
    root = check_not_onedrive(copies_root)
    target = check_not_onedrive(folder)
    try:
        name = str(target.relative_to(root))
    except ValueError:
        name = str(target)
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / (CURRENT_FILE + ".tmp")
    tmp.write_text(name + "\n", encoding="utf-8")
    os.replace(tmp, root / CURRENT_FILE)
    return root / CURRENT_FILE


def resolve(args_copy=None, args_root=None, env=None):
    """Return ``(copy_folder or None, copies_root)``, both resolved and checked.

    copies_root: ``--copies-root`` > env ``CHURCH_MANAGER_HOME`` > parent of the
    copy folder (when ``--copy`` or env ``CHURCH_MANAGER_COPY`` is given) >
    ``%LOCALAPPDATA%\\ChurchManager``.

    copy folder: ``--copy`` > env ``CHURCH_MANAGER_COPY`` > the folder named in
    ``<copies_root>/current.txt`` > ``None`` (first run).
    """
    env = os.environ if env is None else env
    given_copy = args_copy or env.get(ENV_COPY) or None

    if args_root:
        root = Path(args_root)
    elif env.get(ENV_HOME):
        root = Path(env[ENV_HOME])
    elif given_copy:
        root = Path(given_copy).resolve().parent
    else:
        root = default_copies_root(env)
    root = check_not_onedrive(root)

    copy = Path(given_copy) if given_copy else read_current(root)
    if copy is not None:
        copy = check_not_onedrive(copy)
    return copy, root
