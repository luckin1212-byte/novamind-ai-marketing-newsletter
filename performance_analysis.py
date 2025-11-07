"""Summarize live campaign performance using actual send logs."""

import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from openai import OpenAI

CAMPAIGN_LOG = Path("campaign_log.json")
PERFORMANCE_LOG = Path("performance_log.json")


def _load_campaign_entries() -> List[Dict]:
    if not CAMPAIGN_LOG.exists():
        raise FileNotFoundError(
            "campaign_log.json not found. Run a send via crm_newsletter before analyzing."
        )
    with open(CAMPAIGN_LOG, "r") as f:
        entries = json.load(f)
        if isinstance(entries, dict):
            entries = [entries]
    if not entries:
        raise ValueError("campaign_log.json is empty. Send at least one newsletter first.")
    return entries


def _aggregate_performance(entries: List[Dict]) -> Dict[str, Dict]:
    """Return basic KPIs grouped by persona using actual send logs."""
    persona_stats: Dict[str, Dict] = defaultdict(
        lambda: {
            "send_count": 0,
            "unique_contacts": set(),
            "latest_blog": None,
            "last_sent_at": None,
        }
    )

    for entry in entries:
        persona = entry.get("persona", "Unknown")
        stats = persona_stats[persona]
        stats["send_count"] += 1
        stats["unique_contacts"].add(entry.get("email"))
        stats["latest_blog"] = entry.get("blog_title")
        sent_at = entry.get("sent_at")
        if sent_at:
            try:
                sent_time = datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
                if not stats["last_sent_at"] or sent_time > stats["last_sent_at"]:
                    stats["last_sent_at"] = sent_time
            except ValueError:
                pass

    # convert sets/dates into serializable values
    for persona, stats in persona_stats.items():
        stats["unique_contacts"] = len([email for email in stats["unique_contacts"] if email])
        if stats["last_sent_at"]:
            stats["last_sent_at"] = stats["last_sent_at"].isoformat()
        else:
            stats["last_sent_at"] = "N/A"

    return dict(persona_stats)


def _persist_performance(performance: Dict[str, Dict]):
    with open(PERFORMANCE_LOG, "w") as f:
        json.dump(performance, f, indent=2)
    print(f"✅ Performance snapshot saved to {PERFORMANCE_LOG}")


def _build_summary(performance: Dict[str, Dict], openai_client: OpenAI) -> str:
    best_persona = max(
        performance.items(), key=lambda item: item[1]["send_count"], default=(None, None)
    )
    prompt = f"""
You are a marketing analyst. Here is live newsletter delivery data grouped by persona:
{json.dumps(performance, indent=2)}
- Send_count reflects actual Resend deliveries logged in campaign_log.json.
Please write 2 short sentences: highlight which persona had the most volume (currently {best_persona[0]}),
and suggest one action to improve overall engagement next cycle.
"""
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful marketing analyst."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=200,
    )
    return response.choices[0].message.content.strip()


def analyze_performance() -> Tuple[str, Dict]:
    load_dotenv()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    entries = _load_campaign_entries()
    performance_data = _aggregate_performance(entries)
    _persist_performance(performance_data)

    try:
        summary = _build_summary(performance_data, client)
    except Exception as exc:  # pylint: disable=broad-except
        summary = f"Error generating AI summary: {exc}"

    return summary, performance_data
