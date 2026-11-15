# Installing superdev

Superdev is installed for one project at a time, never at user scope.

## Claude Code

From the target Git project:

```bash
claude plugin marketplace add boparaiamrit/superdev --scope project
claude plugin install superdev@superdev --scope project
```

In the interactive `/plugin` browser, choose **Project scope** when installing.

## Which project to install it in

A build needs what Navree needs (Rust, a C compiler, and Docker or Podman for a local TimescaleDB or PostgreSQL database; see the [README's requirements](README.md#requirements)) and the Navree CLI: `cargo install navree-cli`, then `navree --version` prints its version.

- **You already have a Navree app.** The app's root is a Git project; install superdev there, start Claude Code there and ask for the build. Step 1 of the build records the app in `STACK.md` instead of creating one.
- **You are starting a new product.** `navree new` creates the app in a folder that must be missing or empty, so superdev cannot be installed in the app before it exists:
  1. Put the PRD and the design files in a folder of their own, run `git init` there (the install needs a Git project), and install superdev in it.
  2. Start Claude Code in that folder and ask for the build. Step 1 agrees the `navree new` line with you and runs it there, which creates the app as a subfolder. `navree new` makes a folder a repository only outside an existing one, so step 1 runs `git init` in the app and adds the app's folder to the brief folder's `.gitignore`: the app is a repository of its own. If you start inside a repository that holds other code, step 1 first asks whether to track the app there or give it its own repository. Step 1 then installs Navree's skills and superdev in the app and copies the PRD and the design into its `docs/brief/`.
  3. Open every later session of the build in the app's folder; the build resumes from its `STACK.md` and `EXECUTION_PLAN.md`.

## Helper script

From the target project:

```bash
bash /path/to/superdev/install-superdev.sh              # add the marketplace and install at project scope
bash /path/to/superdev/install-superdev.sh --verify     # check the project-scoped install
bash /path/to/superdev/install-superdev.sh --uninstall  # remove superdev from the project
```

The helper needs Claude Code, Git and Python 3, refuses to run outside a Git project, and never writes to user or personal settings.

## Moving a user-scope install

Removing superdev from user scope changes configuration outside the project, so it is a separate, explicit command:

```bash
claude plugin uninstall superdev@superdev --scope user
claude plugin marketplace add boparaiamrit/superdev --scope project
claude plugin install superdev@superdev --scope project
```

## Codex

Keep these in the target project:

```text
.agents/plugins/marketplace.json
plugins/superdev/
```

Start Codex in that project, open `/plugins`, choose **Superdev Local**, install Superdev and start a new session. Do not add superdev to a personal marketplace. For a new product, step 1 of the build copies both into the app it creates. [CODEX.md](CODEX.md) describes how Codex uses it.

## Version 2.1.0 for NestJS and Laravel projects

Version 2.1.0 remains the version for NestJS and Laravel projects. Install it in such a project with:

```bash
claude plugin marketplace add boparaiamrit/superdev#v2.1.0 --scope project
claude plugin install superdev@superdev --scope project
```

A project that already uses 2.1.0 added the marketplace without a pin, under the same names, so an update or a teammate's fresh install would bring 3.0.0. Pin it to 2.1.0: uninstall superdev from the project as the helper's `--uninstall` does, then add the pinned marketplace and install again:

```bash
claude plugin uninstall superdev@superdev --scope project
claude plugin marketplace add boparaiamrit/superdev#v2.1.0 --scope project
claude plugin install superdev@superdev --scope project
```

If `marketplace add` answers that the `superdev` marketplace already exists, remove it in the interactive `/plugin` browser (its marketplaces list) and run the last two lines again.
