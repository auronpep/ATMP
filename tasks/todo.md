# ATMP Setup Tracker

## Plan

- [x] Clone current `harry0703/MoneyPrinterTurbo` into `C:\ATMP`.
- [x] Rename the public GitHub remote to fetch-only `upstream`.
- [x] Create private GitHub repo `auronpep/ATMP` and verify it is private before any push.
- [x] Add Codex project setup files and task tracker.
- [ ] Push the private baseline to `origin`.
- [ ] Install dependencies using the repository-recommended `uv sync --frozen` path.
- [ ] Create local runtime config from `config.example.toml`.
- [ ] Run focused smoke tests and import checks.
- [ ] Start the Web UI and verify the local page responds.
- [ ] Start the API service and verify docs or health response.

## Notes

- Public source: `https://github.com/harry0703/MoneyPrinterTurbo.git`
- Private origin: `https://github.com/auronpep/ATMP.git`
- Public upstream push URL: `DISABLED`
- Upstream clone commit: `83f88fe2d8e7c4caf755e357fe19bb8e0edc23ec`
- Codex CLI verified locally with `codex --version`, `codex --help`, `codex exec --help`, `codex review --help`, and `codex mcp list`.

## Review

- Pending final install and runtime verification.
