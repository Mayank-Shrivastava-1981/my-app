import re
import os
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

load_dotenv()


# =====================================================
# XPath + Element Intelligence Utility
# =====================================================
class Xpath_Util:

    def __init__(self):
        self.known_attribute_list = [
            "id", "name", "aria-label",
            "placeholder", "data-testid",
            "role", "type"
        ]

        self.skip_tags = {
            "script", "style", "meta",
            "link", "noscript", "svg", "path"
        }

        self.xpath_collection = []

    # ---------------- Element Classification ----------------
    def classify_element(self, tag, element_type, role):
        if tag == "input" and element_type in ["text", "email", "search"]:
            return "TEXTBOX"
        if tag == "input" and element_type == "password":
            return "PASSWORD"
        if tag == "input" and element_type == "checkbox":
            return "CHECKBOX"
        if tag == "input" and element_type == "radio":
            return "RADIO"
        if tag == "button":
            return "BUTTON"
        if tag == "a":
            return "LINK"
        if tag == "select":
            return "DROPDOWN_NATIVE"
        if role == "combobox":
            return "DROPDOWN_CUSTOM"
        return "GENERIC"

    def is_interactive(self, tag, element_type, role, element=None):
        # Common interactive tags
        if tag in ["input", "button", "select", "textarea", "a"]:
            return True

        # Common ARIA roles that imply interactivity
        interactive_roles = [
            "button", "textbox", "combobox", "checkbox",
            "radio", "link", "menuitem", "option", "tab", "menu"
        ]
        if role and role.lower() in interactive_roles:
            return True

        # Inspect element attributes that often indicate interactivity
        if element is not None:
            try:
                onclick = element.get_attribute("onclick")
                tabindex = element.get_attribute("tabindex")
                href = element.get_attribute("href")
                if onclick:
                    return True
                if href:
                    return True
                if tabindex and tabindex.strip() != "-1":
                    return True
            except Exception:
                pass

        return False

    # ---------------- Locator Strategy ----------------
    def determine_best_locator(self, tag, attr, value):
        if attr == "id":
            return {"type": "id", "value": value}
        if attr == "name":
            return {"type": "name", "value": value}
        if attr == "aria-label":
            return {
                "type": "css",
                "value": f"{tag}[aria-label='{value}']"
            }
        return {
            "type": "xpath",
            "value": f"//{tag}[@{attr}='{value}']"
        }

    # ---------------- XPath Generators ----------------
    def generate_xpath(self, driver):
        elements = driver.find_elements(By.XPATH, "//*")

        for element in elements:
            try:
                tag = element.tag_name.lower()
                if tag in self.skip_tags:
                    continue

                element_type = element.get_attribute("type")
                role = element.get_attribute("role")
                # Pass the element so we can inspect attributes like onclick/tabindex
                if not self.is_interactive(tag, element_type, role, element):
                    continue

                category = self.classify_element(tag, element_type, role)
                text = self._clean_text(element.text)

                # 1️⃣ Attribute based (highest priority)
                xpath = self._attribute_xpath(driver, element, tag)
                if xpath:
                    self._store(element, tag, category, xpath)
                    continue

                # 2️⃣ text()
                if text:
                    text_xpath = f"//{tag}[text()='{text}']"
                    if self._is_xpath_unique(driver, text_xpath):
                        self._store(element, tag, category, text_xpath)
                        continue

                    contains_xpath = f"//{tag}[contains(text(),'{text[:20]}')]"
                    if self._is_xpath_unique(driver, contains_xpath):
                        self._store(element, tag, category, contains_xpath)
                        continue

                # 3️⃣ XPath Axes (fallback)
                axes_xpath = self._axes_xpath(driver, element, tag)
                if axes_xpath:
                    self._store(element, tag, category, axes_xpath)

            except Exception as e:
                print(f"⚠️ Error processing element: {e}")

    # ---------------- XPath Helpers ----------------
    def _attribute_xpath(self, driver, element, tag):
        for attr in self.known_attribute_list:
            value = element.get_attribute(attr)
            if value and not self._is_auto_generated(value):
                xpath = f"//{tag}[@{attr}='{value}']"
                if self._is_xpath_unique(driver, xpath):
                    return xpath
        return None

    def _axes_xpath(self, driver, element, tag):
        try:
            parent = element.find_element(By.XPATH, "..")
            parent_tag = parent.tag_name.lower()

            xpath = f"//{parent_tag}//{tag}"
            if self._is_xpath_unique(driver, xpath):
                return xpath

            following = element.find_elements(By.XPATH, "following-sibling::*")
            if following:
                sib_tag = following[0].tag_name.lower()
                xpath = f"//{sib_tag}/preceding-sibling::{tag}"
                if self._is_xpath_unique(driver, xpath):
                    return xpath

            preceding = element.find_elements(By.XPATH, "preceding-sibling::*")
            if preceding:
                sib_tag = preceding[0].tag_name.lower()
                xpath = f"//{sib_tag}/following-sibling::{tag}"
                if self._is_xpath_unique(driver, xpath):
                    return xpath

        except Exception:
            pass
        return None

    def _store(self, element, tag, category, xpath):
        self.xpath_collection.append({
            "tag": tag,
            "category": category,
            "xpath": xpath,
            "variable_name": self._generate_variable_name(tag, xpath),
            "is_enabled": element.is_enabled(),
            "is_displayed": element.is_displayed()
        })

    def _is_xpath_unique(self, driver, xpath):
        return len(driver.find_elements(By.XPATH, xpath)) == 1

    def _is_auto_generated(self, value):
        return bool(re.search(r"\b\w{6,}\d+\w*\b", value))

    def _clean_text(self, text):
        text = re.sub(r"\s+", " ", text).strip()
        return text if 0 < len(text) <= 60 else None

    def _generate_variable_name(self, tag, xpath):
        name = re.sub(r"[^a-zA-Z0-9]+", "_", xpath.lower())
        return f"{tag}_{name[-30:]}"


