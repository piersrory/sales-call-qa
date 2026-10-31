"""Markets and the fictional product sold in each one.

Modelled on direct-to-consumer life insurance in four markets. The brand and facts are
made up: change them here and the generator (and later the assessor) picks them up.
"""

from dataclasses import dataclass
from enum import StrEnum


class Market(StrEnum):
    AU = "AU"
    UK = "UK"
    CA = "CA"
    NZ = "NZ"


TIMEZONES = {
    Market.AU: "Australia/Sydney",
    Market.UK: "Europe/London",
    Market.CA: "America/Toronto",
    Market.NZ: "Pacific/Auckland",
}


@dataclass(frozen=True)
class Product:
    name: str
    currency: str
    monthly_premium_range: tuple[int, int]
    facts: tuple[str, ...]


PRODUCTS = {
    Market.AU: Product(
        name="Acme Life Cover",
        currency="AUD",
        monthly_premium_range=(25, 140),
        facts=(
            "Cover amounts range from $50,000 to $1,000,000.",
            "There's no medical exam: acceptance depends on a few health questions.",
            "Only accidental death is covered in the first 12 months.",
            "Premiums are stepped, so they go up each year as the customer gets older.",
            "There is a 30-day cooling-off period with a full refund.",
        ),
    ),
    Market.UK: Product(
        name="Acme Life Cover",
        currency="GBP",
        monthly_premium_range=(10, 70),
        facts=(
            "Cover amounts range from £25,000 to £500,000.",
            "There's no medical exam: acceptance depends on a few health questions.",
            "Only accidental death is covered in the first 12 months.",
            "Premiums are fixed for the whole length of the policy.",
            "There is a 30-day cooling-off period with a full refund.",
        ),
    ),
    Market.CA: Product(
        name="Acme Term Life",
        currency="CAD",
        monthly_premium_range=(20, 110),
        facts=(
            "Coverage ranges from $50,000 to $750,000.",
            "There's no medical exam: acceptance depends on a few health questions.",
            "Terms are 10 or 20 years, and premiums are fixed for the term.",
            "The policy has no cash value.",
            "There is a 30-day free-look period with a full refund.",
        ),
    ),
    Market.NZ: Product(
        name="Acme Life Cover",
        currency="NZD",
        monthly_premium_range=(25, 130),
        facts=(
            "Cover amounts range from $50,000 to $1,000,000.",
            "Pre-existing medical conditions are not covered for the first 2 years.",
            "Premiums are stepped, so they go up each year as the customer gets older.",
            "A terminal illness benefit pays out early if the customer has less than 12 months to live.",
            "There is a 30-day free-look period with a full refund.",
        ),
    ),
}
