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
