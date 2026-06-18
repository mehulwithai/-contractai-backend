"""
Day 3 — Analyzer / prompt test script
Tests the Claude AI analysis on any contract file.

Usage:
    python tests/test_analyzer.py --mock              # free, no API call, tests JSON parsing
    python tests/test_analyzer.py sample_nda.pdf      # real API call (uses credits)
    python tests/test_analyzer.py sample_vendor.pdf   # real API call (uses credits)
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.parser import extract_text, get_word_count, truncate_for_api


# ─── MOCK RESPONSE ───────────────────────────────────────────────
# This is what a perfect Claude response looks like.
# Used to test JSON parsing and UI rendering without spending credits.

MOCK_RESPONSE = {
    "summary": "This is a Non-Disclosure Agreement between Acme Corp and TechStartup Pvt Ltd. It commits TechStartup to keep Acme's business information confidential for 5 years, with extremely harsh penalties including a $500,000 fine per breach and a worldwide non-compete clause lasting 3 years after termination.",
    "contract_type": "NDA",
    "overall_risk": "high",
    "parties": ["Acme Corp", "TechStartup Pvt Ltd"],
    "key_dates": [
        {"label": "Contract start", "date": "January 1, 2025"},
        {"label": "Expiry / renewal", "date": "Auto-renews every year"},
        {"label": "Notice to cancel", "date": "90 days before renewal"}
    ],
    "flags": [
        {
            "id": 1,
            "title": "Massive liquidated damages",
            "clause": "pay liquidated damages of USD 500,000 per incident of unauthorized disclosure",
            "issue": "A $500,000 penalty per breach is wildly disproportionate for a small startup. One accidental disclosure — even a forwarded email — could be financially catastrophic.",
            "severity": "red",
            "suggestion": "Push back hard. Ask for a cap of USD 10,000–25,000 per incident, or remove liquidated damages entirely and rely on actual proven damages."
        },
        {
            "id": 2,
            "title": "3-year worldwide non-compete",
            "clause": "shall not directly or indirectly engage in any business that competes anywhere in the world",
            "issue": "A 3-year global non-compete is extremely broad. It could prevent you from working in your own industry for 3 years after this NDA ends — even if the relationship never went anywhere.",
            "severity": "red",
            "suggestion": "Non-competes in NDAs are unusual. Push to remove it entirely. If they insist, limit to 6 months, specific geography (their operating country), and define 'competing' narrowly."
        },
        {
            "id": 3,
            "title": "Auto-renewal with 90-day notice",
            "clause": "automatically renew unless written notice 90 days prior to end of term",
            "issue": "You must remember to cancel 90 days before the anniversary date or you're locked in for another year. Easy to miss, especially for a startup juggling many priorities.",
            "severity": "amber",
            "suggestion": "Ask to reduce the notice period to 30 days, or change auto-renewal to manual renewal requiring both parties to opt in."
        },
        {
            "id": 4,
            "title": "IP created from confidential info belongs to them",
            "clause": "work product created by Receiving Party using Confidential Information shall be sole property of Disclosing Party",
            "issue": "If you build anything — even internal tools — that touches their information, they own it. Dangerous if you're doing any development work alongside this NDA.",
            "severity": "red",
            "suggestion": "Limit IP assignment to work explicitly commissioned by Acme Corp. Exclude any independently developed tools or products."
        },
        {
            "id": 5,
            "title": "Delaware jurisdiction — expensive to enforce",
            "clause": "disputes shall be resolved exclusively in the courts of Delaware, USA",
            "issue": "As an Indian company, being forced to litigate in Delaware courts would cost you lakhs in legal fees before a case even starts — even if you're in the right.",
            "severity": "amber",
            "suggestion": "Request mutual jurisdiction — disputes filed in the defendant's home country. Or propose Singapore arbitration as a neutral, internationally recognised forum."
        },
        {
            "id": 6,
            "title": "Confidentiality survives termination indefinitely",
            "clause": "obligations of confidentiality shall survive termination of this Agreement indefinitely",
            "issue": "Standard NDAs have a post-termination confidentiality period of 2-5 years. Indefinite is unusual and could bind you forever.",
            "severity": "amber",
            "suggestion": "Ask for a 3-5 year post-termination confidentiality period instead of indefinite."
        }
    ],
    "positives": [
        "Clear definition of what counts as Confidential Information",
        "Standard exclusions for publicly available information are implied",
        "Mutual signing process is straightforward"
    ],
    "questions_to_ask": [
        "Can the $500,000 liquidated damages clause be removed or significantly reduced?",
        "Why is a non-compete clause included in what should be a simple NDA?",
        "Can we change the governing jurisdiction to India or Singapore?",
        "What specific information will actually be shared under this NDA?",
        "Can the auto-renewal notice period be reduced from 90 days to 30 days?"
    ],
    "_meta": {
        "input_tokens": 5432,
        "output_tokens": 812,
        "model": "MOCK"
    }
}


def print_review(result: dict, filename: str):
    """Pretty-print a contract review result in the terminal."""

    risk_colors = {"high": "HIGH RISK", "medium": "MEDIUM RISK", "low": "LOW RISK"}
    sev_labels = {"red": "[RED]  ", "amber": "[AMBER]", "green": "[GREEN]"}

    print(f"\n{'='*60}")
    print(f"CONTRACT REVIEW — {filename}")
    print('='*60)
    print(f"Type    : {result.get('contract_type', 'Unknown')}")
    print(f"Risk    : {risk_colors.get(result.get('overall_risk', ''), 'UNKNOWN')}")
    print(f"Parties : {' vs '.join(result.get('parties', []))}")

    print(f"\n📋 SUMMARY")
    print(f"   {result.get('summary', '')}")

    print(f"\n📅 KEY DATES")
    for d in result.get('key_dates', []):
        print(f"   {d['label']:<25} {d['date'] or 'Not specified'}")

    flags = result.get('flags', [])
    red   = [f for f in flags if f['severity'] == 'red']
    amber = [f for f in flags if f['severity'] == 'amber']
    green = [f for f in flags if f['severity'] == 'green']

    print(f"\n🚩 RISK FLAGS ({len(flags)} total — {len(red)} red, {len(amber)} amber, {len(green)} green)")
    print('-'*60)

    for flag in flags:
        label = sev_labels.get(flag['severity'], '[?]    ')
        print(f"\n{label} {flag['title'].upper()}")
        print(f"   Clause    : \"{flag['clause'][:100]}...\"" if len(flag['clause']) > 100 else f"   Clause    : \"{flag['clause']}\"")
        print(f"   Issue     : {flag['issue']}")
        print(f"   Suggest   : {flag['suggestion']}")

    print(f"\n✅ POSITIVES")
    for p in result.get('positives', []):
        print(f"   • {p}")

    print(f"\n❓ QUESTIONS TO ASK BEFORE SIGNING")
    for i, q in enumerate(result.get('questions_to_ask', []), 1):
        print(f"   {i}. {q}")

    meta = result.get('_meta', {})
    if meta.get('model') != 'MOCK':
        cost = (meta.get('input_tokens', 0) / 1_000_000 * 3) + \
               (meta.get('output_tokens', 0) / 1_000_000 * 15)
        print(f"\n💰 API USAGE")
        print(f"   Model         : {meta.get('model', 'unknown')}")
        print(f"   Input tokens  : {meta.get('input_tokens', 0):,}")
        print(f"   Output tokens : {meta.get('output_tokens', 0):,}")
        print(f"   Cost this call: ${cost:.5f}")
    else:
        print(f"\n   [MOCK MODE — no API call made]")

    print('='*60)


def validate_result(result: dict) -> list:
    """Check the AI response has all required fields."""
    errors = []
    required = ['summary', 'contract_type', 'overall_risk', 'parties',
                'key_dates', 'flags', 'positives', 'questions_to_ask']
    for field in required:
        if field not in result:
            errors.append(f"Missing field: {field}")

    if 'flags' in result:
        for i, flag in enumerate(result['flags']):
            for f in ['id', 'title', 'clause', 'issue', 'severity', 'suggestion']:
                if f not in flag:
                    errors.append(f"Flag {i+1} missing field: {f}")
            if flag.get('severity') not in ['red', 'amber', 'green']:
                errors.append(f"Flag {i+1} invalid severity: {flag.get('severity')}")

    if result.get('overall_risk') not in ['low', 'medium', 'high']:
        errors.append(f"Invalid overall_risk: {result.get('overall_risk')}")

    return errors


def run_mock():
    """Test with mock data — no API call."""
    print("\n[MOCK MODE] Testing with pre-built response — no API credits used")
    print("[MOCK MODE] This validates JSON parsing and output formatting\n")

    # Validate structure
    errors = validate_result(MOCK_RESPONSE)
    if errors:
        print("VALIDATION ERRORS:")
        for e in errors:
            print(f"  - {e}")
        return False

    print("✓ JSON structure valid")
    print("✓ All required fields present")
    print("✓ All flag severities valid")
    print(f"✓ {len(MOCK_RESPONSE['flags'])} flags found")

    print_review(MOCK_RESPONSE, "sample_nda.pdf (mock)")
    return True


def run_real(filepath: str):
    """Run a real Claude API call — costs credits."""
    from app.services.analyzer import analyze_contract
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.anthropic_api_key or settings.anthropic_api_key == "your_anthropic_api_key_here":
        print("\nERROR: ANTHROPIC_API_KEY not set in your .env file")
        print("Set it first, then run again.")
        return False

    filename = os.path.basename(filepath)
    print(f"\n[REAL MODE] Sending {filename} to Claude API...")
    print("[REAL MODE] This will use API credits (~$0.03)\n")

    # Extract text
    try:
        with open(filepath, 'rb') as f:
            file_bytes = f.read()
        text = extract_text(file_bytes, filename)
        truncated = truncate_for_api(text)
    except Exception as e:
        print(f"Parse error: {e}")
        return False

    print(f"✓ Text extracted ({get_word_count(text):,} words)")
    print("  Sending to Claude... (this takes 5-15 seconds)")

    # Call Claude
    try:
        result = analyze_contract(truncated)
    except Exception as e:
        print(f"\nAPI ERROR: {e}")
        print("\nCommon fixes:")
        print("  - Check ANTHROPIC_API_KEY in .env")
        print("  - Check you have API credits at console.anthropic.com")
        return False

    # Validate
    errors = validate_result(result)
    if errors:
        print("VALIDATION ERRORS in Claude response:")
        for e in errors:
            print(f"  - {e}")
        print("\nRaw response:")
        print(json.dumps(result, indent=2))
        return False

    print(f"✓ Claude responded successfully")
    print(f"✓ {len(result.get('flags', []))} risk flags found")

    print_review(result, filename)

    # Save raw output for inspection
    out_path = f"tests/output_{filename.replace('.pdf','').replace('.docx','')}.json"
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\n✓ Full JSON saved to: {out_path}")
    return True


def main():
    args = sys.argv[1:]

    if not args or args[0] == '--mock':
        success = run_mock()
    else:
        filepath = args[0]
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            print("Usage: python tests/test_analyzer.py sample_nda.pdf")
            sys.exit(1)
        success = run_real(filepath)

    print(f"\n{'Day 3 complete — prompt engine working!' if success else 'Fix errors above then re-run'}")


if __name__ == "__main__":
    main()
