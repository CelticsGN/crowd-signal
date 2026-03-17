"""LLM-based vocal crowd narration for completed simulations."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

_MODEL = "llama-3.1-8b-instant"
_TIMEOUT_SECONDS = 8.0
_DISCLAIMER = "This is probabilistic simulation, not financial advice."

VOCAL_AGENTS = [
    {
        "id": "retail_bull_047",
        "persona": "retail_bull",
        "personality": "excited, FOMO-driven, uses trading slang, easily influenced by news, overconfident",
    },
    {
        "id": "retail_bear_023",
        "persona": "retail_bear",
        "personality": "cautious, skeptical, always sees downside, references past crashes, risk-aware",
    },
    {
        "id": "whale_003",
        "persona": "whale",
        "personality": "calm, contrarian, thinks long term, fades retail euphoria, cryptic and brief",
    },
    {
        "id": "algo_011",
        "persona": "algo",
        "personality": "robotic, data-driven, no emotion, reports crowd statistics precisely, speaks in percentages and signals",
    },
    {
        "id": "narrator",
        "persona": "narrator",
        "personality": "objective analyst summarizing what the crowd simulation revealed",
    },
]


def _get_client() -> OpenAI | None:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None
    return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1", timeout=_TIMEOUT_SECONDS)


def _fmt(value: Any) -> str:
    try:
        return f"{float(value):.3f}"
    except Exception:
        return "0.000"


def _stance_label(stance: float) -> str:
    if stance > 0.5:
        return "very bullish"
    if stance > 0.1:
        return "moderately bullish"
    if stance > -0.1:
        return "neutral"
    if stance > -0.5:
        return "moderately bearish"
    return "very bearish"


def _build_user_prompt(
    ticker: str,
    catalyst: str,
    persona: str,
    simulation_result: dict[str, Any],
    catalyst_analysis: dict[str, Any],
) -> str:
    persona_stances = simulation_result.get("persona_mean_stance", {}) or {}
    total = int(simulation_result.get("agent_count", 0) or 0)
    up_count = int(simulation_result.get("up_count", 0) or 0)
    down_count = int(simulation_result.get("down_count", 0) or 0)
    probability_up = simulation_result.get("probability_up")
    probability_down = simulation_result.get("probability_down")
    if probability_up is None:
        probability_up = (up_count / total) if total else 0.0
    if probability_down is None:
        probability_down = (down_count / total) if total else 0.0

    rules_fired = [
        str(entry.get("rule", ""))
        for entry in catalyst_analysis.get("reasoning", [])
        if str(entry.get("rule", ""))
    ]

    agent_stance = float(simulation_result.get("mean_stance", 0.0)) if persona == "narrator" else float(persona_stances.get(persona, 0.0))

    return (
        f"Ticker: {ticker}\n"
        f"Catalyst: {catalyst}\n"
        "Simulation result:\n"
        f"- Crowd aggregate stance: {_fmt(simulation_result.get('mean_stance', 0.0))}\n"
        f"- Probability up: {_fmt(probability_up)}\n"
        f"- Probability down: {_fmt(probability_down)}\n"
        f"- Your persona ({persona}) stance: {_fmt(persona_stances.get(persona, 0.0))}\n"
        f"- Whale stance: {_fmt(persona_stances.get('whale', 0.0))}\n"
        f"- Retail bull stance: {_fmt(persona_stances.get('retail_bull', 0.0))}\n"
        f"- Rules fired: {', '.join(rules_fired) if rules_fired else 'none'}\n"
        f"- Final bias: {_fmt(catalyst_analysis.get('final_bias', 0.0))}\n"
        f"Your current stance is {_fmt(agent_stance)} on a scale of -1.0 (fully bearish) to +1.0 (fully bullish).\n"
        f"This means you are currently feeling: {_stance_label(agent_stance)}.\n"
        "Your message MUST be consistent with this stance.\n"
        "Do not contradict your stance value.\n"
        "What do you say?"
    )


def _extract_message(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", "") if message is not None else ""
    return str(content or "").strip()


def _is_stance_consistent(message: str, stance: float) -> bool:
    text = message.lower()
    bullish_hits = len(re.findall(r"\b(bull|buy|upside|upward|long|breakout|rally)\b", text))
    bearish_hits = len(re.findall(r"\b(bear|sell|downside|downward|short|correction|pullback|risk)\b", text))

    if stance > 0.1:
        return bullish_hits >= bearish_hits
    if stance < -0.1:
        return bearish_hits >= bullish_hits
    return True


def _fallback_aligned_message(persona: str, ticker: str, stance: float, probability_up: float, probability_down: float) -> str:
    label = _stance_label(stance)
    if stance > 0.1:
        return (
            f"Stance is {stance:.3f} ({label}) on {ticker}, with probability up {probability_up:.3f} "
            f"versus down {probability_down:.3f}; I remain positioned for upside."
        )
    if stance < -0.1:
        return (
            f"Stance is {stance:.3f} ({label}) on {ticker}, with probability down {probability_down:.3f} "
            f"versus up {probability_up:.3f}; I remain positioned defensively for downside risk."
        )
    return (
        f"Stance is {stance:.3f} ({label}) on {ticker}; probabilities are balanced at up {probability_up:.3f} "
        f"and down {probability_down:.3f}, so I stay neutral."
    )


def generate_crowd_narrative(
    ticker: str,
    catalyst: str,
    simulation_result: dict,
    catalyst_analysis: dict,
) -> list[dict]:
    """Generate sequential short reactions from five vocal crowd agents."""
    client = _get_client()
    if client is None:
        return []

    narrative: list[dict[str, Any]] = []
    prior_reactions: list[str] = []
    persona_stances = simulation_result.get("persona_mean_stance", {}) or {}

    for tick, agent in enumerate(VOCAL_AGENTS):
        agent_id = str(agent["id"])
        persona = str(agent["persona"])
        personality = str(agent["personality"])

        base_system_prompt = (
            f"You are {agent_id}, a {persona} trader.\n"
            f"Personality: {personality}\n"
            "You are reacting to a crowd simulation result.\n"
            "Write ONE short message (max 2 sentences) as this trader would naturally say it.\n"
            "Be specific to the numbers. Sound human.\n"
            "No hashtags. No emojis. Plain trading language.\n"
            "You MUST reflect your actual stance in your message.\n"
            "If your stance is positive (bullish), speak bullishly.\n"
            "If your stance is negative (bearish), speak bearishly.\n"
            "Never contradict your numerical stance.\n"
            "Your numerical stance overrides any persona stereotype.\n"
            "Speak like a real trader on a trading desk.\n"
            "No casual phrases like 'buddies' or 'pals'.\n"
            "Professional but human. Terse. Direct."
        )

        if persona == "narrator":
            system_prompt = base_system_prompt
            user_prompt = (
                _build_user_prompt(ticker, catalyst, persona, simulation_result, catalyst_analysis)
                + "\n"
                + f"Previous agent reactions: {' | '.join(prior_reactions) if prior_reactions else 'none'}\n"
                + "Summarize what the crowd simulation revealed in 2-3 sentences. Be objective. "
                + "End with the disclaimer: This is probabilistic simulation, not financial advice."
            )
        else:
            system_prompt = base_system_prompt
            user_prompt = _build_user_prompt(ticker, catalyst, persona, simulation_result, catalyst_analysis)

        try:
            completion = client.chat.completions.create(
                model=_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=140,
            )
            message = _extract_message(completion)
            if not message:
                continue
            stance = float(simulation_result.get("mean_stance", 0.0)) if persona == "narrator" else float(persona_stances.get(persona, 0.0))
            if persona != "narrator" and not _is_stance_consistent(message, stance):
                corrected = client.chat.completions.create(
                    model=_MODEL,
                    messages=[
                        {"role": "system", "content": base_system_prompt},
                        {
                            "role": "user",
                            "content": (
                                f"Your prior message contradicted stance {stance:.3f}. "
                                "Rewrite now so sentiment strictly matches stance. "
                                "If stance > 0, be bullish. If stance < 0, be bearish. Keep max 2 sentences."
                            ),
                        },
                    ],
                    temperature=0.2,
                    max_tokens=120,
                )
                corrected_message = _extract_message(corrected)
                if corrected_message:
                    message = corrected_message
            if persona != "narrator" and not _is_stance_consistent(message, stance):
                probability_up = float(simulation_result.get("probability_up", 0.0) or 0.0)
                probability_down = float(simulation_result.get("probability_down", 0.0) or 0.0)
                message = _fallback_aligned_message(persona, ticker, stance, probability_up, probability_down)
            if persona == "narrator" and not message.rstrip().endswith(_DISCLAIMER):
                message = f"{message.rstrip()} {_DISCLAIMER}"
        except Exception as exc:
            logger.warning("narrator_agent_failed agent_id=%s error=%s", agent_id, exc)
            continue

        stance = float(simulation_result.get("mean_stance", 0.0)) if persona == "narrator" else float(persona_stances.get(persona, 0.0))
        entry = {
            "agent_id": agent_id,
            "persona": persona,
            "message": message,
            "tick": tick,
            "stance": stance,
        }
        narrative.append(entry)
        if persona != "narrator":
            prior_reactions.append(f"{agent_id}: {message}")

    return narrative
