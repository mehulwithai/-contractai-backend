# ContractAI — Backend

AI-powered contract review for founders and SMBs. Built with FastAPI + Supabase + Claude API.

## Stack
- **FastAPI** — Python backend
- **Supabase** — Auth, database, file storage
- **Anthropic Claude** — AI contract analysis
- **Stripe** — Payments

---

## Day 1 Setup (do this now)

### 1. Clone and install
```bash
cd contractai
pip install -r requirements.txt
```

### 2. Create your .env file
```bash
cp .env.example .env
```
Fill in each value (instructions below).

### 3. Get your API keys

**Anthropic:**
- Go to https://console.anthropic.com
- Create an API key
- Paste into `ANTHROPIC_API_KEY`

**Supabase:**
- Go to https://supabase.com → New project
- Settings → API → copy `Project URL` into `SUPABASE_URL`
- Settings → API → copy `service_role` key into `SUPABASE_SERVICE_KEY`
- Run `supabase_schema.sql` in the SQL editor (Database → SQL Editor)
- Enable Email auth: Authentication → Providers → Email

**Stripe (Week 3 — skip for now):**
- https://dashboard.stripe.com
- Create a product ($49/month recurring)
- Copy the Price ID into `STRIPE_PRICE_ID`

### 4. Run the server
```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Test it's working
Open http://localhost:8000 — you should see:
```json
{"product": "ContractAI", "status": "running"}
```

Open http://localhost:8000/docs for the interactive API explorer.

---

## Project structure
```
contractai/
├── app/
│   ├── main.py              # FastAPI app + CORS
│   ├── api/
│   │   ├── reviews.py       # Upload + analyse endpoints
│   │   └── billing.py       # Stripe checkout + webhook
│   ├── core/
│   │   ├── config.py        # All env vars
│   │   ├── auth.py          # Supabase JWT verification
│   │   └── models.py        # Pydantic schemas
│   └── services/
│       ├── parser.py        # PDF/DOCX text extraction
│       └── analyzer.py      # Claude AI analysis
├── supabase_schema.sql      # Run in Supabase SQL editor
├── .env.example             # Copy to .env and fill in
└── README.md
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | / | Health check |
| GET | /docs | Interactive API docs |
| POST | /api/reviews/ | Upload + analyse a contract |
| GET | /api/reviews/ | List all reviews for user |
| GET | /api/reviews/{id} | Get a single review |
| DELETE | /api/reviews/{id} | Delete a review |
| POST | /api/billing/checkout | Create Stripe checkout session |
| POST | /api/billing/webhook | Stripe webhook handler |
| GET | /api/billing/status | Check subscription status |

## Day-by-day build plan

- **Day 1** ✅ Project setup (you are here)
- **Day 2** — Test parser.py on real contracts
- **Day 3** — Refine the Claude prompt in analyzer.py
- **Day 4** — Wire up all API endpoints end-to-end
- **Day 5** — Supabase auth + database schema
- **Day 6-7** — Full pipeline test, bug fixes
- **Day 8+** — Next.js frontend
