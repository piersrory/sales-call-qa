"""The compliance rubric every call is checked against.

Illustrative only, not legal advice. Each criterion says what a compliant agent does
(what the assessor checks) and what a breach looks like (what the generator plants).
"""

from dataclasses import dataclass

from sales_call_qa.markets import Market


@dataclass(frozen=True)
class Criterion:
    id: str
    requirement: str
    breach: str
    markets: tuple[Market, ...] = tuple(Market)
    sale_only: bool = False  # only applies when the customer buys
    vulnerable_only: bool = False  # only applies when the customer shows signs of vulnerability

    def applies(self, market: Market, sold: bool, vulnerable: bool) -> bool:
        return (
            market in self.markets
            and (sold or not self.sale_only)
            and (vulnerable or not self.vulnerable_only)
        )


RUBRIC = (
    Criterion(
        id="recording_disclosure",
        requirement="Within the first minute, the agent tells the customer the call is recorded.",
        breach="The agent starts the pitch without ever saying the call is recorded.",
    ),
    Criterion(
        id="identity_check",
        requirement=(
            "Before discussing the customer's details or quote, the agent confirms "
            "their full name and date of birth."
        ),
        breach="The agent talks about the customer's details and quote without confirming who they are.",
    ),
    Criterion(
        id="needs_assessment",
        requirement=(
            "Before recommending cover, the agent asks about the customer's circumstances "
            "and why they want cover."
        ),
        breach="The agent recommends a cover amount without asking about the customer's situation.",
    ),
    Criterion(
        id="accurate_product_info",
        requirement=(
            "Everything the agent says about the cover, price, waiting periods and "
            "exclusions matches the product facts."
        ),
        breach=(
            "The agent gets one product fact wrong, for example saying a pre-existing "
            "condition is covered straight away."
        ),
    ),
    Criterion(
        id="no_pressure_selling",
        requirement="The agent lets the customer decide in their own time, with no false urgency.",
        breach=(
            "The agent invents urgency, such as a price that is 'only available on this call', "
            "or brushes off the customer's wish to think it over."
        ),
    ),
    Criterion(
        id="explicit_consent",
        requirement=(
            "Before completing the sale, the agent summarises the cover and monthly premium "
            "and gets a clear yes."
        ),
        breach=(
            "The agent completes the sale after a vague answer like 'I guess so', without "
            "summarising the cover or premium."
        ),
        sale_only=True,
    ),
    Criterion(
        id="vulnerability_handling",
        requirement=(
            "When the customer shows signs of vulnerability, such as confusion, recent "
            "bereavement, illness or money worries, the agent slows down, checks they "
            "understand, and offers a call back or to involve someone they trust."
        ),
        breach=(
            "The customer shows clear signs of vulnerability, but the agent carries on at "
            "the same pace without checking they understand."
        ),
        vulnerable_only=True,
    ),
    Criterion(
        id="general_advice_warning",
        requirement=(
            "The agent says any advice is general and doesn't take the customer's personal "
            "circumstances into account."
        ),
        breach="The agent makes recommendations without ever saying the advice is general.",
        markets=(Market.AU,),
    ),
)
