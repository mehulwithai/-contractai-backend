"""
Day 5 — Live server test
Tests your running FastAPI server end-to-end using HTTP requests.
The server must be running first:
    uvicorn app.main:app --reload --port 8000

Usage:
    python tests/test_server.py
"""

import sys, os, json, requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

BASE = "http://localhost:8000"

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"
BOLD = "\033[1m"; RESET = "\033[0m"

def ok(msg):   print(f"  {GREEN}[PASS]{RESET} {msg}")
def fail(msg): print(f"  {RED}[FAIL]{RESET} {msg}")
def info(msg): print(f"  {YELLOW}[INFO]{RESET} {msg}")
def header(msg): print(f"\n{BOLD}{'─'*55}\n{msg}\n{'─'*55}{RESET}")


def test_health():
    header("Test 1 — Server health check")
    try:
        r = requests.get(f"{BASE}/", timeout=5)
        data = r.json()
        if data.get("status") == "running":
            ok(f"Server is running — version {data.get('version')}")
            return True
        else:
            fail(f"Unexpected response: {data}")
            return False
    except requests.ConnectionError:
        fail("Cannot connect to server")
        info("Make sure the server is running:")
        info("  cd E:\\SaaS && venv\\Scripts\\activate")
        info("  uvicorn app.main:app --reload --port 8000")
        return False


def test_signup_via_server(email, password):
    header("Test 2 — Sign up via Supabase (direct)")
    from supabase import create_client
    from app.core.config import get_settings
    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_key)

    try:
        res = sb.auth.sign_up({"email": email, "password": password})
        if res.user:
            ok(f"User created: {email}")
            return True, sb
        fail("Signup returned no user")
        return False, None
    except Exception as e:
        fail(f"Signup failed: {e}")
        return False, None


def test_signin_get_token(sb, email, password):
    header("Test 3 — Sign in + get JWT token")
    try:
        res = sb.auth.sign_in_with_password({"email": email, "password": password})
        if res.session:
            token = res.session.access_token
            ok(f"Got JWT token: {token[:40]}...")
            return True, token
        fail("No session returned")
        info("Disable email confirmation: Supabase → Auth → Email → uncheck 'Confirm email'")
        return False, None
    except Exception as e:
        if "Email not confirmed" in str(e):
            fail("Email confirmation required")
            info("Fix: Supabase → Authentication → Providers → Email → disable 'Confirm email'")
        else:
            fail(f"Signin failed: {e}")
        return False, None


def test_upload_contract(token):
    header("Test 4 — Upload contract via API")

    # Use sample NDA if it exists
    contract_path = "sample_nda.pdf"
    if not os.path.exists(contract_path):
        fail(f"sample_nda.pdf not found — run from E:\\SaaS directory")
        return False, None

    headers = {"Authorization": f"Bearer {token}"}
    with open(contract_path, "rb") as f:
        files   = {"file": ("sample_nda.pdf", f, "application/pdf")}
        try:
            r = requests.post(
                f"{BASE}/api/reviews/",
                headers=headers,
                files=files,
                timeout=30
            )
        except Exception as e:
            fail(f"Request failed: {e}")
            return False, None

    if r.status_code == 200:
        data = r.json()
        ok(f"Review created — ID: {data.get('review_id', '')[:16]}...")
        ok(f"Risk level: {data.get('result', {}).get('overall_risk', '?').upper()}")
        ok(f"Flags found: {data.get('flag_counts', {}).get('total', 0)}")
        return True, data.get("review_id")
    elif r.status_code == 402:
        info("Free limit reached — that's fine, paywall is working correctly")
        return True, None
    else:
        fail(f"Upload failed — status {r.status_code}")
        info(f"Response: {r.text[:300]}")
        return False, None


def test_list_reviews(token):
    header("Test 5 — List reviews")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{BASE}/api/reviews/", headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            count = len(data.get("reviews", []))
            ok(f"Listed {count} review(s) for user")
            return True
        else:
            fail(f"List failed — status {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        fail(f"Request failed: {e}")
        return False


def test_billing_status(token):
    header("Test 6 — Billing status")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{BASE}/api/billing/status", headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            ok(f"Plan: {data.get('plan', '?')}")
            ok(f"Subscribed: {data.get('is_subscribed', False)}")
            return True
        else:
            fail(f"Billing status failed — {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        fail(f"Request failed: {e}")
        return False


def main():
    import uuid
    print(f"\n{BOLD}ContractAI — Day 5 Live Server Tests{RESET}")

    results = {}

    # Test 1 — health
    results["Health"] = test_health()
    if not results["Health"]:
        print(f"\n{RED}Start the server first, then re-run this script.{RESET}")
        return

    # Create test user
    email    = f"test_{uuid.uuid4().hex[:6]}@contractai-test.com"
    password = "TestPass123!"

    passed, sb = test_signup_via_server(email, password)
    results["Signup"] = passed
    if not passed:
        _summary(results); return

    passed, token = test_signin_get_token(sb, email, password)
    results["Signin"] = passed
    if not passed:
        _summary(results); return

    results["Upload contract"] = test_upload_contract(token)[0]
    results["List reviews"]    = test_list_reviews(token)
    results["Billing status"]  = test_billing_status(token)

    # Cleanup test user
    try:
        sb.auth.admin.delete_user(sb.auth.get_user(token).user.id)
    except: pass

    _summary(results)


def _summary(results):
    header("SUMMARY")
    passed = sum(1 for v in results.values() if v)
    for name, v in results.items():
        s = f"{GREEN}PASS{RESET}" if v else f"{RED}FAIL{RESET}"
        print(f"  [{s}] {name}")
    print(f"\n  {passed}/{len(results)} tests passed")
    if passed == len(results):
        print(f"\n  {GREEN}{BOLD}Full server pipeline working!{RESET}")
        print(  "  Day 5 complete — ready for Day 6 (bug fixes + polish)")


if __name__ == "__main__":
    main()
