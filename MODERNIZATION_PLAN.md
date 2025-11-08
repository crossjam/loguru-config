# Modernization Plan

## 1. Adopt uv-based project configuration with setuptools backend
Replace the existing packaging setup with a uv-driven `pyproject.toml` that still delegates builds to setuptools, migrate dependency declarations, and add Python 3.11+ requirement plus uv lockfile/bootstrap instructions (touching `pyproject.toml`, `README.md`, and removing or demoting `setup.py`, `tox.ini`).

:::task-stub{title="Adopt uv-based project configuration with setuptools backend"}
- Create `pyproject.toml` at the repository root containing `[project]` metadata migrated from `setup.py`, `python = ">=3.11"`, runtime dependencies (for example, `loguru`), and test dependencies in `project.optional-dependencies` or uv groups.
- Configure `[build-system]` to use `setuptools.build_meta` and include minimal setuptools/wheel versions.
- Add `[tool.uv]` settings for dependency groups/tests and generate `uv.lock`.
- Update `README.md` usage/development instructions to reference uv commands (`uv sync`, `uv run pytest`), removing outdated tox/pip guidance.
- Decide whether to delete `setup.py`/`tox.ini` or keep thin wrappers pointing to the new configuration; adjust packaging classifiers for supported Python versions.
:::

## 2. Migrate TOML handling to tomlkit
Swap the TOML parser from `toml` to `tomlkit`, ensuring the loader returns plain `dict` objects and updating tests/fixtures accordingly (touching `loguru_config/utils/loaders.py` and any TOML-centric tests under `tests/`).

:::task-stub{title="Migrate TOML handling to tomlkit"}
- Update `loguru_config/utils/loaders.py` to import `tomlkit` and parse strings with `tomlkit.parse`, converting the resulting document to a native dict (for example, `dict(tomlkit.parse(...))` or `tomlkit.loads(...))` while preserving nested structures.
- Adjust any doctests or fixtures that rely on `toml` behaviors (such as ordering or comments) to match tomlkit outputs.
- Update test assertions in `tests/` to handle tomlkit return types (ensuring comparisons use dicts).
- Pin `tomlkit` as a runtime dependency in the new project metadata and remove the old `toml` dependency if present.
:::

## 3. Refresh testing workflow for uv and Python 3.11+
Align continuous testing and metadata with the new tooling and Python floor (touching CI configs if present, docs).

:::task-stub{title="Refresh testing workflow for uv and Python 3.11+"}
- Replace tox-driven or legacy CI instructions with uv equivalents (for example, `uv run pytest`), updating any CI configuration files or badges if applicable.
- Ensure tests run under Python 3.11 in local instructions/CI matrix; drop references to unsupported versions.
- Verify README badges or status indicators reflect the new toolchain and supported versions.
:::
