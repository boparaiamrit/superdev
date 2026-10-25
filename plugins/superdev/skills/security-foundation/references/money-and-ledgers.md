# Money, credits and ledgers

Applies to anything with a balance: credits, wallets, stock, seats, quotas.

## Model: lots + append-only ledger

```
credit_lots     id, account_id, pool, activity, description, credits_added, credits_left, expires_on, order_id?, report_id?
credit_ledger   id, account_id, activity, pool, delta (+/-), lot_id, unlock_id?, order_id?, description,
                balance_after (per pool), admin_user_id? (manual adjustments), created_at
```

- Balance = sum of `credits_left` on unexpired lots. Spend from the soonest-expiring lot first (tie rule stated, e.g. gift before plan).
- Every movement writes one ledger row per lot touched. Rows are never updated or deleted.
- Manual adjustments are their own activities (`Admin Credit`, `Admin Debit`) and record the staff member; credits need an expiry date; debits never take more than the account has.

## Serialize every balance change per account

Take a transaction-scoped lock on the account **first**, in every path that changes a balance — spend, grant, debit, expiry, refund:

```ts
async lock(tx: Tx, accountId: string) {
  await tx.execute(sql`SELECT pg_advisory_xact_lock(hashtext('wallet'), hashtext(${accountId}))`);
}
```

Why not `SELECT … ORDER BY expires_on LIMIT 1 FOR UPDATE` alone: when a parallel transaction empties that lot while you wait, Postgres re-checks the row, finds it no longer matches, and returns **no row** — your spend fails with "no balance" although another lot has credits. The advisory lock serializes the whole decision. It is re-entrant inside one transaction, so the grant/spend/debit helpers can each take it.

When one transaction touches several accounts (a referral reward credits the referrer while the buyer's plan activates), take the locks in a **fixed order** (sort the ids) to avoid deadlocks.

When a spend also changes a shared item with its own limit (a lead that at most N buyers may unlock, the last seats of an event), lock the **item row first** (`SELECT … FOR UPDATE` by id, then check its counter against the limit), **then** the account lock — and use that same order in every path that touches both. Increment the item's counter in the same transaction as the charge.

## Idempotency

Clients send `Idempotency-Key: <uuid per user action>` on money-moving and record-creating requests (unlock, create order, pay, record payment, cancel, adjust credits, create/import records, resolve with refund). The server:

1. claims `idem:<principal>:<method>:<route>:<params>:<key>` in Redis with `SET NX EX 86400` → runs the handler → stores `{ hash(body+query), status, body }`;
2. on a repeat: same hash → replay the stored response with `Idempotent-Replayed: true`; still running → 409 `IDEMPOTENCY_IN_PROGRESS`; different body → 422 `IDEMPOTENCY_KEY_REUSED`;
3. on handler error → delete the claim so a corrected retry can run.

Register the interceptor outermost so a replay is not audited twice. Natural idempotency (status checks under `FOR UPDATE`, unique indexes) stays as a second layer.

The stored response may contain personal data (an unlock returns the contact it revealed). Keep the idempotency store private (not a Redis shared with other apps), TTL ≤ 24 h, never logged — or, for such routes, store the resulting record id and re-read it on replay instead of the body.

## Payments

- The gateway confirmation is server-signed and amount-checked; activation runs once under a row lock on the order (`Pending` → `Paid`), and a second callback is a no-op.
- **Re-validate discounts at payment time.** A pending order keeps the price it was quoted; before money is taken, check the coupon again (expired, switched off, used up by others since). If invalid, cancel the order and tell the buyer — never charge an invalid discount.
- Offline payments recorded by staff go through the **same** activation function as gateway payments.
- **Entitlements derived from a purchase expire with it.** A flag set by buying a tier (priority access, a badge) is cleared by a scheduled job when the plan ends and no other qualifying plan is active — without clobbering flags staff set by hand for others.

## Reconciliation — prove the books

A service that runs a set of SQL invariants and returns failing rows, used nightly (alert staff if anything Critical fails) and on demand from the admin. Typical rules:

- each lot: `credits_added` minus every debit row equals `credits_left`; exactly one positive row per lot;
- no lot below zero or above what it was granted;
- every spend has exactly one charge row of −1 from the pool it records, and no charge exists without its spend;
- counters (e.g. "unlocks on a lead") equal the rows they count and never exceed their limit;
- every paid order activated exactly once with the promised quantity; no unpaid order granted anything;
- rewards and refunds paid exactly once and only for a qualifying source;
- every manual adjustment names a staff member;
- coupon counters are not behind the paid orders using them;
- expired lots were zeroed by the expiry job.

The demo seed must satisfy every rule — link seeded rewards to seeded orders and seed counters consistently, or the check is noise from day one.

## Proof (committed tests)

Exact balance N with N+k parallel spends → exactly N succeed, k get "no balance", balance 0, never negative. Spends across several lots in parallel → all succeed. The same item clicked five times in parallel → one charge. Several accounts racing for the last units → exactly the available number succeed, losers uncharged. Same idempotency key twice at once → one effect; later retry replays; different body refused. A coupon used up between ordering and paying → second payment refused, order cancelled. Reconciliation returns ok afterwards.
