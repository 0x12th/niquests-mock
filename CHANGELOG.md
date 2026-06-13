# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 0.4.0 - 2026-06-13

### Added

- Documented strict mode, pass-through, matching precedence, side effects, async usage, concurrency semantics, release workflow, and RESPX compatibility notes.
- Added regression coverage for router lifecycle, pass-through, diagnostics redaction, marker validation, async side effects, async task context behavior, thread behavior, query/header matching edge cases, and `niquests` runtime compatibility.
- Added PyPI smoke workflow and release-time smoke verification for published packages.
- Added a `CONTRIBUTING.md` release playbook with recovery steps for failed publishes and GitHub Releases.
- Included examples in test/typecheck validation.

### Changed

- Hardened router patch lifecycle with explicit patch-depth/state guards.
- Moved response construction helpers into a dedicated internal module while preserving the public `build_response` export.
- Extracted diagnostic summary helpers into a dedicated internal module.
- Tightened async side-effect typing.

### Fixed

- Redacted sensitive header, query param, body, and JSON matcher details from assertion and route diagnostics.
- Unknown `niquests_mock` pytest marker keyword arguments now fail early with `pytest.UsageError`.
