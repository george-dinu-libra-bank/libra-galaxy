# Banking Application Architecture Guide

## 1. Purpose

This document defines the target architecture and development rules for the banking application.

Claude/code agents working in this repository MUST treat this document as an architectural source of truth unless a newer explicit architectural decision overrides it.

The architecture is based on:

- **Next.js** for the frontend and user-facing application.
- **Supabase** for PostgreSQL, authentication, storage and related platform services.
- **Supabase SDK** for approved direct communication with Supabase.
- **FastAPI** as the Python API layer exposed to the frontend.
- **Python AI agents** for reasoning/orchestration tasks.
- A **Data Access / Repository layer** between Python business logic/agents and Supabase.

The main goal is to keep responsibilities separated, security boundaries explicit, and AI agents independent from the physical database schema.

---

## 2. High-Level Architecture

```text
                         USER
                           |
                           v
                    +--------------+
                    |   Next.js    |
                    |   Frontend   |
                    +------+-------+
                           |
              +------------+-------------+
              |                          |
              v                          v
       Supabase SDK                 FastAPI API
       simple/user-scoped             |
       operations                     v
                              +----------------+
                              |   Services     |
                              | Business Logic |
                              +-------+--------+
                                      |
                         +------------+-------------+
                         |                          |
                         v                          v
                 +---------------+        +----------------+
                 |   AI Agents   |        | Business Logic |
                 |    Python     |        |    Services    |
                 +-------+-------+        +--------+-------+
                         |                         |
                         +------------+------------+
                                      |
                                      v
                               +--------------+
                               |  Tool Layer  |
                               +------+-------+
                                      |
                                      v
                             +------------------+
                             | Repositories /   |
                             | Data Access Layer|
                             +--------+---------+
                                      |
                                      v
                              +---------------+
                              |    Supabase   |
                              | PostgreSQL    |
                              +---------------+
```

### Core principle

There are two legitimate paths from Next.js to backend data:

1. **Next.js -> Supabase SDK -> Supabase/PostgreSQL** for simple, user-scoped operations where direct client access is appropriate and protected by Supabase Auth + RLS.
2. **Next.js -> FastAPI -> Service/Agent -> Tool/Repository -> Supabase/PostgreSQL** for business logic, sensitive operations, AI workflows, orchestration, multi-step operations and privileged actions.

Do NOT force every operation through FastAPI if direct Supabase access is appropriate.
Do NOT put complex business logic in the Next.js client.
Do NOT let AI agents access the database arbitrarily.

---

## 3. Component Responsibilities

## 3.1 Next.js

Next.js is responsible for:

- UI and UX.
- Client-side interaction.
- Rendering user-facing data.
- Calling FastAPI endpoints for backend capabilities.
- Using the official Supabase SDK for approved direct Supabase operations.
- Managing loading/error/success states.
- Never embedding privileged backend credentials.

Next.js SHOULD NOT:

- Execute banking business rules.
- Perform privileged database operations.
- Contain database secrets.
- Decide authorization rules by itself.
- Execute arbitrary SQL.
- Implement AI reasoning logic.

---

## 3.2 Supabase

Supabase provides:

- PostgreSQL database.
- Authentication.
- Row Level Security (RLS).
- Storage where required.
- Realtime functionality where required.
- Data APIs / SDK access.

Supabase is the system of record for persistent application data.

The database should enforce data ownership and access constraints wherever practical, especially through RLS.

---

## 3.3 Supabase SDK

The Supabase SDK is the application library used to communicate with Supabase.

Use the official SDKs:

- JavaScript/TypeScript SDK in Next.js.
- Python SDK (`supabase-py`) in the Python backend when that access pattern is chosen.

The SDK is a communication mechanism. It is NOT a business-logic layer.

Examples of direct access from Next.js:

```ts
const { data, error } = await supabase
  .from("accounts")
  .select("id, currency, balance");
```

