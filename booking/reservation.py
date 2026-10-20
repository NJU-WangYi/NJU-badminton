"""主流程：登录 → 进入羽毛球预约 → 循环刷新扫描空闲场 → 提交 → 点选验证码 → 支付。"""
import datetime
import time

from selenium.common.exceptions import TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from booking import config
from booking.browser import create_driver
from booking.click_captcha import click_chinese_captcha_by_chaojiying
from booking.login import login
from booking.payment import finish_payment_after_captcha
from booking.timing import format_clock, wait_until
from booking.venue import build_target_time_xpath, choose_venue_slot


def _js_click(driver, element):
    driver.execute_script("arguments[0].click();", element)


def _click_first_visible(driver, elements):
    for el in elements:
        if el.is_displayed():
            _js_click(driver, el)
            break


def entry_click_plan(now):
    """
    决定何时点击预约入口：
    "now"（处于开放时段）、"today"（今天尚未开放）、"tomorrow"（今天已关闭）。
    """
    if config.PAGE_OPEN_TIME <= now < config.PAGE_CLOSE_TIME:
        return "now"
    if now < config.PAGE_OPEN_TIME:
        return "today"
    return "tomorrow"


def open_badminton_page(driver):
    """从登录后的首页进入场馆系统，并在开放时段内点击羽毛球预约入口。"""
    venue_link = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, config.VENUE_LINK_XPATH))
    )
    _js_click(driver, venue_link)

    venue_home_entry = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, config.VENUE_HOME_ENTRY_XPATH))
    )
    _js_click(driver, venue_home_entry)

    print(">>> 正在定位羽毛球预约入口...")
    reservation_entry = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, config.RESERVATION_ENTRY_XPATH))
    )

    # 入口出现后再读时间：定位入口可能耗时数秒，提前读取会误判为“未到开放时间”。
    plan = entry_click_plan(datetime.datetime.now().time())
    if plan == "now":
        print(">>> 登录已完成，当前处于允许时段，立即点击羽毛球预约入口...")
    else:
        print(f">>> 登录已完成，等待至 {format_clock(config.PAGE_OPEN_TIME)} 点击羽毛球预约入口...")
        # 今天尚未开放时只等今天：等待期间时间恰好越过开放时刻，就立即点击而不是顺延一天。
        wait_until(config.PAGE_OPEN_TIME, roll_over=(plan == "tomorrow"))

    _js_click(driver, reservation_entry)
    print(">>> 已点击羽毛球预约入口。")


def dismiss_entry_dialogs(driver):
    """处理进入预约页后的系统提示弹窗与场馆系统 SSO 二次跳转页。"""
    print(">>> 正在检测并处理登录后的系统提示弹窗...")
    time.sleep(0.1)  # 稍微等一下界面的过渡动画

    try:
        # 弹窗等待超时设为 0.5 秒，检测到元素后继续执行。
        elements = WebDriverWait(driver, 0.5).until(
            EC.presence_of_all_elements_located((By.XPATH, config.CONFIRM_DIALOG_XPATH))
        )
        _click_first_visible(driver, elements)
    except Exception:
        print("    -> ⚠️ 未捕获到弹窗，系统可能直接放行。")

    print(">>> 正在检测是否进入了场馆系统 SSO 二次跳转页...")
    try:
        # 单点登录按钮等待超时设为 0.5 秒，检测到可点击按钮后继续执行。
        sso_btn = WebDriverWait(driver, 0.5).until(
            EC.element_to_be_clickable((By.XPATH, config.SSO_BUTTON_XPATH))
        )
        _js_click(driver, sso_btn)
        print("    -> ✅ 成功点击 SSO 按钮！")
    except Exception:
        print("    -> ⚠️ 未检测到 SSO 按钮，系统已自动放行...")


def wait_for_target_xpath(driver, options):
    """等待表格加载，返回目标时段空闲格的 XPath。"""
    def resolve(current_driver):
        try:
            return build_target_time_xpath(current_driver, options.start_time, options.end_time)
        except ValueError:
            return False

    try:
        return WebDriverWait(driver, 10, poll_frequency=0.1).until(resolve)
    except TimeoutException:
        raise ValueError(
            f"等待表格加载 10 秒后，页面表头中仍没有完整落在 "
            f"[{options.start_time} - {options.end_time}] 内的时间列。"
        )


def click_slot(driver, target_slot, selected_venue):
    # 将真正的点击元素移动到视口中央，再用 ActionChains 模拟真实鼠标点击其中心
    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
        target_slot
    )
    print(
        "    -> 点击元素:",
        target_slot.tag_name,
        target_slot.get_attribute("class"),
        repr(target_slot.text)
    )
    ActionChains(driver).move_to_element(target_slot).pause(0.05).click().perform()
    print(f"    -> 🏆 成功锁定并点选目标: {selected_venue}")


