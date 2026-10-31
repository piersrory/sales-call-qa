from sales_call_qa.redact import redact


def test_name_and_date_of_birth_are_replaced():
    text = "Thanks, Sarah Mitchell. Can you confirm your date of birth? It's 14 March 1985."
    redacted = redact(text)
    assert "Sarah" not in redacted and "Mitchell" not in redacted
    assert "1985" not in redacted


def test_product_facts_are_left_alone():
    text = (
        "Only accidental death is covered in the first 12 months. "
        "There is a 30-day cooling-off period with a full refund."
    )
    assert redact(text) == text
