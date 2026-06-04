---
description: "Use when: facciamo nuovo rilascio, nuova versione, release, publish, pubblica su PyPI. Prepares and publishes a new promptlens release: bump version, run tests, commit, tag and push to trigger the CI/CD pipeline."
name: "New Release"
argument-hint: "New version number (e.g. 0.2.0)"
agent: "agent"
---

You are preparing a new release of the **promptlens** library.

## Context

- Version is defined only in `Cargo.toml` → `[package] version`. `pyproject.toml` reads it dynamically via maturin.
- Pushing a git tag that starts with `v` triggers the GitHub Actions CI, which builds wheels for all platforms and publishes to PyPI automatically.
- Always use `.venv\Scripts\python.exe` directly — never bare `pytest` or `python` (stale venv launchers).
- Git is at `C:\Program Files\Git\bin\git.exe` if not in PATH.

## Steps

### 1. Determine the new version

If the user provided a version as argument, use it. Otherwise read the current version from `Cargo.toml` and ask the user whether the next release is a patch (Z), minor (Y) or major (X) bump, then compute the new version accordingly.

Current version is in:
[Cargo.toml](../../Cargo.toml)

### 2. Run the full test suite

Run all tests with DeprecationWarning promoted to errors:

```
.venv\Scripts\python.exe -m pytest tests/ -W error::DeprecationWarning -q
```

If any test fails, **stop** and report the failure. Do not proceed with the release until all tests pass.

### 3. Bump the version in Cargo.toml

Update the `version` field under `[package]` in `Cargo.toml` to the new version.

### 4. Rebuild the Rust module

```
maturin develop
```

This ensures the new version is reflected in the installed package.

### 5. Commit the version bump

```
git add Cargo.toml
git commit -m "chore: bump version to X.Y.Z"
git push
```

### 6. Create and push the tag

```
git tag vX.Y.Z
git push origin vX.Y.Z
```

The tag push triggers the CI/CD pipeline, which builds wheels for all platforms and publishes `promptlens X.Y.Z` to PyPI.

### 7. Report

Summarize what was done:
- New version released
- Tag pushed
- Link to the CI run: `https://github.com/marco-scarnato/promptlens/actions`
- Link to PyPI: `https://pypi.org/project/promptlens/`
