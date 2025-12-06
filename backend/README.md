# Automation Code Generator — Backend

This backend exposes a simple HTTP API that wraps your LangGraph workflow (expected to be exported as `app` in `main.py`). It provides `/generate` for generating automation code programmatically.

Quick start

1. Create a virtual environment and install dependencies:

```powershell
cd my-app\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Place your LangGraph workflow file `main.py` next to `server.py`. It must expose a runnable named `app` (as in `from main import app`).

3. Run the backend:

```powershell
uvicorn backend.server:app --reload --port 8000
```

4. Example request (curl):

```powershell
curl -X POST http://localhost:8000/generate -H "Content-Type: application/json" -d "{ \"url\": \"https://example.com\", \"selectedLanguage\": \"Java\", \"selectedTool\": \"Selenium\", \"testCase\": \"Login\" }"
```

Notes
- The server attempts to import `main.app`. If the import fails the `/generate` endpoint will return a 500 error.
- If your LangGraph workflow expects a live browser, you can uncomment and use `create_chrome_driver()` inside `server.py` (make sure Chrome/Chromium + chromedriver are available on the host).
