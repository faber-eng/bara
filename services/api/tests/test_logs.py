import json
import logging

from logs import JsonFormatter


def make_record(**extra) -> logging.LogRecord:
    record = logging.LogRecord(
        "bara", logging.WARNING, __file__, 1, "model %s", ("fallback",), None
    )
    record.__dict__.update(extra)
    return record


def test_formats_a_record_as_one_json_line_with_severity():
    line = JsonFormatter().format(make_record())

    assert json.loads(line) == {
        "severity": "WARNING",
        "message": "model fallback",
        "logger": "bara",
    }


def test_merges_structured_fields_into_the_entry():
    record = make_record(fields={"event": "model_fallback", "code": 404})

    entry = json.loads(JsonFormatter().format(record))

    assert entry["event"] == "model_fallback"
    assert entry["code"] == 404
