# Orchestration Patterns

How the orchestrator (the main Claude Code session) uses subagent primitives. Read this before dispatching any subagent.

## The Agent tool (formerly Task)

Claude Code's `Agent` tool spawns a subagent in a separate context window. The previous name `Task` still works as an alias for backward compatibility.

Conceptually:

```
Agent(subagent_type='<agent-name>', prompt='<instructions>')
```

But you don't write this literally — Claude Code emits the tool call when you describe what you want in natural language:

> "Use the prd-analyst subagent to read the PRD at docs/PRD.md and produce PRD_DIGEST.md."

The main session translates this into an `Agent` tool call with `subagent_type='prd-analyst'` and an appropriate prompt.

- `subagent_type` matches a file at `.claude/agents/<agent-name>.md`
- The prompt is the only message the subagent receives — be precise
- The subagent runs to completion and returns a single text summary
- The subagent's tool calls, file reads, and file writes happen in its own context window — the main session does not see them in real time

The subagent inherits the project's CWD and filesystem state. Anything it writes to disk persists for subsequent agents to read.

**Critical: subagents cannot spawn other subagents.** Only the main session can dispatch via the `Agent` tool. If your workflow needs nested delegation, the main session must orchestrate every level explicitly — there is no recursion. Builder subagents return results and stop; they do not chain to other builders.

## Subagent definitions

Each subagent is a markdown file at `.claude/agents/<name>.md` with frontmatter:

```markdown
---
name: prd-analyst
description: Reads a PRD document and produces PRD_DIGEST.md with structured entity/screen/feature/integration extraction. Read-only; never writes outside the digest file.
tools: Read, Grep, Glob
model: haiku
---

# System prompt body goes here
You are a PRD analyst. Your job is to ...
```

