"""Chrome 浏览器初始化。"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--window-position=0,0")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.add_experimental_option("detach", True)

    # 1. 禁用自动化标志，防止 navigator.webdriver 暴露
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    # 2. 移除开发者插件提示
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])

    driver = webdriver.Chrome(options=chrome_options)
    try:
        driver.maximize_window()
    except Exception as maximize_error:
        print(f">>> ⚠️ 浏览器自动最大化失败: {maximize_error}")

    # 额外通过 CDP 彻底抹去 webdriver 痕迹
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"
    })
    return driver
