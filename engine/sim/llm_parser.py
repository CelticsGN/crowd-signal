"""Catalyst intelligence parser with LLM extraction + graph-based bias synthesis."""

from __future__ import annotations

import os
import json
import re
from typing import Any, Literal, TypedDict

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def _build_extraction_prompt(target_ticker: str) -> str:
    ticker_instr = (
        f"The catalyst text may mention multiple companies. Only extract information relevant to {target_ticker}. "
        f"Return exactly one JSON object about {target_ticker} specifically — never multiple objects, never an array."
    ) if target_ticker else "Return exactly one JSON object — never multiple objects, never an array."

    return (
        "You are an information extraction assistant for intraday stock catalysts. "
        "Given catalyst text, return ONLY valid JSON with these keys:\n"
        "primary_entity: string\n"
        "event_type: one of [earnings, insider_sale, macro, legal, product, regulatory]\n"
        "magnitude: one of [strong, moderate, weak]\n"
        "direction: one of [positive, negative, neutral]\n"
        "related_entities: array of strings\n\n"
        f"{ticker_instr}\n\n"
        "examples:\n"
        "Example 1:\n"
        "Catalyst: Earnings beat driven by AI demand and data center growth\n"
        "Output: {\"primary_entity\":\"company\",\"event_type\":\"earnings\",\"magnitude\":\"strong\",\"direction\":\"positive\",\"related_entities\":[\"data_center_demand\",\"AI\"]}\n"
        "Example 2:\n"
        "Catalyst: CEO sold 2 million shares worth $800M\n"
        "Output: {\"primary_entity\":\"CEO\",\"event_type\":\"insider_sale\",\"magnitude\":\"strong\",\"direction\":\"negative\",\"related_entities\":[]}\n"
        "Example 3:\n"
        "Catalyst: Federal Reserve raises rates 50 basis points\n"
        "Output: {\"primary_entity\":\"Federal Reserve\",\"event_type\":\"macro\",\"magnitude\":\"strong\",\"direction\":\"negative\",\"related_entities\":[\"fed_related\",\"interest_rates\"]}\n"
        "Example 4:\n"
        "Catalyst: FDA approves new cancer drug\n"
        "Output: {\"primary_entity\":\"FDA\",\"event_type\":\"regulatory\",\"magnitude\":\"strong\",\"direction\":\"positive\",\"related_entities\":[\"drug_approval\",\"healthcare\"]}\n"
        "Example 5 (Multi-entity):\n"
        "Target Ticker: NVDA\n"
        "Catalyst: AMD and INTC plummeted after missing estimates, while NVDA held steady amidst strong data center demand.\n"
        "Output: {\"primary_entity\":\"NVDA\",\"event_type\":\"earnings\",\"magnitude\":\"moderate\",\"direction\":\"positive\",\"related_entities\":[\"data_center_demand\",\"semiconductor_sector\"]}\n\n"
        "Return JSON only. No markdown. No explanation."
    )

_MODEL = "llama-3.1-8b-instant"  # llama3-8b-8192 is decommissioned
_TIMEOUT = 8.0  # seconds — allows for Groq cold starts

# Keyword fallback lists (mirrors runner.py — kept here to avoid circular import)
_POSITIVE_KW = [
    "beat",
    "surge",
    "growth",
    "bullish",
    "upgrade",
    "record",
    "blew past estimates",
    "ai demand",
    "strong demand",
]
_NEGATIVE_KW = [
    "miss",
    "crash",
    "layoffs",
    "bearish",
    "downgrade",
    "loss",
    "sold",
    "insider sale",
    "raises interest rates",
    "rate hike",
]

EventType = Literal["earnings", "insider_sale", "macro", "legal", "product", "regulatory"]
Magnitude = Literal["extreme", "strong", "moderate", "weak"]
Direction = Literal["positive", "negative", "neutral"]


class CatalystExtraction(TypedDict):
    primary_entity: str
    event_type: EventType
    magnitude: Magnitude
    direction: Direction
    related_entities: list[str]


