import json
import os
import anthropic
from app.core.config import get_settings
from typing import List, Literal, Optional

# ─── NATIVE GEMINI SCHEMA DEFINITION ─────────────────────────────────────────
# We use a raw dictionary schema because the Gemini Python SDK can misinterpret
# Pydantic's default value wrappers, leading to 'Unknown field for Schema' errors.
GEMINI_CONTRACT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary": {
            "type": "STRING",
            "description": "2-3 sentence plain-English overview of what this contract is and what it commits the user to"
        },
        "contract_type": {
            "type": "STRING",
            "enum": ["NDA", "Vendor Agreement", "Employment", "SaaS/Software", "Service Agreement", "Lease", "Other"]
        },
        "overall_risk": {
            "type": "STRING",
            "enum": ["low", "medium", "high"]
        },
        "parties": {
            "type": "ARRAY",
            "items": {"type": "STRING"}
        },
        "key_dates": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "label": {"type": "STRING"},
                    "date": {"type": "STRING", "description": "The date value, or an empty string if null"}
                },
                "required": ["label", "date"]
            }
        },
        "flags": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "INTEGER"},
                    "title": {"type": "STRING"},
                    "clause": {"type": "STRING", "description": "The exact problematic clause text, max 150 chars"},
                    "issue": {"type": "STRING"},
                    "severity": {"type": "STRING", "enum": ["red", "amber", "green"]},
                    "suggestion": {"type": "STRING"}
                },
                "required": ["id", "title", "clause", "issue", "severity", "suggestion"]
            }
        },
        "positives": {
            "type": "ARRAY",
            "items": {"type": "STRING"}
        },
        "questions_to_ask": {
            "type": "ARRAY",
            "items": {"type": "STRING"}
        }
    },
    "required": ["summary", "contract_type", "overall_risk", "parties", "key_dates", "flags", "positives", "questions_to_ask"]
}

# ─── PROVIDER SWITCH ─────────────────────────────────────────────────────────
# Set AI_PROVIDER in your .env to one of: mock | gemini | claude
# - mock    → instant fake response, zero cost, zero API calls
# - gemini  → real AI, free tier (no billing attached), good for early testing
# - claude  → real AI, paid, used for production once credits/billing are set up

MOCK_RESULT = {
    "summary": "This is a Non-Disclosure Agreement between Acme Corp and TechStartup Pvt Ltd. It commits TechStartup to keep Acme's business information confidential for 5 years, with extremely harsh penalties including a $500,000 fine per breach and a worldwide non-compete clause lasting 3 years after termination.",
    "contract_type": "NDA",
    "overall_risk": "high",
    "parties": ["Acme Corp", "TechStartup Pvt Ltd"],
    "key_dates": [
        {"label": "Contract start",    "date": "January 1, 2025"},
        {"label": "Expiry / renewal",  "date": "Auto-renews every year"},
        {"label": "Notice to cancel",  "date": "90 days before renewal"}
    ],
    "flags": [
        {
            "id": 1,
            "title": "Massive liquidated damages",
            "clause": "pay liquidated damages of USD 500,000 per incident of unauthorized disclosure",
            "issue": "A $500,000 penalty per breach is wildly disproportionate for a small startup. One accidental disclosure could be financially catastrophic.",
            "severity": "red",
            "suggestion": "Push back hard. Ask for a cap of USD 10,000–25,000 per incident, or remove liquidated damages entirely."
        },
        {
            "id": 2,
            "title": "3-year worldwide non-compete",
            "clause": "shall not directly or indirectly engage in any business that competes anywhere in the world",
            "issue": "A 3-year global non-compete is extremely broad. It could prevent you from working in your own industry for 3 years after this NDA ends.",
            "severity": "red",
            "suggestion": "Push to remove it entirely. If they insist, limit to 6 months and specific geography."
        },
        {
            "id": 3,
            "title": "Auto-renewal with 90-day notice",
            "clause": "automatically renew unless written notice 90 days prior to end of term",
            "issue": "You must remember to cancel 90 days before the anniversary or you're locked in for another year. Easy to miss.",
            "severity": "amber",
            "suggestion": "Ask to reduce notice period to 30 days, or change to manual opt-in renewal."
        },
        {
            "id": 4,
            "title": "IP ownership grab",
            "clause": "work product created by Receiving Party using Confidential Information shall be sole property of Disclosing Party",
            "issue": "Anything you build that touches their information — they own it. Dangerous if you do any development alongside this NDA.",
            "severity": "red",
            "suggestion": "Limit IP assignment to work explicitly commissioned by them. Exclude independently developed tools."
        },
        {
            "id": 5,
            "title": "Foreign jurisdiction clause",
            "clause": "disputes shall be resolved exclusively in the courts of Delaware, USA",
            "issue": "As an Indian company, litigating in Delaware courts would cost you lakhs before a case even starts.",
            "severity": "amber",
            "suggestion": "Request mutual jurisdiction or propose Singapore arbitration as a neutral forum."
        }
    ],
    "positives": [
        "Clear definition of what counts as Confidential Information",
        "Standard mutual signing process"
    ],
    "questions_to_ask": [
        "Can the $500,000 liquidated damages clause be reduced significantly?",
        "Why is a non-compete clause included in what should be a simple NDA?",
        "Can we change the governing jurisdiction to India or Singapore?",
        "Can the auto-renewal notice period be reduced from 90 to 30 days?"
    ],
    "_meta": {
        "input_tokens": 0,
        "output_tokens": 0,
        "model": "MOCK"
    }
}