Direct frontend access MUST remain protected by Supabase Auth and RLS.

---

## 3.4 FastAPI

FastAPI is the public application API for Python capabilities.

FastAPI is responsible for:

- HTTP API endpoints.
- Request validation.
- Authentication/context propagation.
- Authorization checks where required.
- Calling application services.
- Calling AI agents.
- Returning stable API responses to Next.js.
- Error handling.
- Observability/logging at the API boundary.

FastAPI SHOULD NOT contain large amounts of business logic directly inside route handlers.

Prefer:

```text
Route -> Service -> Repository/Tool -> Data Source
```

Instead of:

```text
Route -> 100 lines of business logic -> database
```

---

## 3.5 Python AI Agents

AI agents are responsible for reasoning, orchestration and deciding which approved tools/functions they need.

An agent MUST NOT be treated as a database administrator.

Agents SHOULD:

- Receive a well-defined user context.
- Receive only the capabilities/tools they need.
- Call approved tools.
- Reason over returned data.
- Produce structured outputs where possible.
- Avoid direct arbitrary SQL.

Agents SHOULD NOT:

- Receive unrestricted database credentials.
- Invent table names or SQL queries.
- Decide which user they are allowed to access.
- Bypass authorization.
- Mutate financial state directly unless the operation is explicitly exposed as a secured tool/service.

The agent decides **what information or action it needs**.
The application decides **how that information/action is obtained and whether it is allowed**.

---

## 3.6 Tool Layer

AI agents should interact with application capabilities through explicit tools/functions.

Examples:

```text
get_account_balance(user_id)
get_recent_transactions(user_id, start_date, end_date)
get_transaction_details(user_id, transaction_id)
get_recurring_payments(user_id)
get_savings_goals(user_id)
get_card_status(user_id, card_id)
get_monthly_cashflow(user_id, month)
```

Tools provide a controlled interface between agent reasoning and backend data/business logic.

A tool MUST:

- Validate input.
- Enforce user/tenant context.
- Call the appropriate service/repository.
- Return structured data.
- Avoid exposing unnecessary fields.

---

## 3.7 Services / Business Logic Layer

Services contain application business rules.

Examples:

```text
TransferService
CardService
AccountService
SavingsService
TransactionService
SpendingAnalysisService
```

Services are the preferred place for logic such as:

- Transfer validation.
- Limit checks.
- Eligibility checks.
- Multi-step operations.
- Idempotency rules.
- Financial state transitions.
- Calling multiple repositories.
- Triggering external integrations.

For financially sensitive operations, services MUST be treated as critical control points.

---

## 3.8 Repository / Data Access Layer

Repositories encapsulate database access.

Examples:

```text
AccountRepository
TransactionRepository
CardRepository
UserRepository
SavingsRepository
```

Repositories know HOW to retrieve/store data.
They should NOT decide business policy.

Example:

```python
async def get_recent_transactions(
    user_id: str,
    start_date: datetime,
    end_date: datetime,
):
    ...
```

The agent should call the application capability, not write database-specific queries itself.

This abstraction also allows the underlying implementation to evolve from `supabase-py` toward another PostgreSQL access strategy such as SQLAlchemy/asyncpg without rewriting the agents.

---

# 4. Data Access Model

## 4.1 Simple User-Scoped Reads

For simple UI data that is safe and appropriate to expose directly:

```text
Next.js
  |
  v
Supabase JS SDK
  |
  v
Supabase
  |
  v
PostgreSQL
```

Examples may include:

- Current user's profile.
- Current user's account list.
- User-owned transaction list.
- User-owned savings goals.

These operations MUST be protected by Supabase Auth and RLS.

---

## 4.2 Complex / Sensitive Operations

For business logic, privileged operations, AI workflows and multi-step operations:

```text
Next.js
  |
  v
FastAPI
  |
  v
Service / Agent
  |
  v
Tool
  |
  v
Repository
  |
  v
Supabase/PostgreSQL
```