class GraphNode(TypedDict, total=False):
    id: str
    kind: str
    type: str
    color: str
    description: str


class GraphEdge(TypedDict, total=False):
    source: str
    target: str
    relation: str
    weight: float
    label: str


class ReasoningEntry(TypedDict):
    rule: str
    effect: str
    weight: float
    detail: str


class CatalystAnalysis(TypedDict):
    extraction: CatalystExtraction
    graph_nodes: list[GraphNode]
    graph_edges: list[GraphEdge]
    base_bias: float
    graph_adjustment: float
    market_adjustment: float
    final_bias: float
    market_scope: str
    reasoning: list[ReasoningEntry]


def _clamp(value: float) -> float:
    """Clamp *value* to [-1.0, 1.0]."""
    return max(-1.0, min(1.0, value))


def _normalize_event_type(raw: Any) -> EventType:
    text = str(raw or "").strip().lower().replace("-", "_")
    if text in {"earnings", "earning", "guidance"}:
        return "earnings"
    if text in {"insider_sale", "insider", "executive_sale", "ceo_sale", "cfo_sale"}:
        return "insider_sale"
    if text in {"macro", "macro_event", "fed", "economy"}:
        return "macro"
    if text in {"regulatory", "approval", "fda", "ftc", "ec"}:
        return "regulatory"
    if text in {"legal", "lawsuit", "sec"}:
        return "legal"
    if text in {"product", "launch", "release"}:
        return "product"
    return "macro"


def _normalize_magnitude(raw: Any) -> Magnitude:
    text = str(raw or "").strip().lower()
    if text in {"extreme", "very_strong", "very strong", "max"}:
        return "extreme"
    if text in {"strong", "high", "large", "major", "severe"}:
        return "strong"
    if text in {"moderate", "medium", "mid"}:
        return "moderate"
    return "weak"


def _normalize_direction(raw: Any) -> Direction:
    text = str(raw or "").strip().lower()
    if text in {"positive", "bullish", "up", "upside"}:
        return "positive"
    if text in {"negative", "bearish", "down", "downside"}:
        return "negative"
    return "neutral"


