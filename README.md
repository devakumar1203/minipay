# MiniPay — Distributed Payment System

MiniPay is a distributed payment processing platform built for university Distributed Systems courses to demonstrate **sagas, idempotency, concurrency control, double-entry accounting, fault tolerance, transaction outbox, and event-driven notifications**.

---

## Tech Stack
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (Async), PostgreSQL 16, Redis 7, RabbitMQ 3.13 (aio-pika), httpx, tenacity, pybreaker, APScheduler.
- **Frontend:** React 18, Vite, TypeScript, Tailwind CSS, Lucide Icons.
- **Infrastructure:** Docker Compose, Nginx (Reverse Proxy & Load Balancer for 2+ Payment instances).
- **Testing & Benchmarks:** pytest, pytest-asyncio, Locust.

---

## Quick Start

### 1. Start the Complete Stack
```bash
docker compose up --build -d
```

### 2. Service Access URLs
| Service | URL | Default Credentials |
|---|---|---|
| **PayPal Web & Admin** | [http://localhost:3000](http://localhost:3000) | `admin@minipay.com` / `Admin123!` |
| **Bank X Portal** | [http://localhost:3010](http://localhost:3010) | Register any email (Seed: ₹10,000) |
| **Bank Y Portal** | [http://localhost:3020](http://localhost:3020) | Register any email (Seed: ₹10,000) |
| **RabbitMQ Dashboard** | [http://localhost:15672](http://localhost:15672) | `guest` / `guest` |
| **Load Balanced API** | [http://localhost/api/](http://localhost/api/) | Via Nginx proxy |

---

## Key Features

1. **P2P Payments:**
   - **Wallet-to-Wallet:** Deadlock-free fixed-order row locking (`SELECT ... FOR UPDATE`), zero-sum double-entry ledger entries.
   - **Bank-Funded P2P:** Multi-step orchestrated saga with state persistence and compensating refunds.

2. **Add Money & Withdraw:**
   - **Add Money:** Bank debit followed by wallet credit.
   - **Withdraw:** Reserve-first pattern holding wallet funds before crediting the bank.

3. **OAuth-Style Bank Linking:**
   - Cryptographically signed HMAC-SHA256 handshake.
   - PayPal never sees bank credentials; stores only opaque consent tokens.

4. **Fault Tolerance & Chaos Simulation:**
   - Bank circuit breakers (PyBreaker) and exponential retries (Tenacity).
   - Injected latency, error probability, response drop, and bank downtime controls.
   - Reconciliation job resolves timeout transactions via `/status/{reference_id}` queries.

5. **Security & Administration:**
   - Instant multi-instance user blocking via Redis.
   - Configurable rule-based fraud engine with manual review queue.
   - P2P payment reversal via append-only compensating ledger entries.
   - Immutable audit logging.

---

## Documentation
- [System Architecture & Sequence Diagrams](docs/ARCHITECTURE.md)
- [Demo Scenarios & Verification Guide](docs/DEMO.md)
- [Design Assumptions & Decisions](docs/ASSUMPTIONS.md)

---

## Running Automated Tests
```bash
docker compose exec paypal-backend pytest
```

