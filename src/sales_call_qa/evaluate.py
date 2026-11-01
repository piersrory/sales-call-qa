"""Score saved assessments against the answer key and print the README tables.

A breach is a "fail". Recall asks how many planted breaches were caught; precision asks
how many of the breaches flagged were real. A missed breach is the expensive mistake, so
recall matters most; too many false alarms and reviewers stop trusting the flags.

    uv run evaluate                  # every model saved for prompt v1, plus the re-check set-up
    uv run evaluate --version v2     # the same for prompt v2
"""

import argparse
import csv
import statistics
from dataclasses import dataclass
from pathlib import Path

from sales_call_qa.assess import ASSESSMENTS_DIR
from sales_call_qa.generate_calls import REPO_ROOT
from sales_call_qa.rubric import RUBRIC
from sales_call_qa.schemas import AssessmentRecord, Verdict

# Dollars per million tokens (input, output), from the guide's section 13.2, October 2026.
# Check current prices before quoting costs.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}
CHEAP, STRONG = "claude-haiku-5-5", "claude-sonnet-5-5"


def load_labels() -> dict[tuple[str, str], Verdict]:
    with open(REPO_ROOT / "data" / "labels.csv") as f:
        return {(r["call_id"], r["criterion"]): Verdict(r["expected"]) for r in csv.DictReader(f)}


def load_run(model: str, version: str) -> dict[str, AssessmentRecord]:
    run_dir = ASSESSMENTS_DIR / model / version
    return {
        p.stem: AssessmentRecord.model_validate_json(p.read_text())
        for p in sorted(run_dir.glob("*.json"))
    }


def cost(record: AssessmentRecord, model: str) -> float:
    input_price, output_price = PRICES[model]
    return (record.input_tokens * input_price + record.output_tokens * output_price) / 1_000_000


@dataclass
class Run:
    """One set-up's verdicts, one record per call, plus what each call cost and took."""

    name: str
    records: dict[str, AssessmentRecord]
    costs: dict[str, float]
    seconds: dict[str, float]


def single_model_run(model: str, version: str) -> Run:
    records = load_run(model, version)
    return Run(
        name=f"{model}, {version}",
        records=records,
        costs={c: cost(r, model) for c, r in records.items()},
        seconds={c: r.seconds for c, r in records.items()},
    )


def recheck_run(cheap: Run, strong: Run, version: str) -> Run:
    """The cheap model checks every call; only the calls it flags go to the strong model,
    whose verdicts then replace the cheap ones. Clean calls never reach the strong model,
    so a breach the cheap model misses is never re-checked: recall shows if that hurts."""
    records, costs, seconds = {}, {}, {}
    for call_id, record in cheap.records.items():
        flagged = any(v.verdict == Verdict.FAIL for v in record.verdicts)
        if flagged and call_id in strong.records:
            records[call_id] = strong.records[call_id]
            costs[call_id] = cheap.costs[call_id] + strong.costs[call_id]
            seconds[call_id] = cheap.seconds[call_id] + strong.seconds[call_id]
        else:
            records[call_id] = record
            costs[call_id] = cheap.costs[call_id]
            seconds[call_id] = cheap.seconds[call_id]
    return Run(f"Haiku → Sonnet re-check, {version}", records, costs, seconds)


@dataclass
class Score:
    caught: int = 0  # planted breaches flagged as fail (true positives)
    missed: int = 0  # planted breaches not flagged (false negatives)
    false_alarms: int = 0  # fails flagged where no breach was planted (false positives)

    @property
    def recall(self) -> float | None:
        planted = self.caught + self.missed
        return self.caught / planted if planted else None

    @property
    def precision(self) -> float | None:
        flagged = self.caught + self.false_alarms
        return self.caught / flagged if flagged else None