def _extract_json_objects(raw: str, ticker: str = "") -> dict[str, Any] | None:
    import json
    import difflib
    objects = []
    start_idx = 0
    while True:
        start = raw.find("{", start_idx)
        if start < 0:
            break
        brace_count = 0
        end = -1
        for i in range(start, len(raw)):
            if raw[i] == '{':
                brace_count += 1
            elif raw[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = i
                    break
        if end >= 0:
            try:
                parsed = json.loads(raw[start : end + 1])
                if isinstance(parsed, dict):
                    objects.append(parsed)
            except Exception:
                pass
            start_idx = end + 1
        else:
            break

    if not objects:
        return None

    if ticker and len(objects) > 1:
        t = ticker.lower()
        best_obj = objects[0]
        best_score = -1.0
        
        for obj in objects:
            e = str(obj.get("primary_entity", "")).lower()
            if t in e or (e and e in t):
                score = 1.0
            elif t[:2] == e[:2]:
                score = 0.8
            else:
                score = difflib.SequenceMatcher(None, t, e).ratio()
            
            if score > best_score:
                best_score = score
                best_obj = obj
                
        return best_obj
        
    return objects[0]


def _magnitude_from_text(text: str) -> Magnitude:
    if re.search(r"\b(75\s*(basis points|bps|bp)|100\s*(basis points|bps|bp))\b", text):
        return "extreme"
    if re.search(r"\b50\s*(basis points|bps|bp)\b", text):
        return "strong"
    if re.search(r"\b25\s*(basis points|bps|bp)\b", text):
        return "moderate"

    pct_matches = [float(m) for m in re.findall(r"(\d+(?:\.\d+)?)\s*%", text)]
    strongest_pct = max(pct_matches) if pct_matches else 0.0
    if re.search(r"\b\d+(?:\.\d+)?\s*(million|billion|m|bn|b)\b", text):
        if re.search(r"\b(sold|sale|insider)\b", text):
            return "strong"
    if strongest_pct >= 15 or re.search(r"\b(major|massive|huge|record|strong)\b", text):
        return "strong"
    if re.search(r"\b(badly|sharply|significantly|materially)\b", text):
        return "moderate"
    if strongest_pct >= 5 or re.search(r"\b(moderate|solid|notable)\b", text):
        return "moderate"
    if re.search(r"\b(blew past estimates|beat estimates|well above estimates)\b", text):
        return "strong"
    return "weak"


def _direction_from_text(text: str) -> Direction:
    if re.search(r"\b(raises interest rates|rate hike|hawkish)\b", text):
        return "negative"
    if re.search(r"\b(rate cut|dovish)\b", text):
        return "positive"
    if re.search(r"\b(blew past estimates|beat estimates|earnings beat|beat by|strong demand|ai demand|record revenue|upgrade)\b", text):
        return "positive"
    if re.search(r"\b(fda approves|regulatory approval|approval granted|approves)\b", text):
        return "positive"
    if re.search(r"\b(insider sale|ceo sold|cfo sold|director sold|sold\b|missed estimates|downgrade|lawsuit|probe)\b", text):
        return "negative"
    if re.search(r"\b(miss|missed|misses|below expectations|earnings miss)\b", text):
        return "negative"
    return "neutral"


def _magnitude_rank(value: Magnitude) -> int:
    return {"weak": 1, "moderate": 2, "strong": 3, "extreme": 4}[value]


def _primary_entity_from_text(catalyst: str) -> str:
    upper_tokens = re.findall(r"\b[A-Z]{2,5}\b", catalyst)
    ignored = {"AI", "CEO", "CFO", "FDA", "FED", "GDP", "CPI", "EPS"}
    for token in upper_tokens:
        if token not in ignored:
            return token
    person_or_company = re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b", catalyst)
    if person_or_company:
        candidate = person_or_company.group(0)
        if candidate not in {"Data", "Revenue", "Earnings"}:
            return candidate
    text = catalyst.lower()
    if re.search(r"\b(earnings|revenue|guidance|estimates)\b", text):
        return "company"
    return "market"


def _related_entities_from_text(text: str) -> list[str]:
    related: set[str] = set()
    if re.search(r"\b(data center|datacenter|ai demand|gpu demand|cloud demand)\b", text):
        related.add("data_center_demand")
    if re.search(r"\b(ai|artificial intelligence)\b", text):
        related.add("AI")
    if re.search(r"\b(fed|fomc|powell|interest rate|rates|cpi|inflation)\b", text):
        related.add("fed_related")
        related.add("interest_rates")
    if re.search(r"\b(semi|semiconductor|chip)\b", text):
        related.add("semiconductor_sector")
    if re.search(r"\b(competitor|peer|rival)\b", text):
        related.add("competitor_link")
    if re.search(r"\b(macro|economy|jobs report|nfp|gdp)\b", text):
        related.add("macro_link")
    return sorted(related)


def _keyword_fallback(catalyst: str) -> float:
    """Simple keyword-based bias scorer used when the LLM is unavailable."""
    text = catalyst.lower()
    pos = sum(len(re.findall(rf"\b{re.escape(kw)}\b", text)) for kw in _POSITIVE_KW)
    neg = sum(len(re.findall(rf"\b{re.escape(kw)}\b", text)) for kw in _NEGATIVE_KW)
    if pos == 0 and neg == 0:
        return 0.0
    raw = 0.30 * (pos - neg)
    pct_matches = [float(m) for m in re.findall(r"(\d+(?:\.\d+)?)\s*%", text)]
    multiplier = 1.0
    if pct_matches:
        multiplier += min(max(pct_matches), 50.0) / 100.0
    return _clamp(raw * multiplier)


def _keyword_extraction_fallback(catalyst: str) -> CatalystExtraction:
    text = catalyst.lower()

    if re.search(r"\b(earnings|guidance|eps|revenue|beat|miss)\b", text):
        event_type: EventType = "earnings"
    elif re.search(r"\b(fda|approval|approves|approved|clearance|authorized|regulator)\b", text):
        event_type = "regulatory"
    elif re.search(r"\b(insider|form 4|director sold|ceo sold|cfo sold|insider sale)\b", text):
        event_type = "insider_sale"
    elif re.search(r"\b(lawsuit|doj|sec|fine|settlement|legal|probe|investigation)\b", text):
        event_type = "legal"
    elif re.search(r"\b(launch|product|release|roadmap|chip unveil)\b", text):
        event_type = "product"
    else:
        event_type = "macro"

    direction = _direction_from_text(text)
    magnitude = _magnitude_from_text(text)

    # Regulatory approvals are treated as inherently strong catalysts.
    if event_type == "regulatory" and direction == "positive":
        magnitude = "strong"

    return {
        "primary_entity": _primary_entity_from_text(catalyst),
        "event_type": event_type,
        "magnitude": magnitude,
        "direction": direction,
        "related_entities": _related_entities_from_text(text),
    }


def _normalize_extraction_payload(payload: dict[str, Any], catalyst: str) -> CatalystExtraction:
    fallback = _keyword_extraction_fallback(catalyst)

    raw_related = payload.get("related_entities", [])
    related_entities = []
    if isinstance(raw_related, list):
        related_entities = sorted({str(item).strip().lower().replace(" ", "_") for item in raw_related if str(item).strip()})

    extraction: CatalystExtraction = {
        "primary_entity": str(payload.get("primary_entity") or fallback["primary_entity"] or _primary_entity_from_text(catalyst)).strip() or "market",
        "event_type": _normalize_event_type(payload.get("event_type")),
        "magnitude": _normalize_magnitude(payload.get("magnitude")),
        "direction": _normalize_direction(payload.get("direction")),
        "related_entities": related_entities,
    }

    # If LLM returns weak/neutral ambiguity, promote with deterministic text cues.
    if extraction["direction"] == "neutral" and fallback["direction"] != "neutral":
        extraction["direction"] = fallback["direction"]
    if _magnitude_rank(extraction["magnitude"]) < _magnitude_rank(fallback["magnitude"]):
        extraction["magnitude"] = fallback["magnitude"]

    # Prefer stronger, specific event types from text when LLM falls back to generic macro.
    if extraction["event_type"] == "macro" and fallback["event_type"] != "macro":
        extraction["event_type"] = fallback["event_type"]

    # Regulatory approvals should always be modeled as strong positive catalysts.
    if extraction["event_type"] == "regulatory" and extraction["direction"] == "positive":
        extraction["magnitude"] = "strong"

    if not extraction["related_entities"]:
        extraction["related_entities"] = fallback["related_entities"]
    else:
        extraction["related_entities"] = sorted(set(extraction["related_entities"]) | set(fallback["related_entities"]))

    return extraction


def _extract_entities_llm(catalyst: str, ticker: str = "") -> CatalystExtraction:
    client = OpenAI(
        api_key=os.getenv("GROQ_API_KEY"),
        base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        timeout=_TIMEOUT,
    )

    response = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": _build_extraction_prompt(ticker)},
            {"role": "user", "content": f"Target Ticker: {ticker}\nCatalyst: {catalyst}" if ticker else f"Catalyst: {catalyst}"},
        ],
        max_tokens=220,
        temperature=0.0,
    )

    raw = (response.choices[0].message.content or "").strip()
    payload = _extract_json_objects(raw, ticker)
    if payload is None:
        raise ValueError("LLM extraction did not return valid JSON.")

    return _normalize_extraction_payload(payload, catalyst)


