# Project-Scoped Superdev Installation Design

**Date:** 2026-07-20

**Status:** Approved

## Problem

Superdev is intended to apply only to the project in which it is installed. The current repository contradicts that contract in several places:

- Claude installation guidance omits `--scope project`, so the CLI defaults to user scope.
- `install-superdev.sh` copies the plugin into `~/.claude/plugins/superdev` and edits `~/.claude/settings.json`.
- The installer still reports version 1.3.1, 6 skills, and 24 agents, while the repository contains version 1.6.0, 16 skills, and 51 agents.
- Bundled instructions contain 99 references to `~/.claude/skills`, which do not point at a marketplace-installed plugin.
- Claude hooks look for `CLAUDE_PLUGIN_DIR` and global fallback directories instead of using the supported plugin-root variable.
- The self-learning workflow offers to promote project lessons into global Claude instructions.
- Codex documentation identifies the repository marketplace but does not clearly prohibit a personal marketplace installation.

These inconsistencies can make Superdev available outside its intended repository and can also make bundled references fail after a normal marketplace install.

## Project-scope contract

Superdev configuration and activation must always be associated with the current repository:

- Claude uses project scope and records configuration in `<project>/.claude/settings.json`.
- Codex discovers Superdev through `<project>/.agents/plugins/marketplace.json`.
- Superdev never creates or edits personal marketplace files, global Claude settings, global Codex settings, or global instruction files.
- Superdev memory remains inside the current repository.
- Commands that cannot identify a project root fail without making changes.

Claude and Codex may internally cache installed plugin files under a user directory. That host-managed cache is an implementation detail and does not change the project-scoped activation contract. Superdev must not manage or treat those cache paths as installation targets.

## Claude installation

The documented non-interactive installation flow will be:

```bash
claude plugin marketplace add boparaiamrit/superdev --scope project
claude plugin install superdev@superdev --scope project
```

Interactive `/plugin` guidance must tell the user to choose **Project scope**, never the default user scope.

`install-superdev.sh` will become a thin project-scoped wrapper around the supported Claude CLI rather than a custom global file installer. It will:

1. Resolve the current Git repository root.
2. Refuse to continue when no repository root can be found.
3. Run marketplace add and plugin install with `--scope project` from that root.
4. Verify that the project settings enable `superdev@superdev` and that Claude lists the plugin.
5. Implement uninstall through `claude plugin uninstall superdev@superdev --scope project`.
6. Store the optional agent-teams environment setting in the project's `.claude/settings.json`.
7. Report the current manifest version and dynamically count bundled skills and agents instead of embedding stale counts.

The script will not extract `superdev.zip`, create `~/.claude/plugins/superdev`, edit `~/.claude/settings.json`, or remove an existing user-scoped installation. Migration documentation will tell users how to remove an older user-scoped install explicitly before using the project-scoped flow.

## Codex installation

Codex support will use only the repository marketplace:

```text
<project>/.agents/plugins/marketplace.json
<project>/plugins/superdev/
```

Documentation will explain that the marketplace and plugin directory belong in the target repository. Users open the Codex plugin browser from that repository, select the repo marketplace, install Superdev, and start a new session.

No Superdev instructions will recommend `~/.agents/plugins/marketplace.json`, `~/.codex/plugins`, or another personal installation surface. The existing repo marketplace entry remains local, uses a `./`-prefixed source path, and stays inside the marketplace root.

## Portable bundled paths

Bundled instructions will no longer assume a global `~/.claude/skills` tree.

- Prose references in a skill use paths relative to that skill, such as `references/environment-checklist.md`.
- Prose references in an agent use repository/plugin-relative links such as `../skills/systematic-debugging/references/repro-recipes.md`.
- Shell commands that must resolve a bundled executable use `${CLAUDE_PLUGIN_ROOT}`.
- Hook commands use `${CLAUDE_PLUGIN_ROOT}` directly and do not scan global cache or legacy plugin directories.

Claude substitutes `${CLAUDE_PLUGIN_ROOT}` in plugin content and exports it to hooks. Codex provides the same variable for compatibility with Claude plugins, so executable paths remain portable across both hosts.

Duplicated role-prompt references under `skills/*/references/` will be updated together with their source agent files so regenerated or copied prompts do not reintroduce global paths.

## Project-only memory

The self-learning workflow will remain repository-local:

- Claude-hosted projects use `.claude/memory/superdev-learned/`.
- Codex-hosted projects use `.superdev/memory/superdev-learned/` unless the repository deliberately preserves the Claude memory directory.
- Durable Claude lessons may be appended only to the current repository's `CLAUDE.md`.
- Global lesson instructions and writes to `~/.claude/CLAUDE.md` will be removed.

Superdev will not offer or automate promotion of a lesson to a global instruction file.

## Documentation surfaces

The project-scope rule will be made consistent in:

- `README.md`
- `INSTALL.md`
- `CODEX.md`
- `plugins/superdev/README.md`
- installer help and success output
- Claude and Codex marketplace guidance
- self-learning documentation and role prompts

References to “install anywhere,” global installation, “every project,” personal marketplaces, and stale bundle counts will be removed or rewritten. Uses of “global” that describe unrelated application behavior, such as a database global scope or globally registered framework middleware, remain unchanged.

## Error handling and migration

The installer must fail before invoking Claude when:

- the `claude` executable is unavailable;
- the current directory is not inside a Git repository;
- the detected project root is not writable; or
- a required project-scoped Claude command fails.

Existing user-scoped installs are not silently removed because that changes state outside the current project. Migration documentation will provide an explicit user-scope uninstall command and then the project-scope install commands.

Installer JSON edits must preserve unrelated project settings. Invalid project settings are reported as an error rather than replaced with an empty file.

## Testing

A standard-library Python regression suite will enforce the contract without requiring Claude or Codex to be installed.

Static tests will assert that Superdev-owned installation and runtime files contain none of the following:

- `~/.claude/skills`
- `~/.claude/plugins/superdev`
- writes to `~/.claude/settings.json`
- writes to `~/.claude/CLAUDE.md`
- `CLAUDE_PLUGIN_DIR`
- personal Codex marketplace installation guidance

Installer behavior tests will use a temporary Git repository and a fake `claude` executable to verify that install and uninstall commands always include `--scope project`, that the script refuses to run outside a repository, and that optional settings are written only beneath the detected project root.

Repository verification will also include:

- shell syntax checking for `install-superdev.sh`;
- JSON parsing for both marketplace files and both plugin manifests;
- plugin manifest validation;
- exact skill and agent inventory counts; and
- a final repository-wide scan for forbidden global Superdev paths.

## Non-goals

- Removing host-managed plugin caches.
- Automatically deleting a user's existing global installation.
- Changing unrelated uses of framework-level or database-level “global scope.”
- Refactoring Superdev workflows unrelated to installation, path resolution, or project-local memory.
