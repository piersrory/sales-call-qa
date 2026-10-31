import re

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"

# Transcripts record speech, so days and years come as words as well as digits:
# "the fourteenth of March, nineteen eighty-seven" as well as "14 March 1987"
UNITS = "one|two|three|four|five|six|seven|eight|nine"
TEENS = "ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen"
TENS = "twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety"
ORDINALS = (
    "first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|"
    "thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth|thirtieth"
)
DAY = rf"(?:\d{{1,2}}(?:st|nd|rd|th)?|(?:twenty|thirty)[ -](?:first|second|third|{ORDINALS})|{ORDINALS})"
YEAR = (
    r"(?:(?:19|20)\d{2}"
    rf"|(?:nineteen|twenty)[ -](?:(?:{TENS})(?:[ -](?:{UNITS}))?|{TEENS}|oh[ -](?:{UNITS}))"
    rf"|two thousand(?: and)?(?: (?:{TEENS}|{UNITS}))?)"
)

# Full dates only (14 March 1985, March 14th, 1985, 03/07/1990), so "12 months",
# "30-day" and a month or year on its own ("in August", "gave up in 1994") are left alone
date_of_birth = PatternRecognizer(
    supported_entity="DATE_OF_BIRTH",
    patterns=[
        Pattern("day month year", rf"\b(?:the )?{DAY} (?:of )?(?:{MONTHS}),? {YEAR}\b", 0.6),
        Pattern("month day year", rf"\b(?:{MONTHS}) (?:the )?{DAY},? {YEAR}\b", 0.6),
        Pattern("numeric date", r"\b\d{1,2}[/.-]\d{1,2}[/.-](?:(?:19|20)\d{2}|\d{2})\b", 0.6),
    ],
)

analyzer = AnalyzerEngine()
analyzer.registry.add_recognizer(date_of_birth)
anonymizer = AnonymizerEngine()

ENTITIES = [
    "PERSON",
    "DATE_OF_BIRTH",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "CREDIT_CARD",
    "IBAN_CODE",
    "UK_NHS",
]


def redact(text: str, names: list[str] = ()) -> str:
    """Replace personal details. `names` are people known to be on the call, such as the
    customer and agent, and are always caught, even where the language model misses them."""
    # Split full names so "Liam" and "O'Brien" are each caught on their own. Matching is
    # case-sensitive so a customer called May doesn't wipe out every "may".
    words = [word for name in names for word in name.split()]
    known_names = (
        [
            PatternRecognizer(
                supported_entity="PERSON",
                deny_list=words,
                global_regex_flags=re.MULTILINE,
            )
        ]
        if words
        else []
    )
    findings = analyzer.analyze(
        text=text, language="en", entities=ENTITIES, ad_hoc_recognizers=known_names
    )
    return anonymizer.anonymize(text=text, analyzer_results=findings).text
