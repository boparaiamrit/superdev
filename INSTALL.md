# superdev installer

This bundle contains the superdev plugin for Claude Code plus an installer script.

## Quick install (Linux / macOS / WSL)

```bash
bash install-superdev.sh
```

That's it. The installer:
- Verifies prerequisites (Claude Code, Python 3, unzip)
- Extracts the plugin to ~/.claude/plugins/superdev/
- Registers it in ~/.claude/settings.json so it loads in every Claude Code session
- Validates the install

## Optional: enable agent teams

After install:

```bash
bash install-superdev.sh --enable-teams
```

Enables 3-teammate adversarial reviews (security, QA, gap audits). ~3× tokens. High-stakes work only.

## Other commands

```bash
bash install-superdev.sh --verify       # check current install
bash install-superdev.sh --uninstall    # remove
bash install-superdev.sh --help         # full options
```

## WSL specifically

- Run the installer inside your WSL distro, NOT Windows PowerShell.
- Claude Code itself must also be installed inside WSL.
- If you downloaded these files on Windows, copy them into WSL first:
  ```bash
  cp /mnt/c/Users/YOUR_NAME/Downloads/{install-superdev.sh,superdev.zip} ~/
  cd ~
  bash install-superdev.sh
  ```

## Files in this bundle

- `install-superdev.sh` — the installer (~20 KB bash script)
- `superdev.zip` — the plugin (~388 KB, 96 files: 6 skills + 24 agents + hooks)
- `INSTALL.md` — this file