def _build_graph_bias(extraction: CatalystExtraction) -> CatalystAnalysis:
    magnitude_weight = {"extreme": 0.45, "strong": 0.35, "moderate": 0.2, "weak": 0.1}
    direction_sign = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}

    base_bias = direction_sign[extraction["direction"]] * magnitude_weight[extraction["magnitude"]]
    graph_adjustment = 0.0
    market_scope = "ticker"
    reasoning: list[ReasoningEntry] = []

    primary_entity = extraction["primary_entity"] or "market"
    event_id = extraction["event_type"]
    outcome_id = (
        "BULLISH"
        if extraction["direction"] == "positive"
        else "BEARISH"
        if extraction["direction"] == "negative"
        else "NEUTRAL"
    )

    nodes: list[GraphNode] = [
        {
            "id": primary_entity,
            "kind": "entity",
            "type": "primary",
            "color": "amber",
            "description": "Primary catalyst entity",
        },
        {
            "id": event_id,
            "kind": "event",
            "type": "event",
            "color": "purple",
            "description": extraction["event_type"].replace("_", " ").title(),
        },
        {
            "id": outcome_id,
            "kind": "outcome",
            "type": "outcome",
            "color": "green" if outcome_id == "BULLISH" else "red" if outcome_id == "BEARISH" else "gray",
            "description": "Bias outcome node",
        },
    ]

    edges: list[GraphEdge] = [
        {
            "source": primary_entity,
            "target": event_id,
            "relation": "has_event",
            "weight": 0.15,
            "label": "has_event",
        },
        {
            "source": event_id,
            "target": outcome_id,
            "relation": "drives_outcome",
            "weight": 0.35,
            "label": "drives_outcome",
        },
    ]

    for related in extraction["related_entities"]:
        nodes.append(
            {
                "id": related,
                "kind": "related_entity",
                "type": "related",
                "color": "teal",
                "description": related.replace("_", " ").title(),
            }
        )
        edges.append(
            {
                "source": event_id,
                "target": related,
                "relation": "influences",
                "weight": 0.5,
                "label": "influences",
            }
        )
        edges.append(
            {
                "source": related,
                "target": outcome_id,
                "relation": "contributes_to",
                "weight": 0.3,
                "label": "contributes_to",
            }
        )

    earnings_specific_fired = False

    if (
        extraction["event_type"] == "earnings"
        and extraction["direction"] == "positive"
        and "data_center_demand" in extraction["related_entities"]
    ):
        boost = {"extreme": 0.28, "strong": 0.22, "moderate": 0.14, "weak": 0.08}[extraction["magnitude"]]
        graph_adjustment += boost
        earnings_specific_fired = True
        reasoning.append(
            {
                "rule": "earnings_beat_plus_data_center_demand",
                "effect": "bullish",
                "weight": boost,
                "detail": "Earnings beat linked with data center demand strengthens bullish crowd positioning.",
            }
        )

    if (
        extraction["event_type"] == "earnings"
        and extraction["direction"] == "positive"
        and extraction["magnitude"] in {"strong", "moderate"}
        and not earnings_specific_fired
    ):
        graph_adjustment += 0.35
        reasoning.append(
            {
                "rule": "earnings_beat_generic",
                "effect": "bullish",
                "weight": 0.35,
                "detail": "Positive earnings event detected - generic bullish crowd reaction expected",
            }
        )

    if (
        extraction["event_type"] == "earnings"
        and extraction["direction"] == "negative"
        and extraction["magnitude"] in {"strong", "moderate"}
    ):
        graph_adjustment += -0.35
        reasoning.append(
            {
                "rule": "earnings_miss_generic",
                "effect": "bearish",
                "weight": -0.35,
                "detail": "Earnings miss detected - generic bearish crowd reaction expected",
            }
        )

    if extraction["event_type"] == "insider_sale" and extraction["direction"] == "negative":
        graph_adjustment += -0.30
        reasoning.append(
            {
                "rule": "insider_sale_generic",
                "effect": "bearish",
                "weight": -0.30,
                "detail": "Insider selling detected - moderately bearish signal",
            }
        )

    if extraction["event_type"] == "regulatory" and extraction["direction"] == "positive":
        graph_adjustment += 0.40
        reasoning.append(
            {
                "rule": "regulatory_approval_generic",
                "effect": "bullish",
                "weight": 0.40,
                "detail": "Regulatory approval - strong bullish catalyst",
            }
        )

    if extraction["event_type"] == "macro" and "fed_related" in extraction["related_entities"]:
        market_scope = "all_tickers"
        macro_push = direction_sign[extraction["direction"]] * {
            "extreme": 0.3,
            "strong": 0.2,
            "moderate": 0.12,
            "weak": 0.06,
        }[extraction["magnitude"]]
        graph_adjustment += macro_push
        reasoning.append(
            {
                "rule": "macro_event_fed_related_broad_impact",
                "effect": "market_wide",
                "weight": macro_push,
                "detail": "Fed-related macro catalysts are applied as broad market pressure across tickers.",
            }
        )
    elif extraction["event_type"] == "macro" and extraction["direction"] == "negative":
        graph_adjustment += -0.25
        reasoning.append(
            {
                "rule": "macro_generic",
                "effect": "market_wide",
                "weight": -0.25,
                "detail": "Negative macro event - broad market bearish pressure",
            }
        )

    final_bias = _clamp(base_bias + graph_adjustment)
    if not reasoning:
        reasoning.append(
            {
                "rule": "base_directional_bias_only",
                "effect": "neutral",
                "weight": 0.0,
                "detail": "No specialized graph rule fired; using normalized direction/magnitude baseline.",
            }
        )

    return {
        "extraction": extraction,
        "graph_nodes": nodes,
        "graph_edges": edges,
        "base_bias": _clamp(base_bias),
        "graph_adjustment": graph_adjustment,
        "market_adjustment": 0.0,
        "final_bias": final_bias,
        "market_scope": market_scope,
        "reasoning": reasoning,
    }


