# Publishing MemOps

This file documents the minimum release flow for publishing `memops` to PyPI.

## Before First Publish

1. Make sure the package metadata in `pyproject.toml` is correct:
   - `name`
   - `version`
   - `description`
   - `authors`
   - `project.urls`
   - `classifiers`
2. Make sure `README.md` renders correctly outside the local repo:
   - no local absolute file links
   - banner/image URLs point to public GitHub assets
3. Make sure the CLI entrypoint is the intended one:
   - `memops`
4. Confirm the package builds locally.

## Local Release Validation

Build the package:

```bash
uv build
```

This should create:

- `dist/*.tar.gz`
- `dist/*.whl`

Optional local smoke install in a fresh environment:

```bash
uv venv .tmp/publish-venv
source .tmp/publish-venv/bin/activate
uv pip install dist/*.whl
memops --help
```

## PyPI Credentials

For public publishing, create a PyPI account and generate an API token on:

- `https://pypi.org`

Then configure publishing credentials in one of the usual ways, for example:

- `UV_PUBLISH_TOKEN`
- or a PyPI token in your local publish config

## Publish

Once the build artifacts look correct:

```bash
uv publish
```

If you want to test the flow first without publishing to the real public index, use TestPyPI instead:

```bash
uv publish --index testpypi
```

## After Publish

Verify:

1. the project page renders correctly on PyPI
2. the README formatting looks right
3. `memops --help` works after a clean install
4. the listed homepage/repository/issues links resolve correctly

## Versioning Rule

Every public release should:

1. bump `version` in `pyproject.toml`
2. add a matching entry in `docs/versioning.md`
3. rebuild with `uv build`
4. publish with `uv publish`
