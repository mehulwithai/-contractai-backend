from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from supabase import Client
from datetime import datetime, timezone
import os
import uuid

from app.core.auth import get_current_user, get_supabase
from app.services.parser import extract_text, truncate_for_api, get_word_count
from app.services.analyzer import analyze_contract, get_flag_counts

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
FREE_TIER_LIMIT = 1  # free users get 1 review


def get_admin_emails() -> set:
    from app.core.config import get_settings
    settings = get_settings()
    raw = settings.admin_emails
    parsed = {e.strip().lower() for e in raw.split(",") if e.strip()}
    print(f"DEBUG: ADMIN_EMAILS from settings = {raw!r}, parsed = {parsed}")
    return parsed


def check_usage_limit(user_id: str, user_email: str, supabase: Client) -> None:
    """Raise 402 if free user has hit their review limit."""
    # Admin allowlist — always unlimited, skip every other check
    if user_email and user_email.lower() in get_admin_emails():
        return

    # Check subscription
    sub = supabase.table("subscriptions") \
        .select("plan") \
        .eq("user_id", user_id) \
        .eq("status", "active") \
        .execute()

    if sub.data:
        return  # Paid user — no limit

    # Count this month's reviews
    start_of_month = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    ).isoformat()

    count = supabase.table("reviews") \
        .select("id", count="exact") \
        .eq("user_id", user_id) \
        .gte("created_at", start_of_month) \
        .execute()

    if (count.count or 0) >= FREE_TIER_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "free_limit_reached",
                "message": "You've used your free review. Upgrade to review unlimited contracts.",
                "upgrade_url": "/upgrade"
            }
        )


@router.post("/")
async def create_review(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Upload a contract (PDF or DOCX) → get back an AI risk analysis.
    This is the core endpoint of the entire product.
    """
    # 1. Validate file
    if not file.filename:
        raise HTTPException(400, "No file provided")

    fname = file.filename.lower()
    if not (fname.endswith(".pdf") or fname.endswith(".docx")):
        raise HTTPException(400, "Please upload a PDF or DOCX file")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large. Maximum size is 10MB")

    # 2. Check usage limit (free tier, bypassed for admin emails)
    print(f"DEBUG: uploading user email = {user.get('email', 'NONE')!r}")
    check_usage_limit(user["id"], user.get("email", ""), supabase)

    # 3. Extract text
    try:
        contract_text = extract_text(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(400, str(e))

    word_count = get_word_count(contract_text)
    truncated_text = truncate_for_api(contract_text)

    # 4. Store original file in Supabase Storage
    storage_path = f"{user['id']}/{uuid.uuid4()}/{file.filename}"
    try:
        supabase.storage.from_("contracts").upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": file.content_type or "application/octet-stream"}
        )
    except Exception:
        storage_path = None  # Don't block the review if storage fails

    # 5. Run AI analysis
    try:
        result = analyze_contract(truncated_text)
    except Exception as e:
        raise HTTPException(500, f"AI analysis failed: {str(e)}")

    flag_counts = get_flag_counts(result)

    # 6. Save review to database
    review_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    review_row = {
        "id": review_id,
        "user_id": user["id"],
        "filename": file.filename,
        "storage_path": storage_path,
        "word_count": word_count,
        "overall_risk": result.get("overall_risk", "unknown"),
        "contract_type": result.get("contract_type", "Other"),
        "flag_count_red": flag_counts["red"],
        "flag_count_amber": flag_counts["amber"],
        "flag_count_total": flag_counts["total"],
        "result": result,
        "created_at": now,
    }

    supabase.table("reviews").insert(review_row).execute()

    return {
        "review_id": review_id,
        "filename": file.filename,
        "created_at": now,
        "word_count": word_count,
        "result": result,
        "flag_counts": flag_counts,
    }


@router.get("/")
async def list_reviews(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """Return all reviews for the current user, newest first."""
    response = supabase.table("reviews") \
        .select("id, filename, overall_risk, contract_type, flag_count_red, flag_count_total, created_at") \
        .eq("user_id", user["id"]) \
        .order("created_at", desc=True) \
        .execute()

    return {"reviews": response.data}


@router.get("/{review_id}")
async def get_review(
    review_id: str,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """Return a single review by ID. Only accessible by the owner."""
    response = supabase.table("reviews") \
        .select("*") \
        .eq("id", review_id) \
        .eq("user_id", user["id"]) \
        .single() \
        .execute()

    if not response.data:
        raise HTTPException(404, "Review not found")

    return response.data


@router.delete("/{review_id}")
async def delete_review(
    review_id: str,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """Delete a review and its stored file."""
    # Verify ownership first
    review = supabase.table("reviews") \
        .select("storage_path") \
        .eq("id", review_id) \
        .eq("user_id", user["id"]) \
        .single() \
        .execute()

    if not review.data:
        raise HTTPException(404, "Review not found")

    # Delete file from storage
    if review.data.get("storage_path"):
        try:
            supabase.storage.from_("contracts").remove([review.data["storage_path"]])
        except Exception:
            pass  # Don't block deletion if storage removal fails

    # Delete review record
    supabase.table("reviews").delete().eq("id", review_id).execute()

    return {"deleted": True}
