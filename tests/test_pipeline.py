"""
Day 4 — Full pipeline test
Simulates the complete flow: file upload → parse → analyse → format response
No server needed, no API credits needed when MOCK_AI=true.

Usage:
    python tests/test_pipeline.py               # tests both sample contracts
    python tests/test_pipeline.py my_file.pdf   # tests your own file
"""

import sys
import os
import json
import uuid
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env
from dotenv import load_dotenv
load_dotenv()

from app.services.parser import extract_text, get_word_count, truncate_for_api
from app.services.analyzer import analyze_contract, get_flag_counts


def run_pipeline(filepath: str) -> dict:
    filename = os.path.basename(filepath)
    print(f"\n{'='*60}")
    print(f"PIPELINE TEST — {filename}")
    print('='*60)

    # ── Step 1: Read file ─────────────────────────────────────────
    print("\n[1/5] Reading file...")
    with open(filepath, 'rb') as f:
        file_bytes = f.read()
    print(f"      Size: {len(file_bytes):,} bytes")

    # ── Step 2: Parse text ────────────────────────────────────────
    print("[2/5] Extracting text...")
    try:
        contract_text = extract_text(file_bytes, filename)
    except ValueError as e:
        print(f"      FAILED: {e}")
        return None

    word_count = get_word_count(contract_text)
    truncated  = truncate_for_api(contract_text)
    print(f"      Words: {word_count:,}  |  Chars: {len(contract_text):,}")
    print(f"      Truncated for API: {'yes' if len(truncated) < len(contract_text) else 'no'}")

    # ── Step 3: AI analysis ───────────────────────────────────────
    mock = os.getenv("MOCK_AI", "false").lower() == "true"
    print(f"[3/5] Running AI analysis {'(MOCK MODE)' if mock else '(REAL API)'}...")
    try:
        result = analyze_contract(truncated)
    except Exception as e:
        print(f"      FAILED: {e}")
        return None

    flag_counts = get_flag_counts(result)
    print(f"      Risk level : {result.get('overall_risk', '?').upper()}")
    print(f"      Flags found: {flag_counts['total']} total  "
          f"({flag_counts['red']} red, {flag_counts['amber']} amber, {flag_counts['green']} green)")

    # ── Step 4: Build response (same shape as real API) ───────────
    print("[4/5] Building API response...")
    review_id = str(uuid.uuid4())
    response  = {
        "review_id"  : review_id,
        "filename"   : filename,
        "created_at" : datetime.now(timezone.utc).isoformat(),
        "word_count" : word_count,
        "result"     : result,
        "flag_counts": flag_counts,
    }
    print(f"      Review ID : {review_id}")

    # ── Step 5: Save output ───────────────────────────────────────
    print("[5/5] Saving output...")
    os.makedirs("tests/outputs", exist_ok=True)
    out_file = f"tests/outputs/{filename.rsplit('.', 1)[0]}_review.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(response, f, indent=2, ensure_ascii=False)
    print(f"      Saved to: {out_file}")

    # ── Print summary ─────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("REVIEW SUMMARY")
    print(f"{'─'*60}")
    print(f"Contract type : {result.get('contract_type', 'Unknown')}")
    print(f"Overall risk  : {result.get('overall_risk', '?').upper()}")
    print(f"Parties       : {' vs '.join(result.get('parties', []))}")
    print(f"\nSummary:")
    print(f"  {result.get('summary', '')}")

    print(f"\nKey dates:")
    for d in result.get('key_dates', []):
        print(f"  {d.get('label',''):<25} {d.get('date') or 'Not specified'}")

    print(f"\nRisk flags:")
    sev = {"red": "🔴", "amber": "🟡", "green": "🟢"}
    for flag in result.get('flags', []):
        icon = sev.get(flag.get('severity',''), '⚪')
        print(f"  {icon} {flag.get('title','').upper()}")
        print(f"     Issue: {flag.get('issue','')[:120]}")
        print(f"     Fix  : {flag.get('suggestion','')[:120]}")
        print()

    print(f"Questions to ask before signing:")
    for i, q in enumerate(result.get('questions_to_ask', []), 1):
        print(f"  {i}. {q}")

    print(f"\n{'='*60}")
    print(f"✓ PIPELINE COMPLETE — review_id: {review_id}")
    print(f"{'='*60}")

    return response


def main():
    mock = os.getenv("MOCK_AI", "false").lower() == "true"
    print(f"\nContractAI — Day 4 Pipeline Test")
    print(f"Mode: {'MOCK (no API credits used)' if mock else 'REAL (uses Claude API)'}")

    if len(sys.argv) > 1:
        # Single file passed as argument
        filepath = sys.argv[1]
        if not os.path.exists(filepath):
            print(f"\nFile not found: {filepath}")
            sys.exit(1)
        run_pipeline(filepath)
    else:
        # Run on both sample contracts
        samples = ["sample_nda.pdf", "sample_vendor.pdf"]
        results = []
        for s in samples:
            if os.path.exists(s):
                r = run_pipeline(s)
                results.append((s, r is not None))
            else:
                print(f"\nSkipping {s} — file not found in E:\\SaaS\\")
                print(f"  Make sure you downloaded the sample PDFs from Day 2")

        print(f"\n{'='*60}")
        passed = sum(1 for _, ok in results if ok)
        print(f"RESULTS: {passed}/{len(results)} pipelines completed successfully")
        if passed == len(results) and results:
            print("\nDay 4 complete!")
            print("Next step: Day 5 — Supabase auth + database integration")
            if mock:
                print("\nWhen your API credits arrive:")
                print("  1. Set MOCK_AI=false in your .env")
                print("  2. Run: python tests/test_pipeline.py sample_nda.pdf")
                print("  That sends a real contract to Claude and returns live analysis.")
        print('='*60)


if __name__ == "__main__":
    main()
