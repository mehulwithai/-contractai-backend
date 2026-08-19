from fastapi import APIRouter, Depends, HTTPException, Request
from supabase import Client
import stripe

from app.core.auth import get_current_user, get_supabase
from app.core.config import get_settings

router = APIRouter(prefix="/api/billing", tags=["billing"])


def get_stripe():
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key
    return stripe


WHOP_CHECKOUT_URL = "https://whop.com/checkout/plan_RgYzPBJgecKVf"


@router.post("/checkout")
async def create_checkout_session(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Return Whop Checkout session URL for the $10/mo Growth plan.
    """
    user_email = user.get("email", "")
    user_id = user.get("id", "")
    checkout_url = f"{WHOP_CHECKOUT_URL}?email={user_email}&metadata[user_id]={user_id}"
    return {"checkout_url": checkout_url}


@router.post("/webhook")
async def whop_webhook(
    request: Request,
    supabase: Client = Depends(get_supabase)
):
    """
    Handles Whop payment and membership webhooks to activate/cancel subscriptions in Supabase.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")

    event_action = body.get("action") or body.get("event") or body.get("type")
    data = body.get("data", body)

    user_email = None
    user_id = None
    membership_id = data.get("id") or data.get("membership_id")

    if isinstance(data.get("user"), dict):
        user_email = data["user"].get("email")
    elif data.get("email"):
        user_email = data.get("email")

    if data.get("metadata") and isinstance(data["metadata"], dict):
        user_id = data["metadata"].get("user_id")

    if event_action in ["membership.activated", "membership.went_valid", "payment.succeeded", "membership.created", "checkout.session.completed"]:
        if user_id:
            supabase.table("subscriptions").upsert({
                "user_id": user_id,
                "stripe_subscription_id": str(membership_id or f"whop_{user_id}"),
                "stripe_customer_id": user_email or "whop_customer",
                "plan": "growth",
                "status": "active",
            }).execute()

    elif event_action in ["membership.deactivated", "membership.went_invalid", "membership.deleted", "payment.failed", "customer.subscription.deleted"]:
        if user_id:
            supabase.table("subscriptions") \
                .update({"status": "cancelled"}) \
                .eq("user_id", user_id) \
                .execute()

    return {"received": True}


@router.get("/status")
async def get_subscription_status(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """Check if the current user has an active subscription."""
    sub = supabase.table("subscriptions") \
        .select("plan, status") \
        .eq("user_id", user["id"]) \
        .eq("status", "active") \
        .execute()

    is_subscribed = bool(sub.data)

    return {
        "is_subscribed": is_subscribed,
        "plan": sub.data[0]["plan"] if is_subscribed else "free",
    }


@router.post("/portal")
async def create_billing_portal(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """Return Whop customer orders portal for managing subscription."""
    return {"portal_url": "https://whop.com/orders"}