Examples:

- Creating a transfer.
- Freezing/unfreezing a card when additional rules apply.
- Fraud checks.
- Complex financial analysis.
- AI-generated financial insights.
- Operations involving multiple accounts/tables.
- Operations requiring external services.

---

# 5. Authentication and Authorization

Authentication and authorization MUST remain separate concepts.

Authentication answers:

> Who is this user?

Authorization answers:

> What is this user allowed to access or do?

Supabase Auth is the primary authentication mechanism unless explicitly replaced by a new architectural decision.

The authenticated user identity MUST be propagated through the request context into FastAPI/services/tools as appropriate.

Never allow an AI agent to choose an arbitrary `user_id` supplied by natural-language input.

The trusted backend context must determine the user identity.

---

## 5.1 Row Level Security (RLS)

RLS is a critical security layer in Supabase.

For user-owned tables, enforce policies such as:

```text
User A -> can see rows belonging to User A
User B -> can see rows belonging to User B
```

Do not rely exclusively on frontend checks for authorization.

Frontend checks improve UX; database/backend checks provide security.

---

# 6. Supabase Keys and Secrets

## Frontend

Only browser-safe Supabase credentials may be exposed to Next.js client code.

Typical pattern:

```text
SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY / publishable key
```

## Backend

Privileged Supabase credentials belong ONLY in trusted server environments such as FastAPI.

Never expose secret/service credentials to:

- Browser bundles.
- Client-side JavaScript.
- Public environment variables.
- AI model prompts.
- Agent-visible configuration.
- Git repositories.

Treat privileged Supabase credentials as production secrets.

---

# 7. AI Agent Data Access Rules

The preferred pattern is:

```text
User Question
    |
    v
FastAPI
    |
    v
Agent
    |
    | decides which capability is needed
    v
Tool
    |
    v
Service
    |
    v
Repository
    |
    v
Supabase/PostgreSQL
```

NOT:

```text
User Question
    |
    v
Agent
    |
    v
Arbitrary SQL
    |
    v
Database
```

The second pattern MUST NOT be used for unrestricted production access.

---

# 8. Prefer Domain Tools Over Raw Database Access

Instead of exposing:

```text
run_sql(query)
```

prefer:

```text
get_recent_transactions()
get_monthly_spending()
get_cashflow_summary()
get_recurring_payments()
get_savings_goals()
```

Why:

1. Better security.
2. Better authorization.
3. Easier testing.
4. Easier observability.
5. Easier prompt/tool design.
6. Less coupling between agents and DB schema.
7. Easier schema migrations.
8. Easier to reason about financial side effects.

---

# 9. Read Models for AI

AI agents should not always receive raw transaction tables.

For analytical use cases, create optimized read models/views or service-level aggregations such as:

```text
monthly_cashflow
user_spending_summary
recurring_payments
financial_profile
category_spending_summary
```

Example response:

```json
{
  "income": 8500,
  "expenses": 4200,
  "savings": 1800,
  "available": 2500
}
```

This is preferable to sending hundreds of raw transactions to an LLM when a concise aggregate can answer the question.

---

# 10. Financial Mutation Rules

Financial state changes require stricter controls than reads.

Examples:

- Transfer money.
- Freeze a card.
- Unfreeze a card.
- Create/cancel a scheduled transfer.
- Create/close an account.
- Change sensitive account settings.

These actions MUST NOT be performed by the LLM directly.

The LLM may request an approved action tool, but the service must:

1. Authenticate the user.
2. Authorize the action.
3. Validate all parameters.
4. Validate balance/limits/state.
5. Enforce idempotency where relevant.
6. Execute the state change transactionally where required.
7. Record an audit event.
8. Return a structured result.

Example:

```text
Agent:
  "I need to transfer 500 RON to beneficiary X."

Tool:
  create_transfer(user_id, beneficiary_id, amount)

TransferService:
  validate -> authorize -> execute -> audit
```

