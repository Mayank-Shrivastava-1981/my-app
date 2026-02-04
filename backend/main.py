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

# ------------------------
# XPath + Element Intelligence Utility
# ------------------------
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

    # -------- Element Classification --------
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

    def is_interactive(self, tag, element_type, role):
        if tag in ["input", "button", "select", "textarea", "a"]:
            return True
        if role in ["button", "textbox", "combobox", "checkbox", "radio"]:
            return True
        return False

    # -------- Locator Strategy --------
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

    def generate_xpath(self, driver):
        elements = driver.find_elements(By.XPATH, "//*")

        for element in elements:
            try:
                tag = element.tag_name.lower()
                if tag in self.skip_tags:
                    continue

                element_type = element.get_attribute("type")
                role = element.get_attribute("role")

                if not self.is_interactive(tag, element_type, role):
                    continue

                for attr in self.known_attribute_list:
                    value = element.get_attribute(attr)

                    if value and not self._is_auto_generated(value):
                        xpath = f"//{tag}[@{attr}='{value}']"
                        if self._is_xpath_unique(driver, xpath):
                            category = self.classify_element(tag, element_type, role)
                            locator = self.determine_best_locator(tag, attr, value)

                            self.xpath_collection.append({
                                "tag": tag,
                                "category": category,
                                "attribute": attr,
                                "value": value,
                                "locator": locator,
                                "xpath": xpath,
                                "variable_name": self._generate_variable_name(tag, value),
                                "is_enabled": element.is_enabled(),
                                "is_displayed": element.is_displayed()
                            })
                            break

            except Exception as e:
                print(f"Error processing element: {e}")

    def _is_xpath_unique(self, driver, xpath):
        return len(driver.find_elements(By.XPATH, xpath)) == 1

    def _is_auto_generated(self, value):
        return bool(re.search(r"\b\w{5,}\d+\w*\b", value))

    def _generate_variable_name(self, tag, value):
        value = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower())
        return f"{tag}_{value.strip('_')}"


# ------------------------
# LangGraph Nodes
# ------------------------
def fetch_page(state):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    url = state.get("url")
    html = state.get("html")

    if url:
        driver.get(url)
    elif html:
        driver.get("data:text/html;charset=utf-8," + html)
    else:
        raise ValueError("URL or HTML must be provided")

    WebDriverWait(driver, 10).until(
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

    elements = "\n".join([
        f"{el['variable_name']} | {el['category']} | {el['locator']}"
        for el in state["xpaths"]
    ])

    system_prompt = f"""
You are a senior automation engineer.

ACTION RULES:
- TEXTBOX, PASSWORD → sendKeys
- BUTTON, LINK → click
- CHECKBOX → click if not selected
- DROPDOWN_NATIVE → Select class
- DROPDOWN_CUSTOM → click + select visible option
- If no matching element exists → add TODO

Use the provided elements only.
"""

    user_prompt = f"""
Test Case:
{state.get("testCase")}

Start URL:
{state.get("url")}

Available Elements:
{elements}

Generate executable Selenium Java code.
Return ONLY valid Java code.
"""

    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])

    state["generated_code"] = response.content
    return state


# ------------------------
# LangGraph Workflow
# ------------------------
graph = StateGraph(dict)

graph.add_node("fetch_page", fetch_page)
graph.add_node("extract_xpaths", extract_xpaths)
graph.add_node("generate_code", generate_code)

graph.add_edge("fetch_page", "extract_xpaths")
graph.add_edge("extract_xpaths", "generate_code")
graph.set_entry_point("fetch_page")
graph.add_edge("generate_code", END)

app = graph.compile()
