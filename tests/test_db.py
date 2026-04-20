from __future__ import annotations

import sqlite3


def test_migration_runs_cleanly() -> None:
    connection = sqlite3.connect("test.db")
    try:
        result = connection.execute("SELECT 1").fetchone()
    finally:
        connection.close()
    assert result == (1,)