The agent does not directly update `accounts.balance`.

---

# 11. Transaction and Consistency Guidance

For operations that modify multiple financial records, use database transactions or another guaranteed atomic mechanism appropriate to the chosen implementation.

Avoid sequences such as:

```text
UPDATE balance
INSERT transaction
UPDATE transfer
```

without ensuring atomicity.

For financial mutations, partial completion is dangerous.

The implementation must prevent states such as:

- money deducted but transaction not recorded;
- transaction recorded but balance not updated;
- duplicated transfer caused by retry.

Idempotency keys should be considered for externally triggered financial mutations.

---

# 12. API Design Rules

FastAPI endpoints should be domain-oriented and stable.

Preferred:

```text
POST /api/transfers
GET  /api/accounts
GET  /api/transactions
POST /api/agents/chat
POST /api/agents/spending-analysis
POST /api/cards/{card_id}/freeze
```

Avoid exposing internal implementation details such as:

```text
POST /api/run-sql
POST /api/repository/query
```

Use request/response schemas with Pydantic.

Responses should be structured and predictable.

---

# 13. Suggested Python Project Structure

```text
backend/
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── routes/
│   │   │   ├── accounts.py
│   │   │   ├── transactions.py
│   │   │   ├── transfers.py
│   │   │   ├── cards.py
│   │   │   └── agents.py
│   │   │
│   │   └── dependencies.py
│   │
│   ├── agents/
│   │   ├── spending_agent.py
│   │   ├── savings_agent.py
│   │   └── fraud_agent.py
│   │
│   ├── tools/
│   │   ├── transaction_tools.py
│   │   ├── account_tools.py
│   │   └── savings_tools.py
│   │
│   ├── services/
│   │   ├── account_service.py
│   │   ├── transaction_service.py
│   │   ├── transfer_service.py
│   │   ├── card_service.py
│   │   └── spending_service.py
│   │
│   ├── repositories/
│   │   ├── account_repository.py
│   │   ├── transaction_repository.py
│   │   ├── card_repository.py
│   │   └── user_repository.py
│   │
│   ├── infrastructure/
│   │   ├── supabase.py
│   │   ├── logging.py
│   │   └── config.py
│   │
│   └── schemas/
│       ├── accounts.py
│       ├── transactions.py
│       ├── transfers.py
│       └── agents.py
│
└── tests/
```

The exact structure may evolve, but separation of concerns should remain.

---

# 14. Recommended Development Rules for Claude

When implementing a feature, Claude/code agents should follow this decision process:

### Step 1 — Identify the feature type

Ask:

- Is this simple user-scoped data retrieval?
- Is it business logic?
- Is it a financial mutation?
- Is it an AI/agent workflow?

### Step 2 — Choose the correct path

Simple user-scoped read:

```text
Next.js -> Supabase SDK
```

Business logic / sensitive operation:

```text
Next.js -> FastAPI -> Service -> Repository -> Supabase
```

AI feature:

```text
Next.js -> FastAPI -> Agent -> Tool -> Service/Repository -> Supabase
```

### Step 3 — Preserve security boundaries

Never move privileged secrets into the frontend.
Never allow an LLM to choose arbitrary user identity.
Never expose unrestricted SQL tools to production agents.
Never bypass RLS casually.

### Step 4 — Keep layers decoupled

Frontend should not know database implementation details.
Agents should not know database schema details.
Repositories should not contain business policy.
Routes should not contain large business workflows.

---

# 15. Example End-to-End Agent Flow

User asks:

> "How much did I spend on food in the last three months?"

Flow:

```text
Next.js
  |
  | POST /api/agents/chat
  v
FastAPI
  |
  | authenticate + establish trusted user context
  v
SpendingAgent
  |
  | chooses tool
  v
get_category_spending(user_id, category="food", period="3m")
  |
  v
SpendingService
  |
  v
Repository
  |
  v
Supabase/PostgreSQL
  |
  v
Aggregated result
  |
  v
SpendingAgent
  |
  v
Structured answer
  |
  v
FastAPI
  |
  v
Next.js
```

