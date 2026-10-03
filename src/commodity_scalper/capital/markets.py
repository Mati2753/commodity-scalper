"""Dynamic commodity discovery; no EPIC is assumed."""

import json
from datetime import UTC, datetime
from pathlib import Path

from commodity_scalper.capital.client import CapitalClient
from commodity_scalper.capital.models import MarketCandidate, MarketDetails

SEARCH_TERMS = {
    "GOLD": ("Gold",),
    "WTI": ("WTI", "Crude Oil", "Oil"),
    "NATURAL_GAS": ("Natural Gas",),
}
POSITIVE = {
    "GOLD": ("gold",),
    "WTI": ("wti", "west texas", "crude oil", "us crude"),
    "NATURAL_GAS": ("natural gas",),
}
NEGATIVE = ("stock", "etf", "fund", "mini", "silver", "gasoline", "heating")


def candidate_score(label: str, candidate: MarketCandidate) -> int:
    text = f"{candidate.instrumentName} {candidate.epic}".lower()
    if any(word in text for word in NEGATIVE):
        return -100
    score = sum(20 for word in POSITIVE[label] if word in text)
    if (candidate.instrumentType or "").upper() in {"COMMODITIES", "COMMODITY"}:
        score += 10
    if (candidate.marketStatus or "").upper() in {"TRADEABLE", "EDITS_ONLY", "CLOSED"}:
        score += 2
    return score


def choose_candidate(label: str, candidates: list[MarketCandidate]) -> MarketCandidate:
    ranked = sorted(
        ((candidate_score(label, c), c) for c in candidates), key=lambda x: (-x[0], x[1].epic)
    )
    viable = [item for item in ranked if item[0] > 0]
    if not viable:
        raise ValueError(f"No credible {label} candidate found")
    if len(viable) > 1 and viable[0][0] == viable[1][0]:
        names = ", ".join(item[1].epic for item in viable if item[0] == viable[0][0])
        raise ValueError(f"Ambiguous {label} candidates: {names}")
    return viable[0][1]


async def discover(
    client: CapitalClient,
) -> tuple[dict[str, MarketDetails], dict[str, list[MarketCandidate]]]:
    selected, all_candidates = {}, {}
    for label, terms in SEARCH_TERMS.items():
        unique: dict[str, MarketCandidate] = {}
        for term in terms:
            result = await client.get("/api/v1/markets", params={"searchTerm": term})
            for raw in result.get("markets", []):
                candidate = MarketCandidate.model_validate(raw)
                unique[candidate.epic] = candidate
        candidates = list(unique.values())
        all_candidates[label] = candidates
        choice = choose_candidate(label, candidates)
        selected[label] = MarketDetails.model_validate(
            await client.get(f"/api/v1/markets/{choice.epic}")
        )
    return selected, all_candidates


def save_instruments(path: Path, markets: dict[str, MarketDetails]) -> None:
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "instruments": {
            label: details.model_dump(mode="json") for label, details in markets.items()
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_instruments(path: Path) -> dict[str, MarketDetails]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        label: MarketDetails.model_validate(value)
        for label, value in raw.get("instruments", {}).items()
    }
