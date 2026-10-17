from domain.brigade_contact import build_brigade_contact, contact_name


def test_the_name_is_the_trimmed_display_name():
    assert contact_name("  Bu Rina ", "x@y.test") == "Bu Rina"


def test_a_missing_or_blank_display_name_falls_back_to_the_email_name():
    assert contact_name(None, "rina@y.test") == "rina"
    assert contact_name("   ", "rina@y.test") == "rina"


def test_a_real_brigade_contact_is_not_example_data():
    contact = build_brigade_contact("u7", "Bu Rina", "r@y.test", "Brigade", "riau")

    assert contact.id == "u7"
    assert contact.example is False
    assert contact.region == "riau"