Example final structured result:

```json
{
  "category": "food",
  "period": "last_3_months",
  "total": 4320,
  "currency": "RON",
  "average_monthly": 1440
}
```

The frontend decides how to present the result.

---

# 16. Example Direct Supabase Flow

User opens the account page.

The page needs the authenticated user's accounts.

```text
Next.js
  |
  v
Supabase JS SDK
  |
  v
Supabase Auth / RLS
  |
  v
PostgreSQL
  |
  v
User-owned accounts
```

This is appropriate when no complex backend computation is required.

---

# 17. Example Transfer Flow

User requests a transfer of 500 RON.

```text
Next.js
  |
  | POST /api/transfers
  v
FastAPI
  |
  v
TransferService
  |
  +--> validate authentication
  +--> validate beneficiary
  +--> validate balance
  +--> validate limits
  +--> validate idempotency
  +--> execute transaction
  +--> write audit event
  |
  v
Repository
  |
  v
Supabase/PostgreSQL
  |
  v
Result
  |
  v
FastAPI
  |
  v
Next.js
```

The AI agent, if involved, may request a transfer action, but the actual execution remains inside the secured service layer.

---

# 18. Observability and Auditability

Because this is a banking application, important backend actions should be observable.

At minimum, design for:

- request IDs;
- structured logs;
- error tracking;
- agent/tool invocation logs where appropriate;
- audit events for sensitive mutations;
- correlation between frontend request, FastAPI request and downstream operation.

Avoid logging:

- passwords;
- access tokens;
- secret keys;
- full card numbers;
- unnecessary personal/financial data.

---

# 19. Recommended Initial Technology Choice

For the first implementation phase, the recommended stack is:

```text
Frontend:
  Next.js + TypeScript
  @supabase/ssr / official Supabase JS tooling

Backend:
  Python + FastAPI
  Pydantic

Agent layer:
  Python agent framework/library selected by the team
  Explicit tools

Data layer:
  Supabase PostgreSQL
  supabase-py initially for Python access

Security:
  Supabase Auth
  RLS
  server-side secret management
```

The Python Data Access Layer should be designed so that `supabase-py` can later be replaced or supplemented by SQLAlchemy/asyncpg/another PostgreSQL access strategy without changing agent contracts.

---

# 20. Non-Negotiable Architectural Principles

1. **Frontend is not the source of truth for authorization.**
2. **Agents do not get unrestricted database access.**
3. **Financial mutations go through explicit backend services.**
4. **RLS remains an important database security layer.**
5. **Privileged Supabase keys never reach the browser or model context.**
6. **Agents use tools, not arbitrary SQL.**
7. **Repositories encapsulate database access.**
8. **Services contain business rules.**
9. **FastAPI routes stay thin.**
10. **Next.js remains focused on presentation and client experience.**
11. **AI should operate on purpose-built data/read models where possible.**
12. **Financial operations must be designed for atomicity, idempotency and auditability.**

---

# 21. Architecture Decision Summary

The preferred mental model is:

```text
Next.js
  |
  +--> Supabase SDK
  |      |
  |      +--> simple authenticated user-scoped data
  |
  +--> FastAPI
         |
         +--> Services
         |
         +--> AI Agents
                |
                +--> Tools
                       |
                       +--> Repositories
                              |
                              +--> Supabase/PostgreSQL
```

The key architectural idea is:

> **Next.js handles the experience, FastAPI handles backend capabilities and orchestration, services handle business rules, agents handle reasoning, tools expose controlled capabilities, repositories handle data access, and Supabase/PostgreSQL stores the source-of-truth data.**

When in doubt, preserve these boundaries rather than taking the shortest possible implementation path.
