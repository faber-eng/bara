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


GENAI_NOTICE = (
    "Warning: there are non-text parts in the response: ['function_call'], "
    "returning concatenated text result from text parts."
)
HTTPLIB2_NOTICE = (
    "httplib2 transport does not support per-request timeout. "
    "Set the timeout when constructing the httplib2.Http instance."
)


class Collector(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append((record.name, record.getMessage()))


def logged_after_configure(entries):
    from logs import configure_logging

    configure_logging()
    configure_logging()
    collector = Collector()
    logging.getLogger().addHandler(collector)
    try:
        for name, message in entries:
            logging.getLogger(name).warning(message)
    finally:
        logging.getLogger().removeHandler(collector)
    return collector.messages


def test_the_two_known_library_notices_are_dropped():
    assert (
        logged_after_configure(
            [
                ("google_genai.types", GENAI_NOTICE),
                ("google_auth_httplib2", HTTPLIB2_NOTICE),
            ]
        )
        == []
    )


def test_other_messages_from_those_libraries_still_log():
    entries = [
        ("google_genai.types", "Warning: something else"),
        ("google_auth_httplib2", "Making request"),
    ]

    assert logged_after_configure(entries) == entries


def test_the_same_text_from_another_logger_still_logs():
    entries = [("bara", GENAI_NOTICE)]

    assert logged_after_configure(entries) == entries


def test_configuring_twice_adds_one_filter_per_library():
    from logs import configure_logging

    configure_logging()
    configure_logging()

    assert len(logging.getLogger("google_genai.types").filters) == 1