SYSTEM_PROMPT = """You are an expert contract review assistant helping small business owners and founders understand contracts without needing a lawyer.

Your job is to analyze contracts and return a structured JSON review. You must:
- Use plain English — no legal jargon
- Be direct about risks — don't sugarcoat serious issues
- Focus on clauses that could hurt the user financially or operationally
- Always cite the exact clause text (shortened) when flagging an issue

Return ONLY valid JSON — no preamble, no explanation, no markdown fences. The JSON must follow this exact shape:

{
  "summary": "2-3 sentence plain-English overview of what this contract is and what it commits the user to",
  "contract_type": "NDA | Vendor Agreement | Employment | SaaS/Software | Service Agreement | Lease | Other",
  "overall_risk": "low | medium | high",
  "parties": ["Party A name", "Party B name"],
  "key_dates": [
    {"label": "Contract start", "date": "value or null"},
    {"label": "Expiry / renewal", "date": "value or null"},
    {"label": "Notice period", "date": "value or null"}
  ],
  "flags": [
    {
      "id": 1,
      "title": "Short title for this issue (5 words max)",
      "clause": "The exact problematic clause text, max 150 chars",
      "issue": "Plain-English explanation of why this is risky",
      "severity": "red | amber | green",
      "suggestion": "What to ask for instead, or how to negotiate this clause"
    }
  ],
  "positives": ["List of clauses or terms that are actually fair or protective for the user"],
  "questions_to_ask": ["3-5 questions the user should ask the other party before signing"]
}

Severity guide:
- red: Could cause significant financial loss, legal liability, or unfair lock-in
- amber: Worth negotiating — not ideal but not a dealbreaker
- green: Minor note or standard clause worth being aware of

Return between 3 and 10 flags. Prioritize the most impactful issues."""


def _clean_json_response(raw: str) -> str:
    """Safely extracts JSON text from any conversational wrappers or markdown fences."""
    raw = raw.strip()

    # Find the bounds of the actual JSON object
    start_idx = raw.find('{')
    end_idx = raw.rfind('}')

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        return raw[start_idx:end_idx + 1]

    return raw


def _analyze_with_claude(contract_text: str) -> dict:
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"Please review this contract:\n\n{contract_text}"}
        ]
    )

    raw = _clean_json_response(message.content[0].text)
    result = json.loads(raw)

    result["_meta"] = {
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
        "model": message.model,
    }
    return result


def _analyze_with_gemini(contract_text: str) -> dict:
    import google.generativeai as genai
    settings = get_settings()
    genai.configure(api_key=settings.gemini_api_key)

    # Note: Gemini 3.5 Flash is a paid tier model. For the free tier,
    # use "gemini-2.5-flash", "gemini-2.0-flash", or "gemini-3-flash-preview"
    model = genai.GenerativeModel(
        model_name="gemini-3.1-flash-lite",
        system_instruction=SYSTEM_PROMPT,
    )

    response = model.generate_content(
        f"Please review this contract:\n\n{contract_text}",
        generation_config={
            "temperature": 0.2,
            "max_output_tokens": 4000,
            "response_mime_type": "application/json",
            "response_schema": GEMINI_CONTRACT_SCHEMA, # <-- Swapped Pydantic for raw dict schema
        },
    )

    # Clean and parse safely
    raw = _clean_json_response(response.text)
    result = json.loads(raw)

    usage = getattr(response, "usage_metadata", None)
    result["_meta"] = {
        "input_tokens": getattr(usage, "prompt_token_count", 0) if usage else 0,
        "output_tokens": getattr(usage, "candidates_token_count", 0) if usage else 0,
        "model": "gemini-2.0-flash",
    }
    return result


def analyze_contract(contract_text: str) -> dict:
    """
    Send contract text to the configured AI provider and get back a
    structured risk analysis. Returns a parsed dict ready to store in Supabase.
    """
    provider = "gemini"

    if provider == "mock":
        return MOCK_RESULT.copy()

    elif provider == "gemini":
        try:
            return _analyze_with_gemini(contract_text)
        except Exception as e:
            raise RuntimeError(f"Gemini analysis failed: {e}")

    elif provider == "claude":
        try:
            return _analyze_with_claude(contract_text)
        except Exception as e:
            raise RuntimeError(f"Claude analysis failed: {e}")

    else:
        raise ValueError(f"Unknown AI_PROVIDER: {provider}. Use mock, gemini, or claude.")


def get_flag_counts(result: dict) -> dict:
    flags = result.get("flags", [])
    return {
        "total": len(flags),
        "red": sum(1 for f in flags if f.get("severity") == "red"),
        "amber": sum(1 for f in flags if f.get("severity") == "amber"),
        "green": sum(1 for f in flags if f.get("severity") == "green"),
    }
