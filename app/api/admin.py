from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from datetime import datetime, timezone, timedelta

from app.core.auth import get_current_user, get_supabase
from app.api.reviews import get_admin_emails

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(user: dict) -> None:
    """Only emails in ADMIN_EMAILS can access admin routes."""
    email = (user.get("email") or "").lower()
    if email not in get_admin_emails():
        raise HTTPException(403, "Not authorized")


@router.get("/stats")
async def get_admin_stats(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Returns aggregate stats for the admin dashboard:
    total users, paid subscribers, reviews this month, daily trend,
    risk distribution, and recent activity.
    """
    require_admin(user)

    now = datetime.now(timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    fourteen_days_ago = now - timedelta(days=14)

    # --- Total users (from auth.users via admin API) ---
    try:
        users_resp = supabase.auth.admin.list_users()
        total_users = len(users_resp) if isinstance(users_resp, list) else len(users_resp.users)
    except Exception:
        total_users = None

    # --- Active subscriptions ---
    subs = supabase.table("subscriptions") \
        .select("id, plan, status, created_at") \
        .eq("status", "active") \
        .execute()
    active_subs = subs.data or []

    # --- Reviews this month ---
    reviews_month = supabase.table("reviews") \
        .select("id", count="exact") \
        .gte("created_at", start_of_month.isoformat()) \
        .execute()

    # --- All reviews in last 14 days (for trend + risk breakdown) ---
    recent_reviews = supabase.table("reviews") \
        .select("id, created_at, overall_risk, user_id, filename") \
        .gte("created_at", fourteen_days_ago.isoformat()) \
        .order("created_at", desc=True) \
        .execute()

    reviews_data = recent_reviews.data or []

    # --- Daily trend: reviews per day, last 14 days ---
    daily_counts = {}
    for i in range(14):
        day = (now - timedelta(days=13 - i)).strftime("%Y-%m-%d")
        daily_counts[day] = 0
    for r in reviews_data:
        day = r["created_at"][:10]
        if day in daily_counts:
            daily_counts[day] += 1

    # --- Risk distribution (last 14 days) ---
    risk_counts = {"high": 0, "medium": 0, "low": 0}
    for r in reviews_data:
        risk = r.get("overall_risk")
        if risk in risk_counts:
            risk_counts[risk] += 1

    # --- Recent activity feed (last 10 reviews) ---
    recent_activity = [
        {
            "filename": r.get("filename"),
            "overall_risk": r.get("overall_risk"),
            "created_at": r.get("created_at"),
        }
        for r in reviews_data[:10]
    ]

    return {
        "total_users": total_users,
        "active_subscribers": len(active_subs),
        "mrr_estimate": len(active_subs) * 49,  # adjust if you add more plan tiers
        "reviews_this_month": reviews_month.count or 0,
        "daily_trend": [{"date": d, "count": c} for d, c in daily_counts.items()],
        "risk_distribution": risk_counts,
        "recent_activity": recent_activity,
    }


@router.get("/users")
async def get_admin_users(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """Returns a list of all signed-up users with basic info, for the admin table."""
    require_admin(user)

    try:
        users_resp = supabase.auth.admin.list_users()
        users_list = users_resp if isinstance(users_resp, list) else users_resp.users
    except Exception as e:
        raise HTTPException(500, f"Could not fetch users: {e}")

    # Get review counts per user
    reviews = supabase.table("reviews").select("user_id").execute()
    review_counts = {}
    for r in (reviews.data or []):
        uid = r["user_id"]
        review_counts[uid] = review_counts.get(uid, 0) + 1

    # Get active subscriptions
    subs = supabase.table("subscriptions").select("user_id").eq("status", "active").execute()
    subscribed_ids = {s["user_id"] for s in (subs.data or [])}

    result = []
    for u in users_list:
        uid = u.id
        result.append({
            "id": uid,
            "email": u.email,
            "created_at": u.created_at,
            "last_sign_in_at": getattr(u, "last_sign_in_at", None),
            "review_count": review_counts.get(uid, 0),
            "is_subscribed": uid in subscribed_ids,
        })

    result.sort(key=lambda x: x["created_at"], reverse=True)
    return {"users": result}
