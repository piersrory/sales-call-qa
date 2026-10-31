from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"

# Full dates only (14 March 1985, 03/07/1990), so "12 months" and "30-day" are left alone
date_of_birth = PatternRecognizer(
    supported_entity="DATE_OF_BIRTH",
    patterns=[
        Pattern("day month year", rf"\b\d{{1,2}} (?:{MONTHS}) (?:19|20)\d{{2}}\b", 0.6),
        Pattern("numeric date", r"\b\d{1,2}[/.-]\d{1,2}[/.-](?:19|20)\d{2}\b", 0.6),
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


def redact(text: str) -> str:
    findings = analyzer.analyze(text=text, language="en", entities=ENTITIES)
    return anonymizer.anonymize(text=text, analyzer_results=findings).text
