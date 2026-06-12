# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Documented strict mode, pass-through, matching precedence, side effects, async usage, and RESPX compatibility notes in the README.
- Added regression coverage for router lifecycle, pass-through, diagnostics redaction, marker validation, async side effects, query/header matching edge cases, and `niquests` runtime compatibility.
- Added PyPI smoke workflow and release-time smoke verification for published packages.
- Included examples in test/typecheck validation.

### Changed

- Hardened router patch lifecycle with explicit patch-depth/state guards.
- Moved response construction helpers into a dedicated internal module while preserving the public `build_response` export.
- Tightened async side-effect typing.

### Fixed

- Unknown `niquests_mock` pytest marker keyword arguments now fail early with `pytest.UsageError`.
