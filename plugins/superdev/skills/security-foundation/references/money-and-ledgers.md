# Money and ledgers

Rules for any stored balance that requests or jobs change: message credits, wallets, stock, seats, quotas. They serve rule SEC-11 of [security-foundation](../SKILL.md) and build on hard rules 22 (one lock per account) and 23 (idempotent requests). The example: Ledgerly sells message credits for invoice reminders sent by SMS, in packs of 1,000 for ₹ 1,499 (stored as 1,49,900 paise, rule BE-9); each reminder spends one credit.

## Lots and an append-only ledger

Two workspace tables (hard rule 10):

| Table | Columns |
|---|---|
| `credit_lots` | `id`, `workspace_id`, `source` (`purchase`, `grant`, `adjustment`), `order_id` (purchases), `credits_added`, `credits_left`, `expires_on`, `created_at` |
| `credit_ledger` | `id`, `workspace_id`, `lot_id`, `activity` (`purchase`, `grant`, `spend`, `expiry`, `refund`, `adjustment`), `delta` (positive or negative), `balance_after`, `actor_id`, `reason`, `created_at` |

- The balance is the sum of `credits_left` over lots that have not expired.
- A spend takes from the lot that expires soonest; on a tie, from the older lot.
- Every movement writes one ledger row per lot it touches, in the same unit of work as the change to the lot. Ledger rows are never updated or deleted: the module has no route or job that does either.
- A manual adjustment is its own activity: it needs `credits.adjust` and a recent sign-in (SEC-6), names the staff member in `actor_id` and a reason; added credits get an expiry date; a debit never takes more than the balance.
- The expiry job zeroes expired lots and writes their ledger rows; a mass update skips the audit log, so it records its changes with `uow.record_change` (hard rule 7).

Without lots (a khata of credit and repayments, a wallet that does not expire), the ledger rows are the balance: each row carries `balance_after`, and the lock of hard rule 22 still applies.

## Locking

Every path that changes a balance (spend, grant, purchase, adjustment, expiry, refund) takes the account's lock first (hard rule 22). A unit of work that touches several accounts locks them in sorted order of id. A spend that also takes from a shared item with its own limit (the last seats of a training batch in Pune) locks the item row first and the account second, in that order on every path (check `navree-database` for a row lock), and changes the item's counter in the same unit of work as the charge.

## Idempotency store

For JSON routes, Navree has no store for incoming `Idempotency-Key` headers; the app builds one (hard rule 23). A Navree UI form uses the same table with its one-time token as `key`: a repeat post finds the row and changes nothing, answering with the result of the first write.

1. A table `idempotency_keys` with `actor_id`, `route`, `key`, `request_hash`, `state` (`running` or `done`), `status`, `body`, `created_at`, and a unique index on (`actor_id`, `route`, `key`).
2. Claim before the work: insert the row with `state = running` in a transaction of its own, committed before the handler's unit of work does anything (check `navree-database` for opening one). A conflict on the unique index means the key is known: `running` answers 409 `idempotency_in_progress`; `done` with the same hash replays the stored status and body with `Idempotent-Replayed: true`; a different hash answers 409 `idempotency_key_reused`.
3. Inside the request's unit of work, set the row to `done` with the status and body, so the effect and the stored answer commit together.
4. When the request fails (status 400 or more, its unit of work rolled back), delete the claim in a transaction of its own so a corrected retry can run; a `running` row older than the request timeout counts as released.
5. A scheduled task deletes rows older than 24 hours. The stored body can hold personal data: the table is never logged, and for such routes the row keeps the record id and the replay reads the record again instead.

## Payments

With `navree-billing` (the opt-in feature `billing`; the kits turn it on):

- A payment is confirmed by the provider's verified webhook, never by the browser's return; the amount is checked against the order.
- Activation runs once: under a lock on the order row, `pending` becomes `paid` and the pack's lot is granted in the same unit of work; a second callback finds `paid` and changes nothing.
- A payment that staff record by hand goes through the same activation function.
- A discount is checked again at payment: a coupon that expired or ran out since the order was placed cancels the order and tells the buyer; an invalid discount is never charged.
- Entitlements bought with a purchase end with it: a scheduled task removes them when the plan ends and no other plan grants them, without touching what staff set by hand.

## Reconciliation

A console command (`navree make:command credits reconcile`), scheduled nightly at 02:00 IST and runnable on demand, lists every row that breaks a check:

- for each lot, the sum of its ledger deltas equals `credits_left`, which is never below 0 or above `credits_added`;
- for each workspace, the sum of unexpired `credits_left` equals the last `balance_after`;
- every paid order granted its pack exactly once, and no unpaid order granted anything;
- every refund and reward was paid exactly once, and only for a source that qualifies;
- no coupon counter is behind the paid orders that use the coupon;
- every adjustment names a staff member and a reason;
- every expired lot was zeroed by the expiry job;
- every item counter equals the rows it counts and stays within its limit.

A failing check notifies the staff role that holds `credits.adjust`. The demo seed satisfies every check (rule BE-14): seeded lots have their orders and ledger rows.

## Proof

`tests/money.rs`, with the parallel tests on the real database ([security-suites.md](security-suites.md)), and again through the running app by `money-integrity-prober` at the QA gate:

- an exact balance N and N+k parallel spends: N succeed, k get 409 `insufficient_credits`, the balance ends at 0 and never goes below (hard rule 22);
- parallel spends across several lots all succeed;
- one reminder sent five times in parallel with one key: one charge; the cases of hard rule 23;
- a coupon used up between order and payment: the payment is refused and the order cancelled;
- a second payment callback changes nothing;
- the reconciliation reports nothing after the suite.
