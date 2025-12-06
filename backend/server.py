from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.runnables import RunnableConfig
import logging
import traceback
from typing import Optional

# Optional Selenium utilities (only used if your LangGraph workflow needs a live browser)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


def create_chrome_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    chromedriver_log = "/tmp/chromedriver.log"
    try:
        service = Service(ChromeDriverManager().install(), log_path=chromedriver_log)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception:
        logging.exception("Failed to start Chrome WebDriver. See chromedriver log at %s", chromedriver_log)
        try:
            with open(chromedriver_log, "r", encoding="utf-8", errors="ignore") as f:
                logging.error("chromedriver log:\n%s", f.read())
        except Exception:
            logging.error("Could not read chromedriver log %s", chromedriver_log)
        raise


# Try to import your LangGraph workflow (expected to be provided as `main.py` with `app` defined)
lang_app = None
fetch_page_fn = None
extract_xpaths_fn = None
generate_code_fn = None
try:
    # Try importing workflow functions from backend.main
    from main import app as lang_app  # type: ignore
    try:
        from main import fetch_page, extract_xpaths, generate_code  # type: ignore
        fetch_page_fn = fetch_page
        extract_xpaths_fn = extract_xpaths
        generate_code_fn = generate_code
    except Exception:
        # functions may live under backend.main instead
        pass
except Exception:
    try:
        # import as package module (backend.main)
        from backend.main import app as lang_app  # type: ignore
        from backend.main import fetch_page, extract_xpaths, generate_code  # type: ignore
        fetch_page_fn = fetch_page
        extract_xpaths_fn = extract_xpaths
        generate_code_fn = generate_code
    except Exception as e:
        logging.warning("Could not import 'main' or 'backend.main' workflow. Trace:\n%s", traceback.format_exc())
        lang_app = None


class GenerateRequest(BaseModel):
    url: Optional[str] = None
    selectedLanguage: Optional[str] = "Java"
    selectedTool: Optional[str] = "Selenium"
    testCase: Optional[str] = ""
    testData: Optional[str] = ""
    testSteps: Optional[str] = ""


app = FastAPI(title="Automation Code Generator API")

# Allow CORS from frontend during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "lang_app_available": lang_app is not None}


@app.post("/generate")
async def generate(req: GenerateRequest):
    inputs = req.dict()

    try:
        if lang_app is not None and fetch_page_fn and extract_xpaths_fn and generate_code_fn:
            # Run the workflow functions directly in sequence to avoid depending on app.invoke semantics
            state = dict(inputs)
            # fetch_page will start webdriver and store driver into state
            state = fetch_page_fn(state)
            # extract xpaths and quit driver
            state = extract_xpaths_fn(state)
            # generate code using llm and extracted xpaths
            state = generate_code_fn(state)

            generated = state.get("generated_code") or state.get("generated") or state.get("result")
            xpaths = state.get("xpaths") or state.get("extracted_xpaths") or state.get("extracted")
            return {"generated_code": generated, "extracted_xpaths": xpaths}
        elif lang_app is not None:
            # Fallback to invoking the runnable-like object if available
            result = None
            try:
                result = lang_app.invoke(inputs, config=RunnableConfig())
            except Exception:
                # Some runnable implementations accept a simple function call
                try:
                    result = lang_app(inputs)
                except Exception:
                    logging.exception("Failed to invoke lang_app via known patterns")

            if isinstance(result, dict):
                return result
            else:
                return {"generated_code": str(result)}
        else:
            # Fallback/mock generation so frontend works without LangGraph
            logging.info("LangGraph app not available — using mock generator")
            # Simple mock generation
            lang = (inputs.get("selectedLanguage") or "Java").lower()
            tool = inputs.get("selectedTool") or "Selenium"
            test_case = inputs.get("testCase") or "GeneratedTest"
            url = inputs.get("url") or "https://example.com"

            if lang == "java":
                code = f"// Auto-generated {tool} test ({test_case})\nimport org.openqa.selenium.WebDriver;\n// Navigate to {url}\n"
            elif lang == "python":
                code = f"# Auto-generated {tool} test ({test_case})\nfrom selenium import webdriver\n# Navigate to {url}\n"
            elif lang == "javascript":
                code = f"// Auto-generated {tool} test ({test_case})\n// Use Playwright or Puppeteer to navigate to {url}\n"
            else:
                code = f"// Auto-generated test ({test_case}) for {tool} - navigate to {url}\n"

            # Provide a few mock xpaths extracted from common fields
            extracted = [
                {"tag": "input", "attribute": "id", "value": "username", "variable_name": "username_input", "xpath": "//input[@id=\'username\']"},
                {"tag": "input", "attribute": "id", "value": "password", "variable_name": "password_input", "xpath": "//input[@id=\'password\']"},
                {"tag": "button", "attribute": "id", "value": "login", "variable_name": "login_button", "xpath": "//button[@id=\'login\']"},
            ]

            return {"generated_code": code, "extracted_xpaths": extracted}

    except Exception as e:
        logging.exception("Error invoking LangGraph workflow or mock generator")
        raise HTTPException(status_code=500, detail=str(e))
