"""
Day 5 — Supabase connection + auth test
Tests: connection, schema, sign up, sign in, save review, list reviews, delete

Usage:
    python tests/test_supabase.py
"""

import sys, os, json, uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from app.core.config import get_settings

# ── Colours for terminal output ───────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):   print(f"  {GREEN}[PASS]{RESET} {msg}")
def fail(msg): print(f"  {RED}[FAIL]{RESET} {msg}")
def info(msg): print(f"  {YELLOW}[INFO]{RESET} {msg}")
def header(msg): print(f"\n{BOLD}{'─'*55}\n{msg}\n{'─'*55}{RESET}")


# ── Test 1: Config ────────────────────────────────────────────────
def test_config():
    header("Test 1 — Config / .env check")
    settings = get_settings()
    passed = True

    if settings.supabase_url and settings.supabase_url != "your_supabase_project_url_here":
        ok(f"SUPABASE_URL set → {settings.supabase_url[:40]}...")
    else:
        fail("SUPABASE_URL not set in .env")
        passed = False

    if settings.supabase_service_key and len(settings.supabase_service_key) > 20:
        ok("SUPABASE_SERVICE_KEY set")
    else:
        fail("SUPABASE_SERVICE_KEY not set in .env")
        passed = False

    return passed, settings


# ── Test 2: Connection ────────────────────────────────────────────
def test_connection(settings):
    header("Test 2 — Supabase connection")
    try:
        from supabase import create_client
        sb = create_client(settings.supabase_url, settings.supabase_service_key)
        ok("Connected to Supabase successfully")
        return True, sb
    except Exception as e:
        fail(f"Connection failed: {e}")
        info("Check your SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")
        return False, None


# ── Test 3: Schema ────────────────────────────────────────────────
def test_schema(sb):
    header("Test 3 — Database schema check")
    passed = True

    for table in ["reviews", "subscriptions"]:
        try:
            sb.table(table).select("*").limit(1).execute()
            ok(f"Table '{table}' exists")
        except Exception as e:
            fail(f"Table '{table}' missing — did you run supabase_schema.sql?")
            info("Go to Supabase → SQL Editor → paste supabase_schema.sql → Run")
            passed = False

    # Check storage bucket
    try:
        buckets = sb.storage.list_buckets()
        names = [b.name for b in buckets]
        if "contracts" in names:
            ok("Storage bucket 'contracts' exists")
        else:
            fail("Storage bucket 'contracts' missing")
            info("The schema SQL should have created it — re-run supabase_schema.sql")
            passed = False
    except Exception as e:
        fail(f"Storage check failed: {e}")
        passed = False

    return passed


# ── Test 4: Sign up a test user ───────────────────────────────────
def test_signup(sb):
    header("Test 4 — User signup")
    # Use a unique email so repeat runs don't fail
    test_email    = f"test_{uuid.uuid4().hex[:8]}@contractai-test.com"
    test_password = "TestPassword123!"

    try:
        res = sb.auth.sign_up({"email": test_email, "password": test_password})
        if res.user:
            ok(f"User created: {test_email}")
            ok(f"User ID: {res.user.id}")
            return True, res.user.id, test_email, test_password
        else:
            fail("Sign up returned no user")
            return False, None, None, None
    except Exception as e:
        fail(f"Sign up failed: {e}")
        info("Make sure Email auth is enabled: Supabase → Authentication → Providers → Email")
        return False, None, None, None


# ── Test 5: Sign in ───────────────────────────────────────────────
def test_signin(sb, email, password):
    header("Test 5 — User sign in")
    try:
        res = sb.auth.sign_in_with_password({"email": email, "password": password})
        if res.session:
            ok(f"Signed in as {email}")
            ok(f"Access token: {res.session.access_token[:40]}...")
            return True, res.session.access_token
        else:
            fail("Sign in returned no session")
            return False, None
    except Exception as e:
        # New accounts may need email confirmation depending on settings
        if "Email not confirmed" in str(e):
            info("Email confirmation required — disable it for dev:")
            info("Supabase → Authentication → Email → Disable 'Confirm email'")
        else:
            fail(f"Sign in failed: {e}")
        return False, None