def parse_catalyst_analysis_llm(catalyst: str, ticker: str = "") -> CatalystAnalysis:
    """Two-step catalyst analysis pipeline.

    Step 1: extract structured entities and event details.
    Step 2: build a tiny knowledge graph and compute deterministic bias adjustments.
    """
    try:
        extraction = _extract_entities_llm(catalyst, ticker)
    except Exception:
        extraction = _keyword_extraction_fallback(catalyst)

    analysis = _build_graph_bias(extraction)

    # Keep the old keyword scorer as a soft stabilizer when analysis is near-neutral.
    if abs(analysis["final_bias"]) < 0.05:
        fallback_bias = _keyword_fallback(catalyst)
        if abs(fallback_bias) >= 0.05:
            delta = _clamp(fallback_bias - analysis["final_bias"])
            analysis["market_adjustment"] = delta
            analysis["final_bias"] = _clamp(analysis["final_bias"] + delta)
            analysis["reasoning"].append(
                {
                    "rule": "keyword_fallback_stabilizer",
                    "effect": "bias_stabilization",
                    "weight": delta,
                    "detail": "Keyword fallback applied because extracted signal was near-neutral.",
                }
            )

    return analysis


def parse_catalyst_bias_llm(catalyst: str) -> float:
    """Backwards-compatible float parser returning final_bias from the new pipeline."""
    return parse_catalyst_analysis_llm(catalyst, "")["final_bias"]


class _ExtractionView:
    def __init__(self, payload: CatalystExtraction):
        self.primary_entity = payload["primary_entity"]
        self.event_type = payload["event_type"]
        self.magnitude = payload["magnitude"]
        self.direction = payload["direction"]
        self.related_entities = payload["related_entities"]


class _CatalystAnalysisView:
    def __init__(self, payload: CatalystAnalysis):
        self.extraction = _ExtractionView(payload["extraction"])
        self.graph_nodes = payload["graph_nodes"]
        self.graph_edges = payload["graph_edges"]
        reasoning = list(payload["reasoning"])
        if not any(entry.get("rule") == "market_context_adjustment" for entry in reasoning):
            reasoning.append(
                {
                    "rule": "market_context_adjustment",
                    "effect": "contextual_shift",
                    "weight": 0.0,
                    "detail": "No live market context supplied in standalone analyzer call.",
                }
            )
        self.reasoning = reasoning
        self.final_bias = payload["final_bias"]
        self.market_scope = payload["market_scope"]


def analyze_catalyst(catalyst: str) -> _CatalystAnalysisView:
    """Convenience wrapper used for direct debugging/verification scripts."""
    return _CatalystAnalysisView(parse_catalyst_analysis_llm(catalyst, ""))
