import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import requests
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL")
CONTACTS_FILE = Path("contacts.json")
GENERATED_CONTENT_FILE = Path("generated_content.json")

SAMPLE_CONTACTS = [
    {
        "email": "founder@example.com",
        "first_name": "Alex",
        "last_name": "Rivera",
        "persona": "Startup Founder",
    },
    {
        "email": "director@example.com",
        "first_name": "Morgan",
        "last_name": "Lee",
        "persona": "Enterprise Marketing Director",
    },
    {
        "email": "creative@example.com",
        "first_name": "Jamie",
        "last_name": "Chen",
        "persona": "Freelance Creative Strategist",
    },
]


def load_contacts() -> List[Dict]:
    """Load contacts from contacts.json or fall back to sample data."""
    if CONTACTS_FILE.exists():
        with open(CONTACTS_FILE, "r") as f:
            try:
                contacts = json.load(f)
                if isinstance(contacts, dict):
                    contacts = [contacts]
                return contacts
            except json.JSONDecodeError:
                print(
                    f"⚠️ contacts.json is empty or invalid JSON. "
                    "Falling back to sample contacts."
                )
    return SAMPLE_CONTACTS


def load_latest_campaign() -> Dict:
    """Fetch the latest generated content package (blog + newsletters)."""
    if not GENERATED_CONTENT_FILE.exists():
        raise FileNotFoundError(
            "generated_content.json not found. Run ai_generator.py first."
        )

    with open(GENERATED_CONTENT_FILE, "r") as f:
        data = json.load(f)
        if isinstance(data, dict):
            data = [data]
        if not data:
            raise ValueError("generated_content.json is empty.")

    latest_entry = data[-1]
    package = latest_entry.get("content_package", latest_entry)
    topic = package.get("topic") or latest_entry.get("topic", "Untitled Campaign")
    newsletters = package.get("newsletters", [])

    persona_map = {}
    for idx, letter in enumerate(newsletters, start=1):
        persona = letter.get("persona", f"Persona {idx}")
        normalized = persona.lower()
        letter = {**letter}
        letter.setdefault("newsletter_id", f"{normalized.replace(' ', '-')}-{idx}")
        persona_map[normalized] = letter

    return {"blog_title": topic, "newsletters": persona_map}


def save_local_campaign_log(entries: List[Dict]):
    """Append delivery entries to campaign_log.json."""
    log_path = Path("campaign_log.json")
    if log_path.exists():
        with open(log_path, "r") as f:
            try:
                existing = json.load(f)
                if isinstance(existing, dict):
                    existing = [existing]
            except json.JSONDecodeError:
                existing = []
    else:
        existing = []

    existing.extend(entries)
    with open(log_path, "w") as f:
        json.dump(existing, f, indent=2)


class ResendClient:
    API_URL = "https://api.resend.com/emails"

    def __init__(self, api_key: str, from_email: str):
        if not api_key:
            raise ValueError("RESEND_API_KEY is required.")
        if not from_email:
            raise ValueError("RESEND_FROM_EMAIL is required.")
        self.from_email = from_email
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )

    @staticmethod
    def _build_content(newsletter: Dict, blog_title: str) -> Dict[str, str]:
        subject = newsletter.get("subject_line") or f"Latest insights: {blog_title}"
        preview = newsletter.get("preview_text", "")
        body = newsletter.get("body", "")
        plain_text = f"{preview}\n\n{body}\n\nRead the full blog: {blog_title}"
        html_body = (
            f"<p>{preview}</p>"
            f"<p>{body}</p>"
            f"<p><strong>Read the full blog:</strong> {blog_title}</p>"
        )
        return {"subject": subject, "plain_text": plain_text, "html": html_body}

    @staticmethod
    def _slugify_tag(value: str, fallback: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_-]", "-", value or "")
        cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
        return cleaned or fallback

    def send(self, to_email: str, newsletter: Dict, blog_title: str, persona: str):
        content = self._build_content(newsletter, blog_title)
        persona_tag = self._slugify_tag(persona, "persona")
        campaign_tag = self._slugify_tag(blog_title, "campaign")
        payload = {
            "from": self.from_email,
            "to": [to_email],
            "subject": content["subject"],
            "text": content["plain_text"],
            "html": content["html"],
            "tags": [
                {"name": "persona", "value": persona_tag},
                {"name": "campaign", "value": campaign_tag},
            ],
        }
        response = self.session.post(self.API_URL, json=payload, timeout=30)
        if response.status_code not in (200, 202):
            raise RuntimeError(f"Resend error ({response.status_code}): {response.text}")
        return response.json()


def _available_personas(persona_map: Dict[str, Dict]) -> List[str]:
    return [letter.get("persona") for letter in persona_map.values()]


def _process_contact(
    contact: Dict, persona_map: Dict[str, Dict], blog_title: str, resend: ResendClient
) -> Dict:
    persona_label = contact.get("persona")
    if not persona_label:
        raise ValueError("Contact is missing a persona.")

    newsletter = persona_map.get(persona_label.lower())
    if not newsletter:
        available = ", ".join(_available_personas(persona_map))
        raise ValueError(
            f"No newsletter prepared for persona '{persona_label}'. "
            f"Available personas: {available}"
        )

    send_result = resend.send(contact["email"], newsletter, blog_title, persona_label)

    return {
        "email": contact["email"],
        "persona": persona_label,
        "newsletter_id": newsletter["newsletter_id"],
        "blog_title": blog_title,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "provider": "resend",
        "resend_id": send_result.get("id"),
    }


def get_campaign_overview() -> Dict[str, List[str]]:
    campaign = load_latest_campaign()
    return {
        "blog_title": campaign["blog_title"],
        "personas": _available_personas(campaign["newsletters"]),
    }


def send_newsletter_to_contact(contact: Dict) -> Dict:
    campaign = load_latest_campaign()
    persona_map = campaign["newsletters"]
    blog_title = campaign["blog_title"]
    resend = ResendClient(RESEND_API_KEY, RESEND_FROM_EMAIL)

    entry = _process_contact(contact, persona_map, blog_title, resend)
    save_local_campaign_log([entry])
    return entry


def orchestrate_campaign():
    contacts = load_contacts()
    campaign = load_latest_campaign()
    persona_map = campaign["newsletters"]
    blog_title = campaign["blog_title"]
    resend = ResendClient(RESEND_API_KEY, RESEND_FROM_EMAIL)

    log_entries = []
    for contact in contacts:
        try:
            entry = _process_contact(contact, persona_map, blog_title, resend)
        except ValueError as exc:
            print(
                f"⚠️ Skipping {contact['email']} ({contact.get('persona')}): {exc}"
            )
            continue

        log_entries.append(entry)
        print(
            f"✅ Resend delivery '{entry['newsletter_id']}' to "
            f"{contact['email']} ({contact.get('persona')})"
        )

    if log_entries:
        save_local_campaign_log(log_entries)
        print(
            f"\n📬 Completed campaign for '{blog_title}'. "
            f"Logged {len(log_entries)} deliveries via Resend."
        )
    else:
        print("No deliveries logged.")


if __name__ == "__main__":
    orchestrate_campaign()
