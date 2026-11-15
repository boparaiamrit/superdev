# Superdev

Superdev is a plugin of 15 skills and 41 agents for Claude Code and Codex. It is the process for taking a product from a brief and a design to a released, verified app on Navree, a Rust application framework: the order of work, the files written to disk, the rules, and the proof each step needs. Navree's own skills, which every app installs with `navree skills:install`, hold the framework facts; superdev names the skill and the command for each fact instead of restating it. Screens are Navree UI pages drawn on the server, or a Next.js front end on the Navree API; desktop and phone clients in Tauri are optional.

Version 3.0.0.

Status: 3.0.0 has been checked by its tests and by reading against Navree's documentation and source, and its done check has been tested against stand-ins of the Navree CLI; it has not yet been used to build an app end to end.

## Install

Run these from the target Git project; superdev is installed per project, never at user scope:

```shell
claude plugin marketplace add boparaiamrit/superdev --scope project
claude plugin install superdev@superdev --scope project
```

The helper `bash /path/to/superdev/install-superdev.sh` runs the same two commands and checks the result. Codex installs superdev from the repository marketplace `.agents/plugins/marketplace.json`; see [INSTALL.md](INSTALL.md) and [CODEX.md](CODEX.md).

For an existing Navree app, the target project is the app. For a new product, it is a Git folder that holds the PRD and the design; the build creates the app inside it, as a Git repository of its own, and installs superdev in the app ([INSTALL.md](INSTALL.md), "Which project to install it in").

To start a build, give the agent the PRD and, if there is one, the design:

```text
Build this product on Navree. The PRD is docs/prd.md and the design is in docs/design/.
```

## What a build does

The [superdev-build](plugins/superdev/skills/superdev-build/SKILL.md) skill runs these steps in order, and each one ends with a proof on disk:

1. **Navree and the app:** the Navree CLI, the app (created with the agreed `navree new` line, or the existing one), Navree's skills installed, `STACK.md` written.
2. **Digests:** the PRD and the design extracted into `PRD_DIGEST.md` and `DESIGN_DIGEST.md`, without decisions.
3. **Plan:** gaps decided by the operator in `GAPS.md`; `EXECUTION_PLAN.md` written and confirmed before any code.
4. **Foundation:** local services, migrations, the security foundation, the demo seed and the first suite; the release binary boots.
5. **Contracts:** a contract per module in `contracts/`, agreed by the operator before its code.
6. **Modules:** one module at a time: the contract in code, the backend, the runtime proof, the screens, the browser proof, the suites, a commit.
7. **Audits:** the security review, then the product audit.
8. **QA gate:** every route, role, width and colour mode on fresh data, in `QA_COVERAGE.md`, with evidence in every cell.
9. **Deployment:** when the operator asks, with Navree's tools and the deploy checklist.
10. **Done:** `verify-done.mjs --suites --strict` exits 0 on the final commit; lessons recorded.

## Skills

| Skill | Use it when |
|---|---|
| [superdev-build](plugins/superdev/skills/superdev-build/SKILL.md) | building a product from a PRD and a design as a Navree app, or resuming such a build |
| [backend-on-navree](plugins/superdev/skills/backend-on-navree/SKILL.md) | building or changing a backend module: models, routes, validation, access, workspace scope, lists, jobs, mail, audit, seed data |
| [security-foundation](plugins/superdev/skills/security-foundation/SKILL.md) | the app has sign-in, staff, roles, personal data, money or live updates, at step 4 and whenever a module adds one |
| [design-to-navree-ui](plugins/superdev/skills/design-to-navree-ui/SKILL.md) | a design must become Navree UI screens |
| [design-to-nextjs](plugins/superdev/skills/design-to-nextjs/SKILL.md) | a design must become a Next.js front end of a Navree API |
| [frontend-structure](plugins/superdev/skills/frontend-structure/SKILL.md) | laying out or auditing a module of a Next.js front end, or splitting one that has grown too large |
| [prototype-to-navree](plugins/superdev/skills/prototype-to-navree/SKILL.md) | a prototype or an older product must become a Navree app without losing what its users see |
| [design-preservation](plugins/superdev/skills/design-preservation/SKILL.md) | a prototype must be kept as built and every screen checked against it |
| [design-to-tauri](plugins/superdev/skills/design-to-tauri/SKILL.md) | the product needs a desktop or phone client in Tauri on its Navree API |
| [security-review-and-fix](plugins/superdev/skills/security-review-and-fix/SKILL.md) | an app needs a security review: before launch, after a large change, a secret scan, a dependency audit |
| [product-audit](plugins/superdev/skills/product-audit/SKILL.md) | someone needs to know whether the product is really done: real data, wired controls, readiness scores, a full inventory |
| [product-qa](plugins/superdev/skills/product-qa/SKILL.md) | someone asks whether it is tested: every page, every role, contrast, dead links, the phone app; or to explore the running app |
| [systematic-debugging](plugins/superdev/skills/systematic-debugging/SKILL.md) | anything fails: a test, a build, a runtime error, a flaky test |
| [superdev-done](plugins/superdev/skills/superdev-done/SKILL.md) | someone asks whether the build is done, and before any completion claim |
| [superdev-self-learning](plugins/superdev/skills/superdev-self-learning/SKILL.md) | the operator corrects the approach or reverts code, a verifier rejects work, or someone says remember this |

Each skill also runs on its own when a request matches its description.

## Agents

The 41 agents are listed by role in [plugins/superdev/README.md](plugins/superdev/README.md); the skills dispatch them, one module or one task at a time.

## Hard rules

The 25 hard rules in [hard-rules.md](plugins/superdev/skills/superdev-build/references/hard-rules.md) each say where they apply and the check that proves them.

## Requirements

- The Navree CLI (`cargo install navree-cli`) and what Navree needs: Rust 1.95 or newer, a C compiler (gcc or clang; on Windows the MSVC build tools), and Docker or Podman for a local TimescaleDB or PostgreSQL database (MySQL runs on a server you provide; SQLite needs nothing).
- Node.js 22 or newer, only for a Next.js front end and for the browser tools of the QA agents.
- Claude Code or Codex.
- Python 3.9 or newer and `node`, to run this repository's tests.

## Version 2.1.0 for NestJS and Laravel projects

Version 2.1.0 remains the version for NestJS and Laravel projects. Install it in such a project with:

```shell
claude plugin marketplace add boparaiamrit/superdev#v2.1.0 --scope project
claude plugin install superdev@superdev --scope project
```

A project that already uses 2.1.0 added the marketplace without that pin, so an update would bring 3.0.0: [INSTALL.md](INSTALL.md) shows how to pin it to 2.1.0.

## Development

```bash
python -m unittest discover -s tests -v
python tools/build_zip.py
```

`superdev.zip` is the archive attached to each GitHub release; `python tools/build_zip.py` rebuilds it from `plugins/superdev/`, and `--check` compares it with the committed one.

```text
plugins/superdev/      the plugin: skills/, agents/, scripts/verify-done.mjs and both manifests
.claude-plugin/        the Claude Code marketplace
.agents/plugins/       the Codex marketplace
tests/                 the repository's tests
tools/build_zip.py     builds superdev.zip
```

## License

MIT; see [LICENSE](LICENSE).
