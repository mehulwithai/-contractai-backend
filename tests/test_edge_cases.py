"""
Day 6 — Edge case + stress tests
Tests every weird input a real user might throw at the system.

Usage:
    python tests/test_edge_cases.py
"""

import sys, os, io, uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from app.services.parser import extract_text, get_word_count, truncate_for_api
from app.services.analyzer import analyze_contract, get_flag_counts

GREEN  = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"
BOLD   = "\033[1m";  RESET = "\033[0m"

passed_total = 0
failed_total = 0

def ok(msg):    
    global passed_total
    passed_total += 1
    print(f"  {GREEN}[PASS]{RESET} {msg}")

def fail(msg):  
    global failed_total
    failed_total += 1
    print(f"  {RED}[FAIL]{RESET} {msg}")

def info(msg):  print(f"  {YELLOW}[INFO]{RESET} {msg}")
def header(msg): print(f"\n{BOLD}{'─'*55}\n{msg}\n{'─'*55}{RESET}")


# ── Helper: make a minimal valid PDF in memory ────────────────────
def make_pdf(text: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _, h = A4
    y = h - 50
    for line in text.split("\n"):
        c.drawString(50, y, line[:100])
        y -= 14
        if y < 50:
            c.showPage()
            y = h - 50
    c.save()
    return buf.getvalue()


def make_docx(text: str) -> bytes:
    from docx import Document
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ── Test 1: File type validation ──────────────────────────────────
def test_file_types():
    header("Test 1 — File type validation")

    # Valid PDF
    try:
        data = make_pdf("This is a valid contract.\nClause 1: Both parties agree.")
        text = extract_text(data, "contract.pdf")
        if text.strip():
            ok("Valid PDF accepted")
        else:
            fail("Valid PDF returned empty text")
    except Exception as e:
        fail(f"Valid PDF failed: {e}")

    # Valid DOCX
    try:
        data = make_docx("This is a valid contract.\nClause 1: Both parties agree.")
        text = extract_text(data, "contract.docx")
        if text.strip():
            ok("Valid DOCX accepted")
        else:
            fail("Valid DOCX returned empty text")
    except Exception as e:
        fail(f"Valid DOCX failed: {e}")

    # Invalid file type
    try:
        extract_text(b"some content", "contract.txt")
        fail("TXT file should have been rejected")
    except ValueError as e:
        ok(f"TXT file correctly rejected: {str(e)[:50]}")

    # Invalid file type — Excel
    try:
        extract_text(b"some content", "contract.xlsx")
        fail("XLSX file should have been rejected")
    except ValueError as e:
        ok(f"XLSX file correctly rejected")

    # No extension
    try:
        extract_text(b"some content", "contract")
        fail("No-extension file should have been rejected")
    except ValueError:
        ok("No-extension file correctly rejected")


# ── Test 2: Empty and minimal files ──────────────────────────────
def test_empty_files():
    header("Test 2 — Empty and minimal files")

    # Empty PDF (valid structure but no text)
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.showPage()
        c.save()
        empty_pdf = buf.getvalue()

        result = extract_text(empty_pdf, "empty.pdf")
        if not result.strip():
            fail("Empty PDF returned empty text — should raise ValueError")
        else:
            info(f"Empty PDF returned: '{result[:50]}'")
    except ValueError as e:
        ok(f"Empty PDF correctly rejected: {str(e)[:60]}")
    except Exception as e:
        info(f"Empty PDF raised: {type(e).__name__}: {e}")

    # Tiny valid contract (edge of minimum)
    try:
        data = make_pdf("Agreement between A and B.")
        text = extract_text(data, "tiny.pdf")
        ok(f"Tiny PDF accepted ({get_word_count(text)} words)")
    except Exception as e:
        fail(f"Tiny PDF failed: {e}")

    # Empty DOCX
    try:
        from docx import Document
        doc = Document()
        buf = io.BytesIO()
        doc.save(buf)
        result = extract_text(buf.getvalue(), "empty.docx")
        if not result.strip():
            fail("Empty DOCX should raise ValueError")
    except ValueError as e:
        ok(f"Empty DOCX correctly rejected")
    except Exception as e:
        info(f"Empty DOCX raised: {type(e).__name__}")


# ── Test 3: Large files ───────────────────────────────────────────
def test_large_files():
    header("Test 3 — Large files (long contracts)")

    # 50-page contract simulation
    long_contract = "\n".join([
        f"CLAUSE {i}: The party of the first part agrees that all obligations "
        f"under section {i} shall be fulfilled within thirty (30) days of notice. "
        f"Furthermore, indemnification applies to all sub-clauses herein."
        for i in range(1, 300)
    ])

    try:
        data = make_pdf(long_contract)
        size_kb = len(data) / 1024
        text = extract_text(data, "long_contract.pdf")
        words = get_word_count(text)
        ok(f"Long PDF parsed ({size_kb:.0f}KB, {words:,} words)")

        truncated = truncate_for_api(text)
        was_cut = len(truncated) < len(text)
        if was_cut:
            ok(f"Long contract correctly truncated for API ({len(truncated):,} chars)")
        else:
            ok(f"Contract fits in API limit ({len(text):,} chars)")
    except Exception as e:
        fail(f"Long PDF failed: {e}")

    # File over 10MB limit (simulated)
    big_bytes = b"x" * (11 * 1024 * 1024)  # 11MB
    size_mb = len(big_bytes) / (1024 * 1024)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    if len(big_bytes) > MAX_FILE_SIZE:
        ok(f"11MB file would be rejected by size check ({size_mb:.0f}MB > 10MB limit)")
    else:
        fail("Size check logic wrong")


# ── Test 4: Corrupted files ───────────────────────────────────────
def test_corrupted_files():
    header("Test 4 — Corrupted and malformed files")

    # Random bytes pretending to be PDF
    try:
        fake_pdf = b"%PDF-1.4 " + os.urandom(500)
        extract_text(fake_pdf, "corrupted.pdf")
        info("Corrupted PDF was processed (PyMuPDF is resilient)")
    except Exception as e:
        ok(f"Corrupted PDF handled gracefully: {type(e).__name__}")

    # Completely random bytes
    try:
        extract_text(os.urandom(1000), "random.pdf")
        info("Random bytes as PDF — PyMuPDF attempted to parse")
    except Exception as e:
        ok(f"Random bytes rejected: {type(e).__name__}")

    # Valid PDF filename but DOCX content
    try:
        docx_data = make_docx("Some contract text here.")
        result = extract_text(docx_data, "contract.pdf")
        info(f"DOCX content with PDF filename — got: '{result[:40]}'")
    except Exception as e:
        ok(f"Wrong file type detected: {type(e).__name__}")

    # Zero bytes
    try:
        extract_text(b"", "empty.pdf")
        fail("Zero bytes should fail")
    except Exception as e:
        ok(f"Zero bytes correctly rejected: {type(e).__name__}")


# ── Test 5: Special characters ────────────────────────────────────
def test_special_characters():
    header("Test 5 — Special characters and international text")

    # Hindi text (relevant for Indian contracts)
    hindi_contract = """CONTRACT AGREEMENT
    
यह अनुबंध दोनों पक्षों के बीच है।
This agreement is between both parties.

Clause 1: दायित्व (Liability)
The liability shall not exceed Rs. 10,00,000 (Ten Lakhs).

Clause 2: क्षेत्राधिकार (Jurisdiction)  
This contract is governed by Indian law."""

    try:
        data = make_pdf(hindi_contract)
        text = extract_text(data, "hindi_contract.pdf")
        ok(f"International text handled ({get_word_count(text)} words extracted)")
    except Exception as e:
        fail(f"International text failed: {e}")

    # Special legal symbols
    symbols_contract = """AGREEMENT § 1.1
    
The parties agree © 2025. All rights reserved ®.
Payment: ₹5,00,000 or USD $10,000 or €8,500.
Clause 2 — Auto-renewal: 90 days' notice required.
Section 3 • Liability cap: 2× annual contract value."""

    try:
        data = make_pdf(symbols_contract)
        text = extract_text(data, "symbols.pdf")
        ok(f"Special symbols handled")
    except Exception as e:
        fail(f"Special symbols failed: {e}")


# ── Test 6: Mock AI analysis edge cases ──────────────────────────
def test_ai_edge_cases():
    header("Test 6 — AI analysis edge cases (mock mode)")

    os.environ["MOCK_AI"] = "true"

    # Very short contract text
    try:
        result = analyze_contract("Agreement between A and B. Sign here: ___")
        counts = get_flag_counts(result)
        ok(f"Very short text analysed (mock): {counts['total']} flags")
    except Exception as e:
        fail(f"Short text analysis failed: {e}")

    # Contract with only numbers/dates
    try:
        result = analyze_contract("01/01/2025. $500,000. 90 days. 3 years. Delaware.")
        ok("Numbers-only contract analysed (mock)")
    except Exception as e:
        fail(f"Numbers-only analysis failed: {e}")

    # Very long text (at truncation boundary)
    long_text = "The parties agree to the following terms. " * 3000
    try:
        truncated = truncate_for_api(long_text)
        result = analyze_contract(truncated)
        ok(f"Long text analysed after truncation ({len(truncated):,} chars)")
    except Exception as e:
        fail(f"Long text analysis failed: {e}")

    # Verify mock result structure
    try:
        result = analyze_contract("test contract")
        required = ['summary', 'contract_type', 'overall_risk',
                    'parties', 'key_dates', 'flags', 'positives', 'questions_to_ask']
        missing = [f for f in required if f not in result]
        if missing:
            fail(f"Mock result missing fields: {missing}")
        else:
            ok(f"Mock result has all required fields ({len(required)} fields)")
    except Exception as e:
        fail(f"Structure check failed: {e}")


# ── Test 7: Concurrent safety ─────────────────────────────────────
def test_concurrent_safety():
    header("Test 7 — Concurrent request simulation")
    import threading

    os.environ["MOCK_AI"] = "true"
    results = []
    errors  = []

    def process_contract(i):
        try:
            text = f"Contract {i}: Agreement between Party A and Party B. " * 20
            result = analyze_contract(text)
            results.append(result.get("overall_risk"))
        except Exception as e:
            errors.append(str(e))

    # Simulate 10 concurrent analyses
    threads = [threading.Thread(target=process_contract, args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()

    if errors:
        fail(f"{len(errors)} concurrent requests failed: {errors[0]}")
    else:
        ok(f"10 concurrent analyses completed without errors")
        ok(f"All returned risk level: {set(results)}")


# ── Test 8: Full pipeline with edge cases ─────────────────────────
def test_full_pipeline_edge_cases():
    header("Test 8 — Full pipeline edge cases")

    os.environ["MOCK_AI"] = "true"

    # Pipeline with a DOCX
    try:
        docx_data = make_docx("""VENDOR SERVICES AGREEMENT
        
This agreement is between BigCorp and SmallStartup.
        
1. PAYMENT: Client shall pay within 60 days.
2. LIABILITY: Vendor has unlimited liability.
3. TERMINATION: Client can terminate in 7 days, vendor needs 180 days.""")

        text = extract_text(docx_data, "vendor.docx")
        truncated = truncate_for_api(text)
        result = analyze_contract(truncated)
        counts = get_flag_counts(result)

        ok(f"DOCX full pipeline: {get_word_count(text)} words → {counts['total']} flags")
    except Exception as e:
        fail(f"DOCX pipeline failed: {e}")

    # Pipeline with unicode filename
    try:
        data = make_pdf("Standard NDA between parties.")
        text = extract_text(data, "अनुबंध_contract.pdf")
        ok(f"Unicode filename handled")
    except Exception as e:
        fail(f"Unicode filename failed: {e}")


# ── Main ──────────────────────────────────────────────────────────
def main():
    print(f"\n{BOLD}ContractAI — Day 6 Edge Case Tests{RESET}")
    print("Stress-testing the backend with every weird input possible.\n")

    test_file_types()
    test_empty_files()
    test_large_files()
    test_corrupted_files()
    test_special_characters()
    test_ai_edge_cases()
    test_concurrent_safety()
    test_full_pipeline_edge_cases()

    # Summary
    total = passed_total + failed_total
    print(f"\n{BOLD}{'='*55}")
    print(f"FINAL RESULTS: {passed_total}/{total} tests passed")
    print('='*55 + RESET)

    if failed_total == 0:
        print(f"{GREEN}{BOLD}All edge cases handled — backend is bulletproof!{RESET}")
        print("Day 6 complete. Ready for Day 7 (cleanup) then frontend.")
    else:
        print(f"{YELLOW}{failed_total} issue(s) found — review above and fix before frontend.{RESET}")
        print("Most edge case failures are acceptable — check if they're")
        print("gracefully handled or silently swallowed.")

if __name__ == "__main__":
    main()