def score(run: Run, labels: dict[tuple[str, str], Verdict], criterion: str | None = None) -> Score:
    """Breach-catching score for the whole run, or for one criterion."""
    s = Score()
    for call_id, record in run.records.items():
        for v in record.verdicts:
            if criterion and v.criterion != criterion:
                continue
            planted = labels[(call_id, v.criterion)] == Verdict.FAIL
            flagged = v.verdict == Verdict.FAIL
            if planted and flagged:
                s.caught += 1
            elif planted:
                s.missed += 1
            elif flagged:
                s.false_alarms += 1
    return s


def na_accuracy(run: Run, labels: dict[tuple[str, str], Verdict]) -> float:
    """Of the items that should be n/a, the share marked n/a."""
    expected_na = [
        v.verdict == Verdict.NOT_APPLICABLE
        for call_id, record in run.records.items()
        for v in record.verdicts
        if labels[(call_id, v.criterion)] == Verdict.NOT_APPLICABLE
    ]
    return sum(expected_na) / len(expected_na)


def quotes_found(run: Run) -> float:
    """Share of quotes that passed the evidence check. Market n/a rows have none to check."""
    checked = [
        v.evidence_verified
        for record in run.records.values()
        for v in record.verdicts
        if v.evidence_verified is not None
    ]
    return sum(checked) / len(checked)


def pct(value: float | None) -> str:
    return "–" if value is None else f"{value:.0%}"


def disagreements(run: Run, labels: dict[tuple[str, str], Verdict]) -> list[str]:
    """Every verdict that differs from the answer key: the ones to read before changing the prompt."""
    lines = []
    for call_id, record in run.records.items():
        for v in record.verdicts:
            expected = labels[(call_id, v.criterion)]
            if v.verdict != expected:
                lines.append(
                    f"| {call_id} | {v.criterion} | {expected} | {v.verdict} | {v.timestamp} | {v.reason} |"
                )
    return lines


def report(runs: list[Run], labels: dict[tuple[str, str], Verdict]) -> str:
    out = [
        "| Run | Calls | Recall | Precision | n/a accuracy | Quotes found | Cost per call | Seconds per call |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for run in runs:
        s = score(run, labels)
        out.append(
            f"| {run.name} | {len(run.records)} | {pct(s.recall)} ({s.caught}/{s.caught + s.missed}) "
            f"| {pct(s.precision)} ({s.caught}/{s.caught + s.false_alarms}) | {pct(na_accuracy(run, labels))} "
            f"| {pct(quotes_found(run))} | ${statistics.mean(run.costs.values()):.4f} "
            f"| {statistics.median(run.seconds.values()):.1f} |"
        )

    out += ["", "| Rubric item | " + " | ".join(f"Recall ({r.name}) | Precision ({r.name})" for r in runs) + " |"]
    out.append("|---|" + "---|---|" * len(runs))
    for criterion in RUBRIC:
        cells = []
        for run in runs:
            s = score(run, labels, criterion.id)
            cells += [f"{pct(s.recall)} ({s.caught}/{s.caught + s.missed})",
                      f"{pct(s.precision)} ({s.caught}/{s.caught + s.false_alarms})"]
        out.append(f"| {criterion.id} | " + " | ".join(cells) + " |")

    for run in runs:
        lines = disagreements(run, labels)
        out += ["", f"Disagreements with the answer key, {run.name}: {len(lines)}"]
        if lines:
            out += ["", "| Call | Criterion | Expected | Got | At | Reason |", "|---|---|---|---|---|---|", *lines]
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score saved assessments against data/labels.csv.")
    parser.add_argument("--version", default="v1", help="prompt version to score (default v1)")
    args = parser.parse_args()

    labels = load_labels()
    runs = {
        model: single_model_run(model, args.version)
        for model in PRICES
        if (ASSESSMENTS_DIR / model / args.version).is_dir()
    }
    if not runs:
        raise SystemExit(f"No saved assessments for prompt {args.version} in {ASSESSMENTS_DIR}")
    ordered = list(runs.values())
    if CHEAP in runs and STRONG in runs:
        ordered.append(recheck_run(runs[CHEAP], runs[STRONG], args.version))
    print(report(ordered, labels))


if __name__ == "__main__":
    main()
