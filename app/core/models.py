from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# --- Review models ---

class RiskFlag(BaseModel):
    id: int
    title: str
    clause: str
    issue: str
    severity: str  # red | amber | green
    suggestion: str


class KeyDate(BaseModel):
    label: str
    date: Optional[str]


class FlagCounts(BaseModel):
    total: int
    red: int
    amber: int
    green: int


class ReviewResult(BaseModel):
    summary: str
    contract_type: str
    overall_risk: str  # low | medium | high
    parties: list[str]
    key_dates: list[KeyDate]
    flags: list[RiskFlag]
    positives: list[str]
    questions_to_ask: list[str]


class ReviewResponse(BaseModel):
    review_id: str
    filename: str
    created_at: str
    result: ReviewResult
    flag_counts: FlagCounts


# --- Auth models ---

class SignUpRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    user_id: str
    email: str


# --- Subscription models ---

class SubscriptionStatus(BaseModel):
    is_subscribed: bool
    plan: str  # free | starter | growth
    contracts_used_this_month: int
    contracts_limit: int  # -1 = unlimited


# --- Error model ---

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