# =====================================================
# LangGraph Nodes
# =====================================================
def fetch_page(state):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    if state.get("url"):
        driver.get(state["url"])
    else:
        raise ValueError("URL must be provided")

    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    state["driver"] = driver
    return state


def extract_xpaths(state):
    driver = state["driver"]
    util = Xpath_Util()
    util.generate_xpath(driver)
    driver.quit()

    state["xpaths"] = util.xpath_collection
    return state


def generate_code(state):
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.1,
        api_key=os.getenv("OPENAI_API_KEY")
    )

    selectedLanguage = state.get("selectedLanguage", "Java")
    selectedTool = state.get("selectedTool", "Selenium")
    testCase = state.get("testCase", "")
    testData = state.get("testData", "")
    url = state.get("url", "")
    testSteps = state.get("testSteps", "")
    # Filter extracted xpaths to only those referenced in the test steps/case/data
    all_xpaths = state.get("xpaths", [])
    search_text = " ".join([
        str(state.get("testCase", "")),
        str(state.get("testSteps", "")),
        str(state.get("testData", "")),
        str(state.get("url", ""))
    ]).lower()

    def _element_matches_in_steps(el, haystack):
        # Match by variable name, category, full xpath or tokens from variable_name
        try:
            name = (el.get("variable_name") or "").lower()
            cat = (el.get("category") or "").lower()
            xp = (el.get("xpath") or "").lower()

            if name and name in haystack:
                return True
            if cat and cat in haystack:
                return True
            if xp and xp in haystack:
                return True

            # check for text() or contains(...) values inside xpath
            m = re.search(r"text\(\)='([^']+)'", xp)
            if m and m.group(1).strip().lower() in haystack:
                return True
            m2 = re.search(r"contains\(text\(\),'([^']+)'\)", xp)
            if m2 and m2.group(1).strip().lower() in haystack:
                return True

            # tokens from variable name
            tokens = re.findall(r"[a-zA-Z]{3,}", name)
            for t in tokens:
                if t in haystack:
                    return True
        except Exception:
            pass
        return False

    matched = [el for el in all_xpaths if _element_matches_in_steps(el, search_text)]

    # Expose matched set for frontend convenience; also replace state['xpaths'] so UI shows only matched
    state["matched_xpaths"] = matched
    state["extracted_xpaths"] = matched
    state["xpaths"] = matched

    elements = "\n".join([
        f"{el['variable_name']} | {el['category']} | {el['xpath']}"
        for el in matched
    ])

    system_prompt = """
You are an expert automation engineer.
You will receive:
1. A natural language test case
2. Optional test data
3. A list of extracted elements with variable_name and xpath

Your job:
- Map each step of the test case ONLY to elements in the provided list.
- Generate executable {selectedLanguage} code using {selectedTool}.
- Prefer By.id, By.name, By.cssSelector over XPath when possible.
- If an element does not exist in the list, insert a TODO comment instead of inventing a locator."""

    user_prompt = f"""Generate a code snippet in {selectedLanguage} that performs the following task.

Test case: \"{testCase}\"
Data: \"{testData}\"
Start URL: \"{url}\"
Test Steps: \"{testSteps}\"

RULES:
- TEXTBOX, PASSWORD → sendKeys
- BUTTON, LINK → click
- CHECKBOX → click if not selected
- DROPDOWN_NATIVE → Select class
- DROPDOWN_CUSTOM → click + select option
- Use XPath locators only
- Add TODO if element missing
"""

    user_prompt = f"""
Test Case:
{state.get("testCase")}

URL:
{state.get("url")}

Available Elements:
{elements}

Generate clean, executable Selenium Java code.
Return ONLY Java code.
"""

    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])

    state["generated_code"] = response.content
    return state


# =====================================================
# LangGraph Workflow
# =====================================================
graph = StateGraph(dict)

graph.add_node("fetch_page", fetch_page)
graph.add_node("extract_xpaths", extract_xpaths)
graph.add_node("generate_code", generate_code)

graph.add_edge("fetch_page", "extract_xpaths")
graph.add_edge("extract_xpaths", "generate_code")
graph.set_entry_point("fetch_page")
graph.add_edge("generate_code", END)

app = graph.compile()
