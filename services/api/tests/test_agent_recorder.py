from bara_agent.recorder import MAX_SUMMARY_CHARS, one_line


def test_one_line_collapses_newlines_and_runs_of_spaces():
    assert one_line("bad args:\n  limit   too big\n") == "bad args: limit too big"


def test_one_line_caps_the_length():
    assert len(one_line("x" * 500)) == MAX_SUMMARY_CHARS
