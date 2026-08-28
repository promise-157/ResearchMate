# Native Linux desktop host

The native Linux delivery reuses the existing Vue/FastAPI application and
`src/backend/desktop_runtime.py`. A small system-Python GTK 3/WebKitGTK host owns the exact backend process group;
closing its only window requests graceful shutdown and escalates only that owned group when necessary.

It requires user-installed system Python 3, PyGObject, GTK 3 and WebKitGTK 4.1 or 4.0 introspection data. The
transparent setup does not install or remove those packages, the user's Conda-compatible environment, Node,
Tesseract, source or workspaces.

From the repository root:

```bash
python3 packaging/linux/setup_researchmate.py --mode check \
  --conda /absolute/path/to/conda
python3 packaging/linux/setup_researchmate.py --mode plan \
  --conda /absolute/path/to/conda
```

Review the ignored `researchmate-linux-install-plan.json`, then run:

```bash
python3 packaging/linux/setup_researchmate.py --mode apply
```

This installs only user-scoped files under XDG directories plus `~/.local/bin/researchmate`. Run `researchmate`
or select ResearchMate from the desktop application menu. The installed manifest lists every owned path and every
external dependency that uninstall preserves.

To uninstall, first close the window, then run the installed `uninstall_researchmate.py`. Pass
`--remove-local-state` only to remove Linux desktop logs and runtime cache as well.
