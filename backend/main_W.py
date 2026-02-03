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

# Load variables from .env file
load_dotenv()

# ------------------------
# Xpath Utility Class
# ------------------------
class Xpath_Util:
    def __init__(self):
        self.guessable_elements = ['input', 'button', 'select', 'textarea', 'a', 'label', 'img', 'div']
        self.known_attribute_list = [
            'id', 'name', 'placeholder', 'value', 'title', 'type', 'class', 'aria-label', 'data-testid'
        ]
        self.xpath_collection = []

    def generate_xpath(self, driver):
        elements = driver.find_elements(By.XPATH, '//input | //button | //select | //textarea | //a | //label | //img | //div')

        for element in elements:
            try:
                tag = element.tag_name.lower()
                if tag not in self.guessable_elements:
                    continue

                attr_found = False
                for attr in self.known_attribute_list:
                    attr_value = element.get_attribute(attr)
                    if attr_value and not self._is_auto_generated(attr_value):
                        xpath = f"//{tag}[@{attr}='{attr_value}']"
                        if self._is_xpath_unique(driver, xpath):
                            variable_name = self._generate_variable_name(tag, attr_value)
                            self.xpath_collection.append({
                                'tag': tag,
                                'attribute': attr,
                                'value': attr_value,
                                'xpath': xpath,
                                'variable_name': variable_name
                            })
                            attr_found = True
                            break

                if not attr_found and tag == 'button':
                    text = element.text.strip()
                    if text:
                        xpath = f"//button[text()='{text}']"
                        if self._is_xpath_unique(driver, xpath):
                            var_name = self._generate_variable_name(tag, text)
                            self.xpath_collection.append({
                                'tag': tag,
                                'attribute': 'text',
                                'value': text,
                                'xpath': xpath,
                                'variable_name': var_name
                            })

            except Exception as e:
                print(f"Error processing element: {e}")

    def _is_xpath_unique(self, driver, xpath):
        try:
            WebDriverWait(driver, 1).until(EC.presence_of_element_located((By.XPATH, xpath)))
            return len(driver.find_elements(By.XPATH, xpath)) == 1
        except:
            return False

    def _is_auto_generated(self, value):
        return bool(re.search(r'\b\w{5,}\d+\w*\b', value))

    def _generate_variable_name(self, tag, value):
        value = re.sub(r'[\s\-\/\[\],.&]+', '_', value)
        value = re.sub(r'__+', '_', value).strip('_')
        return value

# ------------------------
# LangGraph Nodes
# ------------------------
def fetch_page(state):
    try:
        url = state.get("url")
        html = state.get("html")

        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--log-level=3")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        if url:
            driver.get(url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        elif html:
            driver.get("data:text/html;charset=utf-8," + html)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        else:
            raise ValueError("Either url or html must be provided")

        state["driver"] = driver
        print("Page fetched successfully")
        return state

    except Exception as e:
        print(f"Error fetching page: {e}")
        if 'driver' in locals():
            driver.quit()
        raise

def extract_xpaths(state):
    print("Extracting xpaths...")
    driver = state["driver"]
    xpath_util = Xpath_Util()
    xpath_util.generate_xpath(driver)
    driver.quit()
    state["xpaths"] = xpath_util.xpath_collection
    print(f"Extracted {len(state['xpaths'])} xpaths successfully")
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
    matched = state.get("xpaths", [])  # Use all extracted xpaths if mapping is removed
    available_elements = "\n".join([f"{el['variable_name']}: {el['xpath']}" for el in matched])

    system_prompt = f"""You are an expert automation engineer.
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

Selector rules:
- Prefer: By.name, By.id, or CSS selectors
- Use XPath only if no other option is available
Available Elements:
{available_elements}

Generate {selectedLanguage} code using {selectedTool} that automates this test steps.

STRICT OUTPUT INSTRUCTION:
Return only valid {selectedLanguage} code with necessary imports. Do NOT include markdown, explanations, comments, or extra formatting."""

    resp = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])

    state["generated_code"] = resp.content
    return state

# ------------------------
# Build LangGraph Workflow
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
