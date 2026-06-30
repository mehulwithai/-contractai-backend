from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.reviews import router as reviews_router
from app.api.billing import router as billing_router
from app.api.admin import router as admin_router

from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="ContractAI",
    description="AI-powered contract review for founders and SMBs",
    version="0.1.0",
)

# CORS — allow your Next.js frontend
app.add_middleware(
    CORSMiddleware,
allow_origins=["http://localhost:3000", "https://contractai-frontend.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(reviews_router)
app.include_router(billing_router)
app.include_router(admin_router)



@app.get("/")
async def root():
    return {
        "product": "ContractAI",
        "status": "running",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
