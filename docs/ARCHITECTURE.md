# MiniPay System Architecture

MiniPay is a distributed payment processing platform engineered to demonstrate core distributed systems concepts: **orchestrated sagas, idempotency, double-entry ledgers, deadlock-free concurrency control, fault tolerance, transaction outbox, and event-driven notifications**.

---

## 1. System Topology & Infrastructure

```mermaid
flowchart TD
    Client["Client Browser (React Frontends)"]
    Nginx["Nginx Reverse Proxy & Load Balancer (Port 80)"]

    subgraph PayPal Cluster
        API1["PayPal Backend Instance 1 (:8000)"]
        API2["PayPal Backend Instance 2 (:8001)"]
        PayPalDB[("PostgreSQL 16 (paypal-db)")]
        RedisDB[("Redis 7 (Cache & Idempotency)")]
        RabbitMQ["RabbitMQ 3.13 (minipay.events)"]
        NotificationWorker["Notification Async Consumer"]
    end

    subgraph External Mock Institutions
        BankX["Bank X Backend (:8010)"]
        BankXDB[("PostgreSQL 16 (bank-x-db)")]
        BankY["Bank Y Backend (:8020)"]
        BankYDB[("PostgreSQL 16 (bank-y-db)")]
    end

    Client -->|User & Admin Traffic| Nginx
    Nginx -->|Round-Robin /api/| API1
    Nginx -->|Round-Robin /api/| API2

    API1 --> PayPalDB
    API2 --> PayPalDB
    API1 --> RedisDB
    API2 --> RedisDB
    API1 --> RabbitMQ
    API2 --> RabbitMQ
    RabbitMQ --> NotificationWorker

    API1 -->|HMAC-Signed HTTP| BankX
    API1 -->|HMAC-Signed HTTP| BankY
    API2 -->|HMAC-Signed HTTP| BankX
    API2 -->|HMAC-Signed HTTP| BankY

    BankX --> BankXDB
    BankY --> BankYDB
```

---

## 2. Sequence Diagrams

### 2.1 Wallet-to-Wallet P2P Transfer (Fixed-Order Row Locking)

```mermaid
sequenceDiagram
    autonumber
    actor Sender as User A
    participant API as PayPal Backend
    participant Redis as Redis Cache
    participant DB as PostgreSQL (paypal-db)
    participant Outbox as Outbox Table

    Sender->>API: POST /api/payments/send (Idempotency-Key, source: WALLET)
    API->>Redis: Check Idempotency Key & Blocked Status
    API->>API: Rule-based Fraud Check (Velocity, Limits)
    Note over API,DB: Begin Database Transaction
    API->>DB: SELECT * FROM accounts WHERE id IN (accA, accB) ORDER BY id FOR UPDATE
    API->>DB: Verify User A Balance >= Amount
    API->>DB: INSERT INTO transactions (status='COMPLETED')
    API->>DB: INSERT INTO ledger_entries (DEBIT User A, CREDIT User B)
    API->>DB: UPDATE accounts (Balance A -= amt, Balance B += amt)
    API->>Outbox: INSERT INTO outbox (PaymentCompleted event)
    Note over API,DB: Commit Transaction
    API-->>Sender: 200 OK (Transaction COMPLETED)
```

---

### 2.2 Bank-Funded P2P Transfer (Orchestrated Saga with Compensation)

```mermaid
sequenceDiagram
    autonumber
    actor Sender as User A
    participant API as PayPal Orchestrator
    participant DB as PostgreSQL (paypal-db)
    participant Bank as Bank Backend (Bank X)
    actor Recipient as User B

    Sender->>API: POST /api/payments/send (source: FundingSource UUID)
    API->>DB: INSERT INTO transactions (status='PENDING', type='P2P_BANK')
    API->>DB: INSERT INTO saga_state (step='CREATE_TXN', status='COMPLETED')
    
    API->>Bank: POST /api/debit (reference_id=txn.id, token, amount) [Signed HMAC]
    alt Bank Debit Approved
        Bank-->>API: 200 OK {status: 'APPROVED'}
        API->>DB: INSERT INTO saga_state (step='BANK_DEBIT', status='COMPLETED')
        API->>DB: INSERT INTO ledger_entries (DEBIT BANK_EXTERNAL, CREDIT Recipient Wallet)
        API->>DB: UPDATE transactions (status='COMPLETED')
        API->>DB: INSERT INTO outbox (PaymentCompleted)
        API-->>Sender: 200 OK (Payment Completed)
    else Bank Debit Fails
        Bank-->>API: 200 OK {status: 'FAILED', reason: 'INSUFFICIENT_BALANCE'}
        API->>DB: UPDATE transactions (status='FAILED')
        API-->>Sender: 200 OK (Transaction Failed)
    else Timeout / Network Partition
        API-->>Sender: 200 OK (Transaction PENDING)
        Note over API,Bank: Reconciliation Job queries GET /api/status/{reference_id}
    end
```

---

### 2.3 Withdraw to Bank (Reserve-First Pattern)

