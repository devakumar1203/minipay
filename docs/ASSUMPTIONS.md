# MiniPay Design Decisions & Assumptions

This document records all architectural choices, simplifications, and domain assumptions made during the design and implementation of the **MiniPay** distributed payment system.

---

## 1. Monetary Representation & Precision
- **Integer Representation in Paise:** All monetary amounts are strictly stored and computed as signed 64-bit integers (`BigInteger` in PostgreSQL, `int` in Python/JSON) representing paise (1 INR = 100 paise).
- **No Floating-Point Arithmetic:** Floating-point numbers are strictly forbidden in any ledger, accounting, or database calculation to eliminate rounding anomalies.
- **Conversion on Client Boundary:** Frontends accept user input in INR and convert to paise immediately before transmitting. Responses display formatted INR.

---

## 2. Double-Entry Accounting & Ledger Immutability
- **Append-Only Ledger:** The `ledger_entries` table is strictly append-only. No `UPDATE` or `DELETE` statements are ever executed against it.
- **Zero-Sum per Transaction:** For every transaction, the algebraic sum of debits must equal the sum of credits.
- **Debit/Credit Sign Convention:**
  - `DEBIT` decreases an account's balance.
  - `CREDIT` increases an account's balance.
- **Counter-Accounts (`BANK_EXTERNAL`):** PayPal maintains ledger counter-accounts (`type = BANK_EXTERNAL`) for each mock bank (`bank_x`, `bank_y`). When money is pulled from a bank to a wallet, the ledger debits `BANK_EXTERNAL` and credits the user's `USER_WALLET`.

---

## 3. Distributed Sagas & Compensation
- **Orchestrated Saga Pattern:** The Payment service acts as the saga orchestrator, tracking state transitions in `saga_state`.
- **Compensation Actions:** If crediting a wallet fails after an external bank debit succeeds, the orchestrator triggers a compensating bank credit (`/credit`) to refund the customer.
- **Timeout Handling ("Do Not Guess"):** If a bank call times out or encounters network partitions, the transaction status remains `PENDING`. The orchestrator and asynchronous reconciliation jobs resolve the outcome via idempotent `/status/{reference_id}` queries rather than assuming failure.

---

## 4. Idempotency & Concurrency Control
- **Idempotency Keys:** Every state-mutating payment request requires a client-generated UUID in the `Idempotency-Key` header. Repeated submissions with the same key immediately return the stored transaction result without re-executing accounting actions.
- **Deadlock Prevention (Fixed-Order Row Locking):** In wallet-to-wallet transfers, account rows are always locked using `SELECT ... FOR UPDATE` ordered by their primary key UUIDs (`min(acc1.id, acc2.id)` first).
- **Non-Negative Balance Constraint:** Database-level `CHECK (balance >= 0)` constraints on `USER_WALLET` accounts prevent overdrafts even under high concurrency.

---

## 5. Security & Bank Tokenization
- **No Raw Bank Credentials on PayPal:** PayPal never collects, transmits, or stores user bank passwords. Bank accounts are linked via an OAuth-style consent flow where the user authenticates directly at the bank web portal.
- **Tokenized Funding Sources:** PayPal stores only opaque consent tokens and masked account numbers (`XXXX-1234`).
- **HMAC Signatures:** All inter-service calls between PayPal and the banks are cryptographically signed using HMAC-SHA256 with timestamp verification to prevent request tampering and replay attacks.
- **Immediate Block Propagation:** When an administrator blocks a user, their ID is immediately added to a Redis `blocked_users` set, invalidating active sessions across all load-balanced backend instances instantly.

---

## 6. Multi-Step Onboarding & Asynchronous Bank Linking
- **Climbing Ladder Onboarding:** MiniPay onboarding uses progressive milestone steps (`Step 1: Credentials` -> `Step 2: Personal Profile` -> `Step 3: Address Details` -> `Step 4: Bank Account Linking`). Users can resume onboarding if interrupted.
- **Asynchronous Bank Approval:** Linking a bank account does not block the user from accessing their dashboard. The link request is created in `PENDING` status, and an actionable notification is delivered to the account owner's Bank web portal.
- **Bank KYC Verification:** Bank registrations require full Indian KYC data (Full Name, Gender, Date of Birth, 12-digit Aadhaar Number, 10-character PAN Number) with uniqueness constraints to simulate real Indian banking institutions.
- **Webhooks & Instant Activation:** When the user approves a linking request inside the Bank portal, a signed webhook notifies PayPal, immediately transitioning the funding source from `PENDING` to `ACTIVE`. Wallet payments remain fully operational while bank links are pending.
- **Bank Display Naming:** Internal database identifiers `bank_x` and `bank_y` are displayed across all user interfaces as **Bank A** and **Bank B**.