# ── Test 6: Save a review ─────────────────────────────────────────
def test_save_review(sb, user_id):
    header("Test 6 — Save review to database")

    review_id = str(uuid.uuid4())
    mock_result = {
        "summary": "Test NDA between two parties.",
        "contract_type": "NDA",
        "overall_risk": "high",
        "parties": ["Acme Corp", "TechStartup Pvt Ltd"],
        "key_dates": [{"label": "Start", "date": "2025-01-01"}],
        "flags": [
            {
                "id": 1,
                "title": "High damages",
                "clause": "pay $500,000 per breach",
                "issue": "Disproportionate penalty",
                "severity": "red",
                "suggestion": "Negotiate cap to $10,000"
            }
        ],
        "positives": ["Clear definitions"],
        "questions_to_ask": ["Can damages be capped?"],
        "_meta": {"model": "MOCK", "input_tokens": 0, "output_tokens": 0}
    }

    row = {
        "id":               review_id,
        "user_id":          user_id,
        "filename":         "test_contract.pdf",
        "storage_path":     None,
        "word_count":       250,
        "overall_risk":     "high",
        "contract_type":    "NDA",
        "flag_count_red":   1,
        "flag_count_amber": 0,
        "flag_count_total": 1,
        "result":           mock_result,
        "created_at":       datetime.now(timezone.utc).isoformat(),
    }

    try:
        res = sb.table("reviews").insert(row).execute()
        if res.data:
            ok(f"Review saved — ID: {review_id}")
            ok(f"Rows in response: {len(res.data)}")
            return True, review_id
        else:
            fail("Insert returned no data")
            return False, None
    except Exception as e:
        fail(f"Save failed: {e}")
        return False, None


# ── Test 7: Fetch reviews ─────────────────────────────────────────
def test_fetch_reviews(sb, user_id, review_id):
    header("Test 7 — Fetch reviews for user")
    try:
        # List all reviews for this user
        res = sb.table("reviews") \
            .select("id, filename, overall_risk, contract_type, created_at") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .execute()

        ok(f"Found {len(res.data)} review(s) for user")

        # Fetch the specific review
        res2 = sb.table("reviews") \
            .select("*") \
            .eq("id", review_id) \
            .eq("user_id", user_id) \
            .single() \
            .execute()

        if res2.data:
            ok(f"Single review fetch works")
            ok(f"Risk level stored: {res2.data.get('overall_risk')}")
            ok(f"Flag count stored: {res2.data.get('flag_count_total')}")
            return True
        else:
            fail("Single review fetch returned nothing")
            return False
    except Exception as e:
        fail(f"Fetch failed: {e}")
        return False


# ── Test 8: Cleanup ───────────────────────────────────────────────
def test_cleanup(sb, user_id, review_id):
    header("Test 8 — Cleanup test data")
    try:
        sb.table("reviews").delete().eq("id", review_id).execute()
        ok(f"Deleted test review")
        # Delete test user via admin API
        sb.auth.admin.delete_user(user_id)
        ok(f"Deleted test user")
        return True
    except Exception as e:
        info(f"Cleanup note: {e} (not critical)")
        return True


# ── Main ──────────────────────────────────────────────────────────
def main():
    print(f"\n{BOLD}ContractAI — Day 5 Supabase Tests{RESET}")
    print("Tests your database connection, schema, auth, and review storage.\n")

    results = {}

    # Test 1 — Config
    passed, settings = test_config()
    results["Config"] = passed
    if not passed:
        print(f"\n{RED}Cannot continue — fix .env first{RESET}")
        return

    # Test 2 — Connection
    passed, sb = test_connection(settings)
    results["Connection"] = passed
    if not passed:
        print(f"\n{RED}Cannot continue — fix Supabase connection{RESET}")
        return

    # Test 3 — Schema
    results["Schema"] = test_schema(sb)

    # Test 4 — Signup
    passed, user_id, email, password = test_signup(sb)
    results["Signup"] = passed
    if not passed:
        print(f"\n{RED}Cannot continue — fix auth first{RESET}")
        _print_summary(results)
        return

    # Test 5 — Signin
    passed, token = test_signin(sb, email, password)
    results["Signin"] = passed
    # Don't stop if signin fails — could be email confirm setting
    # We still have user_id from signup to continue testing DB

    # Test 6 — Save review
    passed, review_id = test_save_review(sb, user_id)
    results["Save review"] = passed

    # Test 7 — Fetch reviews
    if passed and review_id:
        results["Fetch reviews"] = test_fetch_reviews(sb, user_id, review_id)
    else:
        results["Fetch reviews"] = False

    # Test 8 — Cleanup
    if review_id:
        test_cleanup(sb, user_id, review_id)

    _print_summary(results)


def _print_summary(results):
    header("SUMMARY")
    passed = sum(1 for v in results.values() if v)
    total  = len(results)
    for name, ok_val in results.items():
        status = f"{GREEN}PASS{RESET}" if ok_val else f"{RED}FAIL{RESET}"
        print(f"  [{status}] {name}")

    print(f"\n  {passed}/{total} tests passed")

    if passed == total:
        print(f"\n  {GREEN}{BOLD}Day 5 complete!{RESET}")
        print(  "  Supabase is fully wired up.")
        print(  "  Next: Day 6 — bug fixes + full pipeline test with real user")
    else:
        print(f"\n  {YELLOW}Fix the failing tests above, then re-run.{RESET}")
        print(  "  Most common fixes are shown above each failure.")


if __name__ == "__main__":
    main()
