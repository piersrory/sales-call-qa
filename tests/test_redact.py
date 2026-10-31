from sales_call_qa.redact import redact


def test_name_and_date_of_birth_are_replaced():
    text = "Thanks, Sarah Mitchell. Can you confirm your date of birth? It's 14 March 1985."
    redacted = redact(text)
    assert "Sarah" not in redacted and "Mitchell" not in redacted
    assert "1985" not in redacted


def test_spoken_dates_of_birth_are_replaced():
    # Each of these is how a customer or agent said it in data/calls
    for spoken in [
        "Born the fourteenth of March, 1987.",
        "It's the 14th of March, 1993.",
        "Born March 14th, 1986.",
        "March the fourteenth, 1961.",
        "Fourteenth of March, 1984.",
        "The fourteenth of March, nineteen fifty-one.",
        "That's the twenty-third of May, two thousand and one.",
        "It's 14/3/87.",
    ]:
        redacted = redact(spoken)
        assert "<DATE_OF_BIRTH>" in redacted, spoken
        assert not any(word in redacted for word in ("March", "May", "14", "fourteenth")), redacted


def test_a_month_or_year_on_its_own_is_left_alone():
    text = "I finished the physio in August, and gave up smoking in 1994."
    assert redact(text) == text


def test_product_facts_are_left_alone():
    text = (
        "Only accidental death is covered in the first 12 months. "
        "There is a 30-day cooling-off period with a full refund."
    )
    assert redact(text) == text


def test_names_on_the_call_are_replaced_even_when_the_model_misses_them():
    # Found in call-001: the language model doesn't spot "Jack" after "g'day"
    assert "Jack" not in redact("Yeah, g'day Jack, how are you?", ["Jack"])


def test_names_that_are_also_ordinary_words_only_match_when_capitalised():
    redacted = redact("You may want to think it over, May.", ["May Jones"])
    assert redacted.startswith("You may want")
    assert not redacted.endswith("May.")
