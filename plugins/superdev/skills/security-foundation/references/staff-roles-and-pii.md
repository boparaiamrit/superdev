# Staff identity, roles, permissions and personal data

## A separate identity

Staff are not end users with a flag. They get their own table (`admin_users`), their own sessions table, their own cookies (names and paths scoped to `/api/v1/admin`), and a JWT with its own audience/`typ`. End-user guards skip admin routes (an `@AdminArea()` marker); the admin guard runs only on them. An end-user cookie on an admin route is 401, and the reverse.

## Permissions are keys; roles are bundles

- A **permission catalog** in the shared contracts: `{ key: 'leads.contact', group: 'Leads', label: 'Reveal a customer’s phone number and email' }`. The API checks keys (`@RequirePermission('leads.contact')`), never role names.
- **Roles** live in the database: name, description, `is_system`, `permissions text[]`. Seed sensible defaults (Owner, Admin, Manager and task roles); the **Owner** role is a locked system role holding every permission.
- The guard re-reads session, staff status and role on **every** request, so removing a permission or disabling someone takes effect on the next request, and live streams re-check on their interval or at once on `me.changed`.
- `GET /admin/me` returns the effective permission list so the UI hides what a role cannot use; the API enforces the same keys and returns a friendly 403 the UI renders as "your role does not allow this".

### A starting catalog and default roles (adapt to the product)

| Group | Keys |
| --- | --- |
| Dashboard | `dashboard.view` |
| Items (e.g. leads, customers) | `items.view`, `items.contact` (reveal), `items.create`, `items.import`, `items.edit`, `items.close` |
| Accounts (e.g. sellers, providers) | `accounts.view`, `accounts.contact` (reveal), `accounts.edit`, `accounts.approve` (approve/block), `accounts.password` |
| Money | `credits.view`, `credits.adjust`, `orders.view`, `orders.create`, `orders.payment` |
| Reports | `reports.view`, `reports.resolve` |
| Catalogue / settings | `catalog.view`, `catalog.manage`, `reference.manage` |
| Team and security | `team.view`, `team.manage`, `roles.manage`, `sessions.view`, `sessions.revoke`, `audit.view` |

| Default role | Holds | Never holds |
| --- | --- | --- |
| Owner (system, locked) | everything | — |
| Admin | everything except `roles.manage` | — |
| Manager | day-to-day operations incl. reveal, approve, adjust | `roles.manage`, `team.manage` |
| Caller / telecaller | view, **reveal contact**, edit, raise orders | money adjustments, approve/block, dashboard numbers |
| Marketer | dashboard, view, catalogue/coupons | **any reveal permission**, money, team |
| Finance | view, adjustments, orders and payments, audit log | reveal of customer contact |
| Support | view, reveal account contact, reports | money adjustments, team |

### Definitions the guards use

- Role **A exceeds** role B when A's permission set is **not a subset** of B's. You may manage a colleague only if their role does not exceed yours (their permissions are a subset of yours); peers with equal sets may manage each other.
- Granting the Owner role therefore needs every permission — only an Owner can make an Owner.
- The system Owner role's permissions, name and system flag are immutable (409 `ROLE_LOCKED`).
- Status codes: lacking the permission → 403 `FORBIDDEN`; a rule about the target's state (last owner, self-change, role in use, locked role) → 409 with its own code.

## Escalation guards (enforce in the service, test each)

- Nobody can create or edit a role with permissions they do not hold.
- Nobody can assign a role that grants something theirs does not, or edit/disable/reset a colleague whose role exceeds theirs.
- Nobody can disable themselves or change their own role.
- There is always at least one active Owner. Check it inside a transaction holding a lock (e.g. an advisory lock on "staff roles"), or two owners demoting each other at once can leave none.
- A role with members cannot be deleted.
- Permission changes notify affected staff (`me.changed`).

## Personal data: masked by default, revealed on purpose

- **Lists and detail views never contain contact details.** Phone/email/alternate phone come back as fixed masks (`+91 ••••• •••••`, `••••••••@•••••.com`) — the real value is **not in the JSON**, not merely hidden in the UI.
- **Reveal is a separate permission** (`accounts.contact`, `items.contact`) and a separate endpoint (`POST /admin/<thing>/:id/contact`) that returns the values and writes an audit row naming the staff member.
- **Search by contact field** (phone, email) is allowed only for roles with the reveal permission; otherwise a search would confirm who owns a number.
- **Editing** a contact field requires the reveal permission; the edit form omits contact fields unless revealed and changed, so a masked value is never written back.
- Exports follow the same rule: masked unless the role may reveal, and the export is audited.
- **The reveal audit is written synchronously and fails closed:** if the audit row cannot be written, the value is not returned. A queued audit write that can be lost is not enough for a reveal.
- **Rate-limit reveals per staff member** (e.g. a few dozen per hour) and notify owners when someone exceeds a threshold — the permission exists to make calls, not to export a list. Require staff two-factor for any role holding a reveal permission.
- **Free text leaks contact data:** notes, messages and descriptions can contain numbers. Do not show end-user free text to roles without the reveal permission unless it is scrubbed, and never put contact details into URLs (`tel:`, `wa.me`) rendered for roles that cannot reveal.
- **Audit rows never hold the revealed values** — record who revealed whose contact, not the number.

## Audit

Every staff mutation and every reveal writes `audit_logs` with actor kind (Admin/Merchant/System/Anonymous), actor id, the subject and subject id, the affected end user (from the route param or body), status (Success/Failure — failures are audited too), request id and IP. Readable action labels in the admin audit log; recent activity on the dashboard only for roles with `audit.view`.

## Proof (committed tests)

A role-matrix suite: for every staff endpoint × every seeded role, the expected status (200/403). Masking: every list/detail response for every role contains no real contact value — and on the end-user side, an item that has not been unlocked/purchased contains no contact fields at all (search the raw JSON for the seeded phone numbers). Reveal: allowed roles get the value and an audit row appears with their name; others get 403. Escalation: each guard above returns 403/409. Removing a permission applies on the very next request. A disabled staff member's open session and stream end.
