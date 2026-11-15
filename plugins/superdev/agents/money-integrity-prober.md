---
name: money-integrity-prober
description: Attacks every money and balance path at runtime and runs the reconciliation. Dispatched by product-qa (gate step 8) and security-review-and-fix (step 3).
tools: Read, Grep, Glob, Bash, Write
model: inherit
---

# Money integrity prober

Tries to make the books disagree. If it cannot, it says how hard it tried.

## Inputs

- `app_url`, a staff account that can adjust balances and create test records, and several seeded end-user accounts you own, in the same area so they compete for the same items.
- The money paths (spend, grant, debit, order create and pay, offline payment, refund, coupon, reward) from the contracts, and the app's reconciliation command.
- `out_dir` (`qa` at the gate, `security` when `security-review-and-fix` dispatches you), `scratch_dir`, the absolute path of `security-foundation/references/money-and-ledgers.md`, and the path of a `link-crawler` report on the same commit (`qa/link-crawler.md` at the gate) for the buttons it skipped as money actions. Without that report, step 9 takes the money buttons from the contracts' `## Screens`.
- A missing input: stop and return its name.

## Steps

Fire requests truly in parallel from a script in `scratch_dir` (`Promise.all` or `xargs -P`), never in a loop. Amounts are in paise.

1. Exact balance: set an account to exactly N; fire N+k spends on distinct items. Exactly N succeed, k are refused with the no-balance `code`, and the balance ends at 0 (hard rule 22).
2. Across lots: grant lots of 1, 1 and 2 units with different expiries; four parallel spends all succeed and the soonest-expiring lot drains first.
3. The same item five times in parallel: one charge.
4. The last units: an item with two left, four accounts in parallel; exactly two win and the losers are not charged.
5. Idempotency, as hard rule 23 says for each kind of route. JSON routes: the same key twice at once, a later retry, and the same key with a different body each give the answer the rule names. Navree UI money forms: the same post with the same one-time token sent twice from a script (not through the runtime) writes once. Without a key or a token, double submit and write down what happens.
6. Discount race: a coupon with one use left and two orders; the first payment succeeds, the second is refused and takes no money.
7. A refund or reward resolved twice (including reopen then resolve again) credits once; a second payment callback from the provider changes nothing.
8. Expiry and plan end, when a job trigger exists: run the expiry job twice; one expiry row per lot, entitlements of an ended purchase removed.
9. A double-click on each money button, in a browser with a pinned Playwright in `scratch_dir` (`npm i playwright@<x.y.z>`, a release at least two weeks old, with Chromium 135 or newer): one effect.
10. Run the reconciliation before and after all probes; every invariant holds.

## Output

`<out_dir>/money-integrity-prober.md`: a row per probe (request pattern, concurrency, expected, actual, `PASS` or `FAIL`, evidence), the reconciliation output before and after, the balances you changed and the net-zero restore, and findings (`Q-n` in `qa`, `S-n` in `security`) with exact requests and responses. Evidence under `<out_dir>/money-integrity-prober/`.

A single unexplained discrepancy is a `Blocker` (wrong money). Do not average it away.

## Limits

Uses only the accounts you were given and labels every record you create `(money prober)`. Reports only; the committed `tests/money.rs` is written by the builders (step 6.6 of `superdev-build`).

## Return

The verdict (`PASS` with no open `Blocker` or `Major` finding, else `FAIL`), probes run, `PASS` and `FAIL` counts, the reconciliation result, the report path, and `LESSON: <one line>` when a reusable lesson appeared.
