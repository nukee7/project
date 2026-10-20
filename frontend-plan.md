# Frontend Plan

**Stack:** Plain HTML + CSS + vanilla JS (no React, no build step)
**Served from:** FastAPI static files on the Portfolio Agent (port 8001)

---

## Pages

### Page 1: `/` — Sign In / Sign Up

Single page with two forms (toggle between them).

```
┌──────────────────────────────────────┐
│         Portfolio Research            │
│                                      │
│  ┌─ Sign In ─────────────────────┐   │
│  │  Email:    [_______________]  │   │
│  │  Password: [_______________]  │   │
│  │                               │   │
│  │  [ Sign In ]                  │   │
│  │                               │   │
│  │  Don't have an account?       │   │
│  │  → Sign Up                    │   │
│  └───────────────────────────────┘   │
│                                      │
│  (or toggled to Sign Up form)        │
│  ┌─ Sign Up ─────────────────────┐   │
│  │  Name:     [_______________]  │   │
│  │  Email:    [_______________]  │   │
│  │  Password: [_______________]  │   │
│  │                               │   │
│  │  [ Sign Up ]                  │   │
│  │                               │   │
│  │  Already have an account?     │   │
│  │  → Sign In                    │   │
│  └───────────────────────────────┘   │
└──────────────────────────────────────┘
```

**API calls:**
- Sign Up → `POST /auth/signup` → gets JWT token → stores in localStorage → redirects to `/portfolio`
- Sign In → `POST /auth/signin` → gets JWT token → stores in localStorage → redirects to `/portfolio`

**On load:** Check localStorage for token. If valid, redirect to `/portfolio`.

---

### Page 2: `/portfolio` — Portfolio + Chat

Two sections side by side (or stacked on mobile).

```
┌─────────────────────────────────────────────────────────────┐
│  Portfolio Research                          [Refresh] [Out] │
├──────────────────────────┬──────────────────────────────────┤
│                          │                                  │
│  MY PORTFOLIO            │  ASK ABOUT YOUR PORTFOLIO        │
│                          │                                  │
│  Total: ₹5,72,250       │  ┌────────────────────────────┐  │
│  Current: ₹4,85,000     │  │                            │  │
│  P&L: -₹87,250 (-15%)   │  │  Chat messages appear here │  │
│                          │  │                            │  │
│  ┌──────────────────┐   │  │  User: What are my top     │  │
│  │ RELIANCE    28%  │   │  │        holdings?            │  │
│  │ ₹2,450 → ₹1,202 │   │  │                            │  │
│  │ 50 qty  -51%     │   │  │  Agent: Your largest        │  │
│  ├──────────────────┤   │  │  holding is HDFC Bank at    │  │
│  │ TCS         22%  │   │  │  28% of portfolio...        │  │
│  │ ₹3,500 → ₹2,461 │   │  │                            │  │
│  │ 30 qty  -30%     │   │  │                            │  │
│  ├──────────────────┤   │  │                            │  │
│  │ HDFCBANK    28%  │   │  │                            │  │
│  │ ₹1,600 → ₹1,610 │   │  └────────────────────────────┘  │
│  │ 100 qty   +1%    │   │                                  │
│  ├──────────────────┤   │  ┌──────────────────────┐ [Send] │
│  │ ...              │   │  │ Ask a question...    │        │
│  └──────────────────┘   │  └──────────────────────┘        │
│                          │                                  │
│  [ + Add Position ]      │  Suggested:                      │
│                          │  • What are my top holdings?     │
│                          │  • Am I concentrated?            │
│                          │  • Tell me about Reliance        │
├──────────────────────────┴──────────────────────────────────┤
│  Add Position (expandable form)                             │
│  Ticker [____] Name [__________] Qty [___] Price [___]      │
│  Sector [____] Exchange [BSE▾]                  [ Add ]     │
└─────────────────────────────────────────────────────────────┘
```

**Left section — Portfolio:**
- On load → `GET /portfolio` (with Bearer token) → display positions
- Refresh button → `POST /portfolio/refresh-prices` → then `GET /portfolio`
- Add position form → `POST /portfolio/positions`
- Delete position → `DELETE /portfolio/positions/{id}`

**Right section — Chat:**
- User types question → `POST /query` with `{"question": "..."}` (with Bearer token)
- Response displayed as a chat message (answer + key findings)
- Suggested questions shown below input

**Logout:** Clear localStorage token → redirect to `/`

---

## API Routes Used

| Page | Action | Method | Endpoint | Auth? |
|------|--------|--------|----------|-------|
| `/` | Sign up | POST | `/auth/signup` | No |
| `/` | Sign in | POST | `/auth/signin` | No |
| `/portfolio` | View portfolio | GET | `/portfolio` | Yes |
| `/portfolio` | List positions | GET | `/portfolio/positions` | Yes |
| `/portfolio` | Add position | POST | `/portfolio/positions` | Yes |
| `/portfolio` | Delete position | DELETE | `/portfolio/positions/{id}` | Yes |
| `/portfolio` | Update position | PUT | `/portfolio/positions/{id}` | Yes |
| `/portfolio` | Refresh prices | POST | `/portfolio/refresh-prices` | Yes |
| `/portfolio` | Ask question | POST | `/query` | Yes |
| `/portfolio` | Health check | GET | `/health` | No |

---

## Files

```
portfolio-agent/
└── static/
    ├── index.html          ← Sign in / Sign up page (served at /)
    ├── portfolio.html      ← Portfolio + Chat page (served at /portfolio)
    ├── style.css           ← Shared styles
    └── app.js              ← All JS (auth, portfolio CRUD, chat, API calls)
```

**4 files total. No build step. No npm. No framework.**

---

## Auth Flow

```
Sign Up/In → API returns {token, user_id, name}
          → JS stores token in localStorage
          → Redirect to /portfolio

/portfolio loads → JS reads token from localStorage
               → If no token → redirect to /
               → If token → GET /portfolio with Authorization: Bearer {token}
               → If 401 → token expired → redirect to /

Logout → JS clears localStorage → redirect to /
```
