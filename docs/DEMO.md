# MiniPay Demo Scenarios & Verification Guide

This document provides step-by-step instructions to reproduce and verify all 11 distributed systems demo scenarios.

---

## Prerequisites
Ensure the stack is running:
```bash
docker compose up --build -d
```
Access the portals:
- **PayPal Web Application:** [http://localhost:3000](http://localhost:3000) (Admin: `admin@minipay.com` / `Admin123!`)
- **Bank X Portal:** [http://localhost:3010](http://localhost:3010)
- **Bank Y Portal:** [http://localhost:3020](http://localhost:3020)
- **RabbitMQ Management:** [http://localhost:15672](http://localhost:15672) (guest / guest)

---

## Scenario 1: Normal Wallet & Bank-Funded Transfers
1. Log in as `user1@example.com` on [http://localhost:3000](http://localhost:3000).
2. Click **Bank Accounts** &rarr; **+ Link Bank X**.
3. In Bank X portal, log in, select account, and authorize.
4. Click **Add to Wallet** &rarr; Add ₹1,000.00.
5. Go to **Send Money** &rarr; Transfer ₹200.00 to `user2@example.com` using `WALLET`.
6. Verify sender balance decreases by ₹200.00 and transaction status shows `COMPLETED`.

---

## Scenario 2: Idempotency Verification (Same Key Sent Twice)
Submit two identical HTTP requests with the exact same `Idempotency-Key` header:
```bash
TOKEN=$(curl -s -X POST http://localhost/api/auth/login -H "Content-Type: application/json" \
  -d '{"email":"admin@minipay.com","password":"Admin123!"}' | jq -r .access_token)

KEY="demo-idempotency-key-001"

# First request
curl -i -X POST http://localhost/api/payments/send \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"recipient_email":"user2@example.com","amount":5000,"source":"WALLET"}'

# Second request with SAME key
curl -i -X POST http://localhost/api/payments/send \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"recipient_email":"user2@example.com","amount":5000,"source":"WALLET"}'
```
**Outcome:** Both requests return HTTP 200 with the exact same transaction ID; the wallet balance is debited only once.

---

## Scenario 3: 50 Parallel Payments from One Wallet (No Overdraft)
Run Locust load test or parallel curl batch:
```bash
docker compose run --rm load-tests locust -f locustfile.py --headless -u 50 -r 10 --run-time 20s -H http://nginx
```
**Outcome:** Zero overdrafts occur. Final balance equals `seed_balance - (successful_transfers * amount)`. Database row-level `CHECK (balance >= 0)` and `SELECT ... FOR UPDATE` row locks preserve balance invariant.

---

## Scenario 4: Bank Down (Fail-Fast & Hold Release)
1. In Admin Panel &rarr; **Bank Chaos Controls** &rarr; Check **Bank Down (503)** on Bank X.
2. Attempt to add money or send bank-funded payment from Bank X.
**Outcome:** PyBreaker trips circuit breaker; request immediately returns clear error `Bank is temporarily unavailable`, and no orphan holds or corrupted ledger entries remain.

---

## Scenario 5: Bank Drops Response (Timeout-after-processing & Reconciliation)
1. In Bank Chaos Controls &rarr; Check **Drop Response** on Bank X.
2. Initiate Add Money from Bank X for ₹500.00.
3. Bank processes the debit in its DB, but drops the network response.
4. PayPal keeps transaction in `PENDING` status.
5. In Admin Panel &rarr; **Reconciliation** &rarr; Click **Run Reconciliation Now**.
**Outcome:** Reconciliation job queries Bank `GET /api/status/{reference_id}`, discovers it was `APPROVED`, credits the user's wallet, and marks transaction `COMPLETED`.

---

## Scenario 6: Kill Payment Service Mid-Saga (Resumption / Recovery)
1. Initiate bank-funded transfer with simulated latency.
2. Kill container: `docker compose stop paypal-backend`.
3. Start container: `docker compose start paypal-backend`.
4. Trigger reconciliation.
**Outcome:** State persisted in `saga_state` allows orchestrator to resolve or compensate the interrupted transaction safely.

---

## Scenario 7: Admin Blocks User (Immediate Multi-Instance Propagation)
1. User logs in on Instance 1 and obtains a JWT token.
2. Admin goes to **Admin Panel** &rarr; **Users** &rarr; Blocks the user with reason "Fraud investigation".
3. Immediately send a request using the existing JWT token to Instance 2.
**Outcome:** Redis `blocked_users` check rejects the request instantly with HTTP 403 `Account is blocked` across all instances without waiting for JWT expiration.

---

## Scenario 8: Fraud Rule & Manual Review Queue
1. Attempt a transfer exceeding ₹50,000 (e.g., ₹60,000.00 / 6,000,000 paise).
2. Transaction is flagged by rule engine and placed in `UNDER_REVIEW`. No money moves.
3. Admin navigates to **Admin Panel** &rarr; **Fraud Review Queue**.
4. Admin clicks **Approve** (funds move, ledger balanced) or **Reject** (marked `FAILED`).

---

## Scenario 9: Admin Reverses Completed P2P Transaction
1. Execute a P2P transfer of ₹300.00 from User A to User B.
2. In Admin Panel &rarr; **Transactions & Reversals** &rarr; Click **Reverse P2P**.
3. Provide mandatory reason: "Duplicate payment dispute resolved".
**Outcome:** New compensating ledger entries are appended (`DEBIT User B`, `CREDIT User A`), reversing funds without altering historical records.

---

## Scenario 10: Brute-Force Lockout & Velocity Counter
1. Send 5 consecutive failed login attempts with wrong password.
2. 6th attempt is locked out with HTTP 403 `Account temporarily locked`.
3. Admin clicks **Unlock Lockout** on User Detail page to clear counter.

---

## Scenario 11: Ledger Audit & Zero Discrepancies
1. Perform various transfers, withdrawals, and reversals.
2. In Admin Panel &rarr; **Reconciliation** &rarr; Click **Run Reconciliation Now**.
**Outcome:** Discrepancy report verifies:
- `sum(DEBIT) == sum(CREDIT)` for all transactions.
- Every wallet balance matches `sum(CREDIT) - sum(DEBIT)` from ledger records.

