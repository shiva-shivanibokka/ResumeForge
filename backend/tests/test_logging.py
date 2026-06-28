import json

from app.logging import configure_logging, get_logger


def test_logs_emit_valid_json(capsys):
    configure_logging("INFO")
    log = get_logger("test")
    log.info("hello_event", foo="bar", n=3)
    out = capsys.readouterr().out.strip().splitlines()
    assert out, "expected at least one log line"
    record = json.loads(out[-1])
    assert record["event"] == "hello_event"
    assert record["foo"] == "bar"
    assert record["n"] == 3
    assert record["level"] == "info"
    assert "timestamp" in record
