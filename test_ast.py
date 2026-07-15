"""Small dependency-free syntax check for every active Python source file."""

import ast
from pathlib import Path


ACTIVE_PATHS = [
    Path("main.py"),
    Path("database.py"),
    Path("fsm_storage.py"),
    Path("text_utils.py"),
    Path("migrate_to_neon.py"),
    *sorted(Path("handlers").glob("*.py")),
    *sorted(Path("tests").glob("test_*.py")),
]


def main() -> None:
    checked = 0
    for path in ACTIVE_PATHS:
        if path.name == "mechanic_backup.py":
            continue
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        checked += 1
    print(f"Syntax OK: {checked} active Python files")


if __name__ == "__main__":
    main()
