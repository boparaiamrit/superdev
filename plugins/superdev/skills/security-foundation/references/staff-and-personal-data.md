# Staff and personal data

How a build defines its roles and permission keys, guards against escalation, and keeps personal data masked until someone allowed to see it reveals it on purpose. It serves rules SEC-7 to SEC-10 of [security-foundation](../SKILL.md). The examples come from Ledgerly, a small invoicing product with the workspaces "Sandhu Traders, Ludhiana" and "Sharma Textiles, Pune" and two staff roles of the company that runs it.

## Permission keys

A key is `<subject>.<action>` in lower case; `src/abilities.rs` turns the keys a person holds into abilities (`navree-access-control`). The catalog is written in `EXECUTION_PLAN.md` `## Access` at step 3 and in each contract's `## Abilities and permissions`, one row per key:

| Key | Allows | Workspace roles | Staff roles | Staff-only |
|---|---|---|---|---|
| `customers.read` | list and open customers, contact fields masked | `owner`, `admin`, `member`, `viewer` | `support`, `finance` | no |
| `customers.reveal_contact` | see one customer's phone and email in full | `owner`, `admin`, `member` | `support` | no |
| `invoices.send` | send an invoice to its customer | `owner`, `admin`, `member` | none | no |
| `members.manage` | change the workspace role of another member | `owner`, `admin` | none | no |
| `credits.adjust` | add or remove message credits by hand, with a reason | none | `finance` | yes |
| `helm.view` | open Helm, the staff panel at `/admin` | none | `support`, `finance` | yes |

## Default roles

- Workspace roles are `owner`, `admin`, `member` and `viewer`; their keys go in `config/app.toml`, for example `[workspace.roles.viewer]` with `permissions = ["customers.read"]`. What `owner` holds without a list: check `navree-workspaces`. Inside a workspace, the workspace role decides.
- Staff roles are global rows in the database: the demo seeder creates them, their grants and the staff accounts that hold them, and production gets them from a release step (rule BE-14 has the calls). Staff use Helm (`navree-helm`), which has no permission system of its own and asks the same abilities.
- Key names stay clear of `AccessModule`'s own: `roles.manage` is its global permission for managing roles, so a workspace key that manages members is named `members.manage`.
- The global role `admin` is `AccessModule`'s super-admin and holds every ability: give it to nobody who needs less. It is not the workspace role `admin`.
- Who holds what is decided in the plan; a staff role never gets reveal and money keys together unless the PRD asks for it (in Ledgerly, `support` reveals and `finance` adjusts credits).
- A password that staff set for someone else is temporary: the person changes it at the next sign-in (check `navree-auth`, account flows; record an open item `O-n` when it is missing).

## Escalation guards (SEC-8)

Role A exceeds role B when A's keys are not a subset of B's. The guards run in the service, inside the request's unit of work:

| Guard | Answer | Test in `tests/access.rs` |
|---|---|---|
| nobody assigns a role that exceeds their own | 403 `forbidden` | Gurpreet Kaur (`admin`) makes Arjun Mehta an `owner`: refused |
| nobody manages a member whose role exceeds theirs | 403 `forbidden` | an `admin` changes the role of an `owner`: refused |
| nobody changes their own role | 409 `own_role` | Meera Sharma changes her own role: refused |
| nobody disables or removes themselves | 409 `own_account` | Harpreet Sandhu removes himself: refused |
| a workspace keeps at least one `owner` | 409 `last_owner` | the only `owner` steps down: refused; two owners demote each other at the same time: one `owner` remains |
| a permission change tells the person | a notice (SEC-5's channel) | Arjun Mehta's role changes: his notice is found |

The last-owner check takes a lock per workspace before it counts the owners: on PostgreSQL and TimescaleDB the same transaction-scoped lock as hard rule 22; on MySQL and SQLite check `navree-database` and record the method. Its parallel test runs on the real database ([security-suites.md](security-suites.md)). Whether a removed permission applies on the next request or when the access token is renewed: check `navree-access-control`, record it in the plan, and test that behaviour.

## Masks

- A role without the reveal key never receives a contact value: the resource struct is built for the caller's role and the real value is not in the JSON (rule BE-1), not merely hidden on the screen. In a Navree UI table the column is removed with `TableQuery::without_columns` (rule NUI-3).
- Formats, made on the server by one function used everywhere: phone `+91 98140 12345` becomes `+91 98••• ••345`; email `meera.sharma@example.com` becomes `m•••@example.com`.
- An edit form for a role without reveal leaves the contact fields out, so a mask is never written back.

## Reveal

1. The key `customers.reveal_contact` and a route of its own, declared for the action the key grants on the record from the path: in a Navree UI app a form post `POST !/customers/{id}/reveal-contact` with `.can("reveal_contact", "Customer", Some("id"))`; for a token client `POST /api/v1/customers/{id}/reveal-contact` with `#[can(..)]` and `from = "id"`.
2. A recent sign-in and no impersonation (SEC-6): `#[recent_auth(minutes = 10)]` and `#[not_while_impersonating]` on a JSON route; for a page route, check `navree-auth` and `navree-ui` for the same guards on a `RouteDef`.
3. The handler writes the audit entry with `record_in` (action `customers.contact_revealed`, the customer as subject, the caller as actor, no contact value in the metadata) before it returns the values, so a failed write returns nothing.
4. At most 30 reveals an hour per person: check `navree-controllers-and-routing` for a throttle keyed by the account; otherwise count the person's entries of the last hour in the handler and answer 429 with `Retry-After`. Reaching the limit notifies the person the plan names (a workspace's owners for its members).
5. Searching by phone or email needs the reveal key; otherwise a search confirms who owns a number. The contact fields are not searchable in the list spec that other roles use.

## Sessions, devices and failed actions

- A person sees their sign-ins and ends one: Navree lists and ends sessions (`GET /api/auth/sessions`, `DELETE /api/auth/sessions/{id}`); check `navree-auth` for a page that shows them, and build one from Navree UI components when there is none.
- A sign-in from a new device sends the person a notice (SEC-5's channel): check `navree-auth` for one; when Navree sends none, build it and record it in the plan.
- A staff action that is refused or fails is audited too, with `AuditLog`'s `record`, which writes outside the request's unit of work (rule BE-12).

## Exports and free text

- An export is masked unless the role holds the reveal key, is audited (`#[audit]` with the action `customers.exported`) and is throttled.
- Notes and messages can contain phone numbers and emails: for a role without the reveal key, scrub them before showing the text, or do not show it.
- No contact data in URLs: no `tel:`, `mailto:` or `wa.me` link for a role without the reveal key.

## Proof

In `tests/access.rs`, and again in a browser by `role-matrix-tester` at the QA gate:

- every route of every contract against every role: the status the contract gives;
- for every role without the reveal key, the raw body of every list, detail and export contains none of the seeded phone numbers or emails;
- reveal: an allowed role gets the values and an audit entry naming the caller; other roles get 403; the 31st reveal within the hour gets 429;
- each escalation guard of the table above, with its status and `code`;
- a removed permission stops working as the plan records.