Frontmatter fields (most useful subset; see [Claude Code docs](https://code.claude.com/docs/en/sub-agents) for the full list):

- `name` — kebab-case identifier; the filename does not need to match
- `description` — when the main session should delegate to this subagent
- `tools` — comma-separated allowlist; if omitted, inherits all tools (rarely what you want)
- `disallowedTools` — denylist alternative
- `model` — `sonnet`, `opus`, `haiku`, full model ID, or `inherit`. Default: inherit. Use `haiku` for cheap read-only work.
- `permissionMode` — `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, `plan`
- `skills` — preload these skill bodies into the subagent's context at startup (big context-savings win for builder agents)
- `mcpServers` — MCP servers exclusive to this subagent
- `memory` — `user`, `project`, or `local` for persistent learning across invocations
- `hooks` — `PreToolUse` / `PostToolUse` / `Stop` hooks scoped to this subagent

The body is the subagent's system prompt. It defines the role, inputs, outputs, constraints, and examples.

## Parallelism

Multiple `Agent` tool calls in **one tool-use batch** run concurrently. The main session emits a batch by describing the parallel work in one message:

> "Dispatch two subagents in parallel:
> 1. Use the prd-analyst subagent to read the PRD and produce PRD_DIGEST.md.
> 2. Use the design-inventory subagent to inventory the design and produce DESIGN_DIGEST.md."

Claude Code translates this into two `Agent` tool calls in one batch. They run with independent contexts.

The anti-pattern — sequential when independence allows parallel — looks like two separate messages, each waiting for the previous result.

The wins are real: 2 subagents in parallel is ~2× faster than sequential, 6 is ~6×. The orchestrator's job is to recognize independence and batch aggressively.

### When NOT to parallelize

- **Producer/consumer pairs.** If subagent B reads what subagent A writes, they must be sequential. (`gap-auditor` reads what `prd-analyst` produces — never batch them.)
- **Foundational steps.** `monorepo-bootstrapper` must finish before anything else writes to the repo.
- **Race-prone writes.** Two subagents writing to the same file is a merge conflict waiting to happen. Define exclusive ownership per subagent (see "Exclusive ownership" below).

### When TO parallelize

- **Independent inputs.** `prd-analyst` reads the PRD; `design-inventory` reads the design. They share no input and write to different files.
- **Per-feature builders.** `backend-module-builder` for `companies` and `backend-module-builder` for `contacts` write to different folders. Run them concurrently.
- **Cross-app builders for same feature.** Once `packages/contracts/src/companies.ts` exists, the backend and frontend companies modules write to entirely different paths. Run them concurrently.

### Concurrency cap

Claude Code can spawn many subagents, but each consumes context and compute. **Cap at 6 concurrent `Agent` tool calls per tool-use batch.** Beyond that, returns diminish and the coordination overhead spikes.

For a 5-feature wave, that's 10 builders (backend + frontend per feature). The orchestrator splits into two batches and waits between them. Describe each batch as a single natural-language instruction:

> "Batch 1 — dispatch six subagents in parallel: backend-module-builder + frontend-module-builder for companies, contacts, and mailboxes."

After all six complete:

> "Batch 2 — dispatch four subagents in parallel: backend-module-builder + frontend-module-builder for campaigns and pipeline."

## Agent teams: an alternative to subagents

Subagents are the right default. **Agent teams** are an opt-in alternative for specific phases where teammates need to communicate. Enable with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `settings.json` or environment.

Differences from subagents:

| | Subagents | Agent teams |
|---|---|---|
| Lifecycle | Spawn → work → return → done | Long-lived; can be re-messaged |
| Cross-talk | None (workers report to caller only) | Teammates message each other directly |
| Coordination | Caller decides everything | Shared task list; teammates self-claim |
| User interaction | Only with main session | Shift+Down to message any teammate |
| Cost | Lower | ~3× per teammate |

**The agent definitions in `.claude/agents/<name>.md` work as both subagent definitions AND teammate types without modification.** When the user asks the lead to "spawn a static-auditor teammate," the same file's `tools` and `model` apply, and the body is appended to the teammate's system prompt as additional instructions.

When to consider agent teams over subagents:
- The "competing hypotheses" pattern (security audit, hard performance investigation, gap audit on ambiguous PRDs)
- Long-running roles the user wants to message directly (a tester, a researcher)
- Pair-programming style work where backend↔frontend must negotiate contracts live

When NOT to use agent teams:
- Read-only audits with clear outputs (use subagents — cheaper, deterministic)
- Per-feature parallel builds with no cross-feature dependencies (use subagents)
- Anything that fits the subagent pattern cleanly (subagents are stable; agent teams are experimental)

This skill notes specific phases where agent teams are useful. See "Agent teams (optional)" sections in Phase A.3, Phase C.2, and Phase D.

Don't try to chain Batch 2 into the same tool call as Batch 1 expecting "queuing" — Task calls all start immediately.

## Exclusive ownership

To prevent merge conflicts when subagents run in parallel:

| Agent | Owns (exclusive write) | May read |
|---|---|---|
| `prd-analyst` | `PRD_DIGEST.md` | the PRD source |
| `design-inventory` | `DESIGN_DIGEST.md` | the design source |
| `gap-auditor` | `AUDIT.md` | both digests |
| `plan-architect` | `EXECUTION_PLAN.md` | digests + audit |
| `monorepo-bootstrapper` | root `package.json`, `pnpm-workspace.yaml`, `turbo.json`, `apps/api/package.json`, `apps/web/package.json`, `packages/*/package.json`, infra files | EXECUTION_PLAN |
| `contracts-author` | `packages/contracts/src/*.ts` | EXECUTION_PLAN |
| `backend-module-builder` | `apps/api/src/modules/<feature>/**`, `apps/api/src/db/schema/<feature>.ts` | contracts, other modules' types (read-only) |
| `frontend-module-builder` | `apps/web/src/modules/<feature>/**`, `apps/web/src/mocks/<feature>/**`, `apps/web/src/app/<feature-routes>/**` | contracts, design source |
| `integration-tester` | (none — read-only test runs) | everything |

Two backend-module-builders running concurrently for different features never write to the same path. Safe.

If an agent NEEDS to touch shared files (e.g., `app.module.ts` to register a new feature module), centralize that in a separate "wiring" pass after the wave: the orchestrator does it directly, or dispatches a single sequential agent for it.

## Error handling and retries

A subagent can fail by:

1. **Returning early with a "can't proceed" message** — usually a missing input. Orchestrator: inspect, fix the missing input, re-dispatch.
2. **Reporting completion but leaving a broken state** — typecheck fails after it claims done. Orchestrator: catch via wave-gate typecheck, dispatch a focused fix prompt.
3. **Tool-call failures inside the subagent** — usually transient. Re-dispatch with the same prompt.

The orchestrator should NEVER:

- Re-dispatch the same agent more than 3 times for the same task without changing the prompt
- Ignore a failure and proceed to the next wave
- Trust a "done" report without the wave-gate check

## Prompt structure for subagent dispatch

A well-formed prompt to a subagent has four parts:

```
1. Task statement      — one sentence: what to do
2. Inputs              — paths/files to read
3. Outputs             — exact path and shape of the artifact to produce
4. Constraints         — what NOT to do, scope boundaries
```

Example for `prd-analyst`:

```
Task: Read the PRD at ./PRD.md and produce a structured digest.

Inputs: ./PRD.md (markdown)

Outputs:
  Write a single file at ./PRD_DIGEST.md following the format in
  ~/.claude/skills/prd-design-build-orchestrator/references/artifacts-format.md.
  Include: features list, entity list with view-shape proposals, screen list,
  external integrations, NFRs.

Constraints:
  - Do NOT make architectural decisions (which DB, which auth model, etc.) —
    record what the PRD says; the plan-architect will decide later.
  - Do NOT modify the PRD source.
  - Do NOT write any file other than PRD_DIGEST.md.
  - If the PRD is incomplete or contradicts itself, surface the issue in a
    "QUESTIONS" section at the end of the digest.
```

Subagents are good at following structured prompts. Sloppy prompts produce sloppy outputs.

## Anti-patterns

- ❌ **Telling a subagent about other subagents.** They don't share context. If `gap-auditor` needs `prd-analyst`'s output, give it the file path, not a reference to the agent.
- ❌ **Long sequential chains in the orchestrator.** Look for parallelizable lanes. If 5 things run in 5 sequential subagents, that's a 5x speed-up missed.
- ❌ **Granting Write to read-only agents.** They will sometimes create unsolicited files.
- ❌ **One-shot "do everything" agents.** Specialize. Each agent has one job; that's what makes the multi-agent system useful.
- ❌ **Hoping subagents will negotiate.** They can't talk to each other mid-run. Plan the handoff before dispatching.
- ❌ **Dispatching without reading the previous wave's output.** The orchestrator MUST check artifacts between phases.