def submit_order(driver, wait, settings):
    """添加同伴、勾选须知、点击提交。返回 (勾选完成时刻, 提交完成时刻)。"""
    print("    -> 正在添加同伴...")
    try:
        companion_name = settings.companion_name
        companion_btn = wait.until(
            EC.presence_of_element_located((By.XPATH, config.companion_xpath(companion_name)))
        )
        _js_click(driver, companion_btn)
        print(f"    -> ✅ 已成功选择同伴: {companion_name}")
    except Exception:
        print("    -> ⚠️ 选择同伴失败，请检查该同伴是否在列表中。")

    print("    -> 正在勾选预约须知...")
    try:
        # 很多 UI 框架的 checkbox 是隐藏的，点击它旁边的文字 Label 最为稳妥
        _js_click(driver, driver.find_element(By.XPATH, config.AGREE_XPATH))
        print("    -> ✅ 已勾选同意协议！")
    except Exception:
        print("    -> ⚠️ 勾选协议失败。")
    agreed_at = time.time()

    print("    -> 准备提交最终订单...")
    try:
        _js_click(driver, driver.find_element(By.XPATH, config.SUBMIT_XPATH))
        print("    -> 🚀🚀🚀 提交指令已发送！")
    except Exception:
        print("    -> ⚠️ 提交按钮点击失败。")
    submitted_at = time.time()
    return agreed_at, submitted_at


def pass_captcha_and_pay(driver, settings):
    """返回点选验证码处理完成的时刻。"""
    # 验证码点击后页面可能跳转或打开新窗口，必须提前记录状态。
    old_url = driver.current_url
    old_handles = list(driver.window_handles)

    print(">>> 正在检测并识别点选验证码...")
    captcha_success = click_chinese_captcha_by_chaojiying(driver, settings, timeout=10)
    captcha_done_at = time.time()

    if not captcha_success:
        print("    -> ⚠️ 点选验证码处理失败，请在浏览器中手动完成。")
    elif finish_payment_after_captcha(driver, old_url, old_handles, timeout=15):
        print(">>> ✅ 验证码与自动支付流程均已执行完成。")
    else:
        print(">>> ⚠️ 验证码已完成，但自动支付未成功。")
    return captcha_done_at


def refresh_page(driver):
    try:
        driver.refresh()
        # 如果刷新页面后出现“确定”提示弹窗，自动点击关掉它
        _click_first_visible(driver, driver.find_elements(By.XPATH, config.CONFIRM_DIALOG_XPATH))
    except Exception as refresh_err:
        print(f"    -> ⚠️ 页面刷新过程中发生异常: {refresh_err}")


def scan_and_book(driver, wait, settings, options):
    """循环刷新扫描目标时段空闲场，抢到后走完提交、验证码和支付流程。"""
    print(">>> 正在读取场地空闲状态数据...")
    print(f">>> 🚀 开启固定频率循环扫描模式，频率: {config.SCAN_INTERVAL}秒/次")
    started_at = time.time()
    target_time_xpath = wait_for_target_xpath(driver, options)

    while True:
        print(
            f"    -> 正在扫描 [{options.start_time}-{options.end_time}] "
            "时段的 [空闲] 场地..."
        )
        try:
            free_slots = WebDriverWait(driver, 0.1).until(
                EC.presence_of_all_elements_located((By.XPATH, target_time_xpath))
            )

            if free_slots:
                target_slot, selected_venue, is_preferred = choose_venue_slot(
                    free_slots,
                    options.preferred_venues,
                    allow_other=settings.allow_other_venues
                )

                if target_slot is None:
                    print(
                        "    -> ℹ️ 当前有其他空闲场地，但指定场均不可用，"
                        "继续刷新等待指定场..."
                    )
                    raise TimeoutException("指定场当前均无空闲时段")

                if is_preferred:
                    print(
                        f"    -> 🎯 发现 {len(free_slots)} 个空闲元素，"
                        f"优先锁定指定场: {selected_venue}"
                    )
                else:
                    print(f"    -> 🎯 指定场均不可用，按配置选择其他空闲场: {selected_venue}")

                click_slot(driver, target_slot, selected_venue)
                agreed_at, submitted_at = submit_order(driver, wait, settings)
                captcha_done_at = pass_captcha_and_pay(driver, settings)

                print(">>> 🎉 抢场脚本核心流程执行完毕！退出扫描。")
                break

        except Exception:
            print("    -> ⚠️ 未找到指定时段的空闲场地，或等待超时。")

        print(f"    -> ⏳ 等待 {config.SCAN_INTERVAL} 秒后刷新页面重新扫描...")
        time.sleep(config.SCAN_INTERVAL)
        refresh_page(driver)

    print(f"    -> ⏱️ [检测耗时: {time.time() - started_at:.3f}秒] -----------------------。")
    print(f"    -> ⏱️ [检测耗时: {time.time() - submitted_at:.3f}秒] -----------------------。")
    print(f"    -> ⏱️ [检测耗时: {time.time() - captcha_done_at:.3f}秒] -----------------------。")
    print(f"    -> ⏱️ [检测耗时: {agreed_at - started_at:.3f}秒] -----------------------。")


def nju_venue_reservation(settings, options):
    print(">>> 正在初始化环境，加载浏览器驱动...")

    try:
        driver = create_driver()
        wait = WebDriverWait(driver, 10)

        if not login(driver, wait, settings):
            return
        print(">>> 准备接管后续抢场地逻辑...")

        open_badminton_page(driver)
        dismiss_entry_dialogs(driver)
        scan_and_book(driver, wait, settings, options)
    except Exception as e:
        print("\n" + "=" * 40)
        print("❌ 脚本遇到严重错误！")
        print(e)
        print("=" * 40 + "\n")
    finally:
        print(">>> 运行结束，浏览器将保持打开状态。")
