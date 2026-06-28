from pathlib import Path

from app.store import FileStore


def _make_file(tmp_path: Path, name: str = "f.txt") -> str:
    p = tmp_path / name
    p.write_text("hi")
    return str(p)


def test_register_and_get_roundtrip(tmp_path):
    store = FileStore(ttl_seconds=100, now=lambda: 1000.0)
    path = _make_file(tmp_path)
    fid = store.register(path)
    got = store.get(fid)
    assert got is not None and got.exists()


def test_get_unknown_id_returns_none():
    store = FileStore(ttl_seconds=100, now=lambda: 1000.0)
    assert store.get("nope") is None


def test_expired_entry_returns_none_and_deletes_file(tmp_path):
    clock = {"t": 1000.0}
    store = FileStore(ttl_seconds=100, now=lambda: clock["t"])
    path = _make_file(tmp_path)
    fid = store.register(path)
    clock["t"] = 2000.0  # well past ttl
    assert store.get(fid) is None
    assert not Path(path).exists()


def test_sweep_removes_only_expired(tmp_path):
    clock = {"t": 1000.0}
    store = FileStore(ttl_seconds=100, now=lambda: clock["t"])
    old = _make_file(tmp_path, "old.txt")
    store.register(old)
    clock["t"] = 1050.0
    new = _make_file(tmp_path, "new.txt")
    store.register(new)
    clock["t"] = 1160.0  # old expired (age 160 > 100), new still valid (age 110 > 100?)
    # old created@1000 age=160 expired; new created@1050 age=110 expired too -> both
    removed = store.sweep()
    assert removed == 2
    clock["t"] = 1100.0
    # reset scenario: only old expired
    store2 = FileStore(ttl_seconds=100, now=lambda: clock["t"])
    a = _make_file(tmp_path, "a.txt")
    store2.register(a)
    clock["t"] = 1150.0
    b = _make_file(tmp_path, "b.txt")
    store2.register(b)
    clock["t"] = 1205.0  # a age=105 expired, b age=55 valid
    assert store2.sweep() == 1
    assert not Path(a).exists()
    assert Path(b).exists()
