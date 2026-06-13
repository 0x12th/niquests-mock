# Contributing

## Development

Install development dependencies and run the full local check before opening a PR or cutting a release:

```bash
uv sync --dev
just check
```

`just check` runs linting, formatting checks, type checking, and tests for `tests` and `examples`.

## Release Playbook

This project releases through the manual GitHub Actions `Release` workflow.

### Normal release

1. Confirm `main`/`master` is green in CI.
2. Confirm `CHANGELOG.md` has the intended user-facing notes under `Unreleased`.
3. Run the `Release` workflow manually and choose `patch`, `minor`, or `major`.
4. Wait for all jobs to pass:
   - version bump commit and tag creation;
   - lint, format, typecheck, tests, and build;
   - PyPI publish;
   - installed-package smoke test;
   - GitHub Release creation.
5. Verify the published package manually if needed:

   ```bash
   python -m venv smoke-venv
   smoke-venv/bin/python -m pip install --upgrade pip
   smoke-venv/bin/python -m pip install niquests-mock
   smoke-venv/bin/python -c "import niquests_mock; print(niquests_mock.__all__)"
   ```

### Recovery: tag pushed, PyPI publish failed

The current workflow pushes the release commit and tag before publishing to PyPI. If the
`publish` job fails after the tag exists, use this recovery path.

1. Check whether the package version exists on PyPI.
   - If the version exists and the smoke test failed, fix the smoke issue or rerun the
     failed job if the artifact is correct.
   - If the version does not exist, continue below.
2. Inspect the failure reason:
   - transient PyPI/network/OIDC issue: rerun the failed `publish` job;
   - invalid artifact or package metadata: do not rerun blindly; fix the source and cut
     a new release version.
3. If the tag points to a bad artifact source, delete the remote tag before cutting a
   replacement release:

   ```bash
   git push origin --delete vX.Y.Z
   git tag -d vX.Y.Z
   ```

4. Revert or supersede the release commit if the version should not remain on the main
   branch.
5. Cut a new patch release after the fix. Do not reuse a version that has already been
   accepted by PyPI.

### Recovery: GitHub Release creation failed

If PyPI publish and smoke test passed but GitHub Release creation failed:

1. Rerun the failed job when possible.
2. If rerun is not available, create the GitHub Release manually from the existing tag.
3. Attach the `dist/*.tar.gz` and `dist/*.whl` artifacts from the workflow run if they
   are still available.

### Version and changelog policy

- PyPI versions are immutable. Once a version is published, fix forward with a new
  patch release.
- Keep `CHANGELOG.md` aligned with user-visible changes before running the release.
- GitHub generated release notes are useful, but they should not be the only source of
  curated user-facing release information.

### Manual TestPyPI smoke

Use the existing TestPyPI workflow before risky packaging changes. After publishing to
TestPyPI, install from TestPyPI in a clean environment and run a minimal import/router
smoke test.
