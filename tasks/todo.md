# ATMP Setup Tracker

## Plan

- [x] Clone current `harry0703/MoneyPrinterTurbo` into `C:\ATMP`.
- [x] Rename the public GitHub remote to fetch-only `upstream`.
- [x] Create private GitHub repo `auronpep/ATMP` and verify it is private before any push.
- [x] Add Codex project setup files and task tracker.
- [x] Push the private baseline to `origin`.
- [x] Install dependencies using the repository-recommended `uv sync --frozen` path.
- [x] Create local runtime config from `config.example.toml`.
- [x] Run focused smoke tests and import checks.
- [x] Start the Web UI and verify the local page responds.
- [x] Start the API service and verify docs or health response.

## Notes

- Public source: `https://github.com/harry0703/MoneyPrinterTurbo.git`
- Private origin: `https://github.com/auronpep/ATMP.git`
- Public upstream push URL: `DISABLED`
- Upstream clone commit: `83f88fe2d8e7c4caf755e357fe19bb8e0edc23ec`
- Codex CLI verified locally with `codex --version`, `codex --help`, `codex exec --help`, `codex review --help`, and `codex mcp list`.
- Private origin verified `PRIVATE`; local and remote `main` matched at `a41770f6dbf048e0c2b8e0914f78185ef94905ac` after the initial push.
- GitHub warned that two upstream blobs are slightly over the recommended 50 MB size, but the private push completed.
- Python 3.11.15 installed under `.local\uv-python`; dependencies installed into `.venv` with `uv sync --frozen`.
- Local ignored `config.toml` was created from `config.example.toml` and points to:
  - `ffmpeg_path = "C:\\Users\\JesusLovesMe\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.exe"`
  - `imagemagick_path = "C:\\Program Files\\ImageMagick-7.1.2-Q16-HDRI\\magick.exe"`
- Verification passed:
  - `uv run python -m compileall -q app webui main.py`
  - `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 uv run python -m unittest discover -s test` -> `51` tests, `3` skipped, `OK`
  - Web UI `http://127.0.0.1:8501` returned HTTP `200`
  - API `http://127.0.0.1:8080/openapi.json` returned HTTP `200`, title `MoneyPrinterTurbo`, version `1.2.8`

## Review

- Complete. Current local services are running from `C:\ATMP`; logs are under `C:\ATMP\logs`.
- Web UI listener: `127.0.0.1:8501`
- API listener: `0.0.0.0:8080`
- Full video generation will still require real provider keys in ignored `config.toml`, especially material-source keys such as Pexels or Pixabay and an LLM provider key unless a local/providerless route is selected.

## Collaborator Admin Setup

- [x] Verify `auronpep/ATMP` is still private before collaborator writes.
- [x] Add `erewhonsgroup` with `admin` permission.
- [x] Add `votewood` with `admin` permission.
- [x] Add `JWoodMedia` with `admin` permission.
- [x] Verify active collaborators and pending invitations separately.

### Collaborator Verification

- Repo privacy check: `auronpep/ATMP` reports `visibility=PRIVATE`, `isPrivate=true`, and current viewer permission `ADMIN`.
- Active collaborators currently include only `auronpep`; the three new accounts have not accepted yet.
- Pending, non-expired admin invitations created on `2026-05-30T05:48:44Z`:
  - `erewhonsgroup`, invitation id `320648154`, permission `admin`
  - `VoteWood`, invitation id `320648155`, permission `admin`
  - `JWoodMedia`, invitation id `320648156`, permission `admin`

## CI Pipeline Hardening

- [x] Add GitHub Actions CI workflow.
- [x] Add local CI runner script.
- [x] Add Git pipeline guide.
- [x] Run local CI-equivalent verification.
- [x] Push CI setup to private origin.
- [x] Try to configure `main` branch protection or document the GitHub plan limitation.
- [x] Verify the pushed workflow and final GitHub state.

### Local CI Verification

- `pwsh -NoProfile -File C:\ATMP\scripts\Run-CI.ps1` passed.
- Steps covered: `uv sync --frozen`, Python `3.11.15`, compile check for `app`, `webui`, and `main.py`, and `python -m unittest discover -s test`.
- Test result: `51` tests run, `3` skipped, `OK`.

### GitHub CI Verification

- Initial workflow run `26677189313` failed before project checks because `astral-sh/setup-uv@v8` did not resolve as a major tag.
- Workflow actions were pinned to exact tags verified through GitHub API:
  - `actions/checkout@v6.0.2`
  - `actions/setup-python@v6.2.0`
  - `astral-sh/setup-uv@v8.1.0`
- Follow-up workflow run `26677208376` passed on GitHub Actions; job `ci` completed successfully in about `1m27s`.
- Classic branch protection and repository rulesets both returned GitHub `403`: `Upgrade to GitHub Pro or make this repository public to enable this feature.`
- Until the GitHub plan supports enforcement, the team rule is: open PRs into `main` and require the `CI / ci` workflow result by practice.