```mermaid
sequenceDiagram
    autonumber
    actor User as User A
    participant API as PayPal Orchestrator
    participant DB as PostgreSQL (paypal-db)
    participant Bank as Bank Backend (Bank X)

    User->>API: POST /api/funding/withdraw (amount, funding_source_id)
    Note over API,DB: Step 1: Reserve Hold
    API->>DB: SELECT * FROM accounts WHERE id = wallet_id FOR UPDATE
    API->>DB: INSERT INTO transactions (status='PENDING', type='WITHDRAW')
    API->>DB: INSERT INTO ledger_entries (DEBIT wallet_id, CREDIT BANK_EXTERNAL)
    API->>DB: UPDATE accounts (wallet balance -= amount)
    
    API->>Bank: POST /api/credit (reference_id=txn.id, token, amount) [Signed HMAC]
    alt Bank Credit Approved
        Bank-->>API: 200 OK {status: 'APPROVED'}
        API->>DB: UPDATE transactions (status='COMPLETED')
        API->>DB: INSERT INTO outbox (WithdrawalCompleted)
        API-->>User: 200 OK (Withdrawal COMPLETED)
    else Bank Credit Fails
        Bank-->>API: 200 OK {status: 'FAILED'}
        Note over API,DB: Reverse Hold
        API->>DB: INSERT INTO ledger_entries (DEBIT BANK_EXTERNAL, CREDIT wallet_id)
        API->>DB: UPDATE accounts (wallet balance += amount)
        API->>DB: UPDATE transactions (status='FAILED')
        API-->>User: 200 OK (Withdrawal FAILED, Funds Refunded)
    end
```

---

### 2.4 OAuth-Style Bank Linking Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as PayPal User
    participant PayPal as PayPal Web & Backend
    participant BankWeb as Bank Web Portal
    participant BankAPI as Bank Backend

    User->>PayPal: Click "Link Bank Account" (Bank X)
    PayPal-->>User: Redirect to Bank Portal (/consent?paypal_request_id=...)
    User->>BankWeb: Log in to Bank X
    User->>BankWeb: Select Bank Account & Approve Consent
    BankWeb->>BankAPI: POST /linking/consent
    BankAPI-->>BankWeb: Return single-use authorization_code
    BankWeb-->>User: Redirect to PayPal Callback (/funding/callback?code=...)
    User->>PayPal: Submit authorization_code
    PayPal->>BankAPI: POST /api/exchange-code {code} [HMAC-Signed]
    BankAPI-->>PayPal: Return {token, masked_account: 'XXXX-4521'}
    PayPal->>PayPal: Store token in funding_sources table
    PayPal-->>User: Bank Account Successfully Linked
```

---

## 3. Data Model (Entity-Relationship Diagram)

```mermaid
erDiagram
    USERS ||--o{ ACCOUNTS : owns
    USERS ||--o{ FUNDING_SOURCES : links
    USERS ||--o{ ADMIN_ACTIONS : performs
    ACCOUNTS ||--o{ LEDGER_ENTRIES : contains
    TRANSACTIONS ||--o{ LEDGER_ENTRIES : balanced_by
    TRANSACTIONS ||--o{ SAGA_STATE : tracked_by
    TRANSACTIONS }o--|| ACCOUNTS : from_account
    TRANSACTIONS }o--|| ACCOUNTS : to_account

    USERS {
        UUID id PK
        string email UK
        string password_hash
        string role
        string status
        string blocked_reason
        datetime created_at
    }

    ACCOUNTS {
        UUID id PK
        UUID user_id FK
        string type
        string bank_id
        bigint balance
        int version
    }

    TRANSACTIONS {
        UUID id PK
        string idempotency_key UK
        string type
        string status
        bigint amount
        UUID from_account_id FK
        UUID to_account_id FK
        UUID funding_source_id FK
        datetime created_at
    }

    LEDGER_ENTRIES {
        UUID id PK
        UUID txn_id FK
        UUID account_id FK
        string direction
        bigint amount
        datetime created_at
    }

    FUNDING_SOURCES {
        UUID id PK
        UUID user_id FK
        string bank_id
        string token
        string masked_account
        bool is_default
        string status
    }

    SAGA_STATE {
        UUID id PK
        UUID txn_id FK
        string step
        string status
        string error_detail
    }
```

---

## 4. Distributed Systems Concepts Mapping

| Distributed Concept | Implementation Mechanism | Code Reference |
|---|---|---|
| **Sagas & Compensation** | Orchestrated multi-step sagas persisting step state; reverse holds and refund credits upon failure | `app/funding/service.py` |
| **Idempotency** | Header `Idempotency-Key` requirement + database UNIQUE constraints + deterministic retrieval | `app/middleware/idempotency.py`, `app/payment/service.py` |
| **Deadlock Prevention** | Total ordering / fixed-order row locking (`min(id1, id2)` locked first) with `SELECT ... FOR UPDATE` | `app/payment/service.py:100` |
| **Transactional Outbox** | Outbox table written in same DB transaction as state change; publisher pushes to RabbitMQ | `app/outbox/publisher.py` |
| **Fault Tolerance & Retries** | Tenacity exponential backoff retries on safe idempotent bank calls | `app/bank_client/client.py` |
| **Circuit Breakers** | PyBreaker fast-failure circuits per mock bank to prevent cascading exhaustion | `app/bank_client/client.py` |
| **Immediate Cache Invalidation** | Redis `blocked_users` set checked on every request across load-balanced instances | `app/auth/dependencies.py` |
| **Auditability & Double-Entry** | Append-only balanced ledger entries (`sum(debits) == sum(credits)`) | `app/wallet/service.py` |

