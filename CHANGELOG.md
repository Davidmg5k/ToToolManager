# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.9.6] - 2026-11-03

First release published to PyPI as `to-tool-manager`.

### Added

- `BaseAgent` (`to_tool_manager.util.base_agent`) — abstract base class that hides the `TTMBuilder`
  lifecycle behind a two-step construct → `init_agent()` flow, so a concrete agent is defined by a
  single `_composer()` hook.
- `TTMBuilder.add_sub_agent()` — register an already-built `Agent` on the parent's roster for
  delegation by name.
- `Dependency` (`to_tool_manager.core.main.shared.dependency`) — dynamic attribute-bag container for
  service instances. It replaces the previous `DinamicDepend` class; the name survives only in the
  legacy `DependencyNotSetError` message.
- Contract tests covering the optional `fastmcp` dependency group.

### Changed

- `pydantic-ai-slim` is now installed without the optional `openai` extra, shrinking the install
  surface for consumers that do not use OpenAI. Install your provider explicitly, e.g.
  `pip install "pydantic-ai-slim[openai]"`.
- `FastMCPNotInstalledError` message states explicitly that `TTMBuilder.to_mcp_tool()` requires the
  server side of the `fastmcp` group, while the rest of the package keeps working without it.
- `HumanInTheLoopToolMiddleware` accepts its HITL parameters keyword-only.
- Type hints tightened across the builder and middleware modules; `pytest-asyncio` added to the dev
  dependency group.

### Fixed

- Sub-agent registration now forwards the built `Agent` directly and raises a typed error when a
  delegate name is missing from the roster.
- Example application stores timezone-aware datetimes, so chat session endpoints no longer return
  HTTP 500 (`Datetime values must have timezone information`).
- README quickstart runs on a fresh install: it now uses pydantic-ai's built-in test model instead of
  `openai:gpt-4o`, which required a provider package this distribution does not ship.

### Notes for consumers

- `fastmcp` remains a PEP 735 dependency group and is **never** installed by
  `pip install to-tool-manager`. Install it explicitly (`uv add "fastmcp>=4.0.9"`) only if you use
  `TTMBuilder.to_mcp_tool()`.
- No model provider package is installed by default. `to-tool-manager` only declares
  `pydantic-ai-slim[cli]`; install the extra for the provider you actually use.
- `cryptography>=50.0.0` is pinned as a transitive override to pick up the PYSEC-2026-3552 fix
  (Bleichenbacher oracle) regardless of what the auth stack resolves to.

[Unreleased]: https://github.com/Davidmg5k/ToToolManager/compare/v0.9.6...HEAD
[0.9.6]: https://github.com/Davidmg5k/ToToolManager/releases/tag/v0.9.6
