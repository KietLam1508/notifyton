import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="skyline-test-")
os.environ["SKYLINE_DATA"] = _TMP
os.environ["SKYLINE_DB"] = str(Path(_TMP) / "test.db")
os.environ["SKYLINE_DEMO"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from app import seed  # noqa: E402
from app.db import connect, init_db  # noqa: E402


@pytest.fixture
def conn():
    path = os.environ["SKYLINE_DB"]
    if os.path.exists(path):
        os.remove(path)
    c = connect(path)
    init_db(c)
    ids = seed.seed_catalog(c)
    seed.set_day(c, "2026-11-02")  # thứ Hai
    c.commit()
    yield _Conn(c, ids)
    c.close()


class _Conn:
    """Bọc sqlite3.Connection để gắn thêm ids của dữ liệu seed."""

    def __init__(self, c, ids):
        self._c = c
        self.ids = ids

    def __getattr__(self, name):
        return getattr(self._c, name)
