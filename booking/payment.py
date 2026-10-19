"""验证码通过后的订单支付。"""
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from booking.config import PAYMENT_BUTTON_XPATHS, PAYMENT_MODAL_XPATH


def _switch_to_payment_page(driver, old_url, old_handles, timeout):
    try:
        WebDriverWait(driver, timeout, poll_frequency=0.1).until(
            lambda d: (
                len(d.window_handles) > len(old_handles)
                or d.current_url != old_url
            )
        )
    except TimeoutException:
        print("    -> ⚠️ 未检测到新窗口或 URL 跳转，继续尝试查找支付按钮。")

    new_handles = [
        handle for handle in driver.window_handles
        if handle not in old_handles
    ]
    if new_handles:
        driver.switch_to.window(new_handles[0])
        print("    -> ✅ 已切换到新打开的支付页面。")

    try:
        WebDriverWait(driver, timeout, poll_frequency=0.1).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except TimeoutException:
        print("    -> ⚠️ 支付页面未完全加载，继续查找可用按钮。")


def _confirm_payment_modal(driver):
    # 移植 zzk.py 的支付确认弹窗处理。
    try:
        modal_pay_button = WebDriverWait(
            driver, 2, poll_frequency=0.1
        ).until(
            EC.element_to_be_clickable((By.XPATH, PAYMENT_MODAL_XPATH))
        )
        driver.execute_script("arguments[0].click();", modal_pay_button)
        print("    -> ✅ 已处理支付确认弹窗。")
    except TimeoutException:
        print("    -> ℹ️ 未出现支付确认弹窗，继续。")


def _find_clickable_payment_button(driver):
    for xpath in PAYMENT_BUTTON_XPATHS:
        for element in driver.find_elements(By.XPATH, xpath):
            try:
                if element.is_displayed() and element.is_enabled():
                    return element
            except Exception:
                continue
    return False


def finish_payment_after_captcha(driver, old_url, old_handles, timeout=15):
    """等待验证码完成后的页面跳转，并自动处理支付操作。"""
    print(">>> 正在等待跳转至订单支付页面...")
    _switch_to_payment_page(driver, old_url, old_handles, timeout)
    _confirm_payment_modal(driver)

    try:
        payment_button = WebDriverWait(
            driver, timeout, poll_frequency=0.1
        ).until(_find_clickable_payment_button)
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            payment_button
        )
        driver.execute_script("arguments[0].click();", payment_button)
        print("    -> 💰 已点击最终支付按钮，支付指令已发送。")
        return True
    except TimeoutException:
        print("    -> ❌ 未找到可点击的最终支付按钮。")
        return False
    except Exception as e:
        print(f"    -> ❌ 点击最终支付按钮失败: {e}")
        return False
