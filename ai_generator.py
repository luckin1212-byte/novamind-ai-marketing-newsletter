# ai_generator.py
import os
import json
from datetime import datetime
from textwrap import fill

from dotenv import load_dotenv
from openai import OpenAI

# === 1️⃣ Load environment variables ===
# Make sure your .env file contains: OPENAI_API_KEY=your_key_here
load_dotenv()

# === 2️⃣ Initialize OpenAI client ===
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

PERSONA_BRIEFS = [
    {
        "name": "Enterprise Marketing Director",
        "focus": "Cares about ROI, campaign consistency, and executive-ready insights.",
    },
    {
        "name": "Startup Founder",
        "focus": "Wants scrappy, growth-oriented messaging with clear differentiation.",
    },
    {
        "name": "Freelance Creative Strategist",
        "focus": "Looks for inspiring hooks, adaptable assets, and collaboration cues.",
    },
]


def build_topic_prompt(topic: str) -> str:
    """Create a structured prompt for the model."""
    persona_details = "\n".join(
        [f"- {p['name']}: {p['focus']}" for p in PERSONA_BRIEFS]
    )

    return f"""
You are an editorial strategist. Use the topic "{topic}" to produce planning assets
for a marketing team. Respond ONLY with valid JSON matching this schema:
{{
  "topic": "{topic}",
  "blog_outline": ["short, directive section headlines"],
  "blog_draft": {{
    "word_goal": "400-600 words",
    "content": "narrative blog draft meeting the outline"
  }},
  "newsletters": [
    {{
      "persona": "persona name",
      "angle": "unique spin for that persona",
      "subject_line": "email subject",
      "preview_text": "40-60 char preheader",
      "body": "snappy ~120 word body copy"
    }}
  ]
}}

Guidelines:
- Outline should include 4-6 sections and stay action oriented.
- Blog draft must cite the sections in logical order and stay between 400-600 words.
- Provide exactly three newsletter versions tailored to the personas below.
- Subject lines should stay under 60 characters and must differ.
- Newsletter body copy should reference the blog as the CTA.

Personas to target:
{persona_details}

Return concise JSON with no additional commentary.
"""


def clean_json_blob(raw_text: str) -> str:
    """Strip markdown fences so the JSON can be parsed."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned_lines = [
            line
            for line in cleaned.splitlines()
            if not line.strip().startswith("```")
        ]
        cleaned = "\n".join(cleaned_lines).strip()
    return cleaned


def request_content(prompt: str) -> str:
    """Send the structured request to the OpenAI API."""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        temperature=0.7,
        max_tokens=1200,
        messages=[
            {
                "role": "system",
                "content": "You are a senior marketing strategist who writes crisp JSON.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content.strip()


def generate_topic_package(topic: str) -> dict:
    """Generate the outline, draft, and newsletters for a topic."""
    prompt = build_topic_prompt(topic)
    try:
        raw_output = request_content(prompt)
    except Exception as exc:
        return {"topic": topic, "error": f"API call failed: {exc}"}
    cleaned = clean_json_blob(raw_output)

    try:
        structured = json.loads(cleaned)
    except json.JSONDecodeError:
        structured = {
            "topic": topic,
            "error": "Model did not return valid JSON.",
            "raw_output": raw_output,
        }

    structured.setdefault("topic", topic)
    structured.setdefault("raw_output", raw_output)
    return structured


def save_generated_content(topic: str, package: dict):
    """Persist the generated assets to generated_content.json."""
    filename = "generated_content.json"
    new_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "topic": topic,
        "content_package": package,
    }

    if os.path.exists(filename):
        with open(filename, "r") as f:
            try:
                existing_data = json.load(f)
                if isinstance(existing_data, dict):
                    existing_data = [existing_data]
            except json.JSONDecodeError:
                existing_data = []
    else:
        existing_data = []

    existing_data.append(new_entry)

    with open(filename, "w") as f:
        json.dump(existing_data, f, indent=2)

    print(f"\n✅ Content saved to {filename}")
    print(f"📂 Total saved entries: {len(existing_data)}")


def display_package(package: dict):
    """Pretty-print the generated assets for the console."""
    if package.get("error"):
        print(f"\n⚠️ {package['error']}")
        raw_output = package.get("raw_output")
        if raw_output:
            print("\nRaw model output:")
            print(raw_output)
        return

    print("\n=== Blog Outline ===")
    outline = package.get("blog_outline", [])
    if outline:
        for idx, item in enumerate(outline, start=1):
            print(f"{idx}. {item}")
    else:
        print("No outline returned.")

    print("\n=== Blog Draft (~400-600 words) ===")
    draft = package.get("blog_draft", {})
    draft_content = draft.get("content") if isinstance(draft, dict) else None
    if draft_content:
        print(fill(draft_content, width=100))
    else:
        print("No draft returned.")

    print("\n=== Persona Newsletters ===")
    newsletters = package.get("newsletters", [])
    if newsletters:
        for idx, letter in enumerate(newsletters, start=1):
            print(f"\n--- Newsletter #{idx}: {letter.get('persona', 'Persona TBD')} ---")
            print(f"Subject: {letter.get('subject_line', 'N/A')}")
            print(f"Preview: {letter.get('preview_text', 'N/A')}")
            body = letter.get("body", "No body provided.")
            print(fill(body, width=100))
    else:
        print("No newsletters returned.")


# === Main Script ===
if __name__ == "__main__":
    topic = input("Enter the topic you'd like to cover: ").strip()
    if not topic:
        raise ValueError("Topic is required to generate content.")

    package = generate_topic_package(topic)
    display_package(package)
    save_generated_content(topic, package)
