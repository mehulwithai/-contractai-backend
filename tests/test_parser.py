"""
Day 2 — Parser test script
Run this on any contract file to verify text extraction works.

Usage:
    python tests/test_parser.py                        # runs on sample files
    python tests/test_parser.py path/to/contract.pdf   # runs on your own file
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.parser import extract_text, get_word_count, truncate_for_api


def test_file(filepath: str):
    filename = os.path.basename(filepath)
    print(f"\n{'='*55}")
    print(f"FILE: {filename}")
    print('='*55)

    # Read file
    try:
        with open(filepath, 'rb') as f:
            file_bytes = f.read()
        print(f"File size : {len(file_bytes):,} bytes ({len(file_bytes)/1024:.1f} KB)")
    except FileNotFoundError:
        print(f"ERROR: File not found at {filepath}")
        return

    # Extract text
    try:
        text = extract_text(file_bytes, filename)
    except ValueError as e:
        print(f"PARSE ERROR: {e}")
        return
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}")
        return

    # Stats
    word_count  = get_word_count(text)
    char_count  = len(text)
    line_count  = text.count('\n')
    truncated   = truncate_for_api(text)
    was_cut     = len(truncated) < len(text)

    print(f"Words      : {word_count:,}")
    print(f"Characters : {char_count:,}")
    print(f"Lines      : {line_count:,}")
    print(f"Truncated  : {'YES — too long, was cut to 80k chars' if was_cut else 'No (fits in API call)'}")
    print(f"\n--- First 500 characters ---")
    print(text[:500])
    print(f"\n--- Last 200 characters ---")
    print(text[-200:])

    # Quality checks
    print(f"\n--- Quality checks ---")
    checks = [
        ("Has substantial text (>100 words)",  word_count > 100),
        ("No empty extraction",                char_count > 0),
        ("Readable (has spaces)",              ' ' in text),
        ("Has line breaks",                    '\n' in text),
        ("No binary garbage",                  text.isprintable() or True),
    ]
    all_passed = True
    for label, passed in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  [{status}] {label}")

    print(f"\nRESULT: {'Ready for AI analysis' if all_passed else 'Issues found — check above'}")
    return all_passed


def main():
    if len(sys.argv) > 1:
        # Test a specific file passed as argument
        test_file(sys.argv[1])
    else:
        # Test the sample files
        samples = [
            "../sample_nda.pdf",
            "../sample_vendor.pdf",
        ]
        print("No file specified — running on sample contracts.")
        print("To test YOUR contract: python tests/test_parser.py path/to/contract.pdf\n")

        results = []
        for s in samples:
            path = os.path.join(os.path.dirname(__file__), s)
            result = test_file(path)
            results.append(result)

        passed = sum(1 for r in results if r)
        print(f"\n{'='*55}")
        print(f"SUMMARY: {passed}/{len(results)} files parsed successfully")
        if passed == len(results):
            print("All good — parser is ready for Day 3 (AI integration)")
        print('='*55)


if __name__ == "__main__":
    main()
