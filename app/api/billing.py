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


@router.post("/checkout")
async def create_checkout_session(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Create a Stripe Checkout session for the $49/mo plan.
    Returns a URL to redirect the user to.
    """
    settings = get_settings()
    get_stripe()

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
            success_url=f"{settings.frontend_url}/dashboard?payment=success",
            cancel_url=f"{settings.frontend_url}/upgrade?payment=cancelled",
            metadata={"user_id": user["id"], "email": user["email"]},
            customer_email=user["email"],
        )
        return {"checkout_url": session.url}
    except Exception as e:
        raise HTTPException(500, f"Failed to create checkout session: {str(e)}")


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    supabase: Client = Depends(get_supabase)
):
    """
    Stripe sends events here after payment.
    We listen for checkout.session.completed to activate subscriptions,
    and customer.subscription.deleted to deactivate them.
    """
    settings = get_settings()
    get_stripe()

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except Exception:
        raise HTTPException(400, "Invalid webhook signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session["metadata"].get("user_id")
        subscription_id = session.get("subscription")

        if user_id and subscription_id:
            supabase.table("subscriptions").upsert({
                "user_id": user_id,
                "stripe_subscription_id": subscription_id,
                "stripe_customer_id": session.get("customer"),
                "plan": "starter",
                "status": "active",
            }).execute()

    elif event["type"] == "customer.subscription.deleted":
        subscription_id = event["data"]["object"]["id"]
        supabase.table("subscriptions") \
            .update({"status": "cancelled"}) \
            .eq("stripe_subscription_id", subscription_id) \
            .execute()

    elif event["type"] == "invoice.payment_failed":
        subscription_id = event["data"]["object"].get("subscription")
        if subscription_id:
            supabase.table("subscriptions") \
                .update({"status": "past_due"}) \
                .eq("stripe_subscription_id", subscription_id) \
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
    """Create a Stripe billing portal session for managing subscription."""
    settings = get_settings()
    get_stripe()

    sub = supabase.table("subscriptions") \
        .select("stripe_customer_id") \
        .eq("user_id", user["id"]) \
        .execute()

    if not sub.data:
        raise HTTPException(404, "No subscription found")

    try:
        session = stripe.billing_portal.Session.create(
            customer=sub.data[0]["stripe_customer_id"],
            return_url=f"{settings.frontend_url}/dashboard",
        )
        return {"portal_url": session.url}
    except Exception as e:
        raise HTTPException(500, str(e))
