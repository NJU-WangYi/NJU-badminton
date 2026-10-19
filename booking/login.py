"""南京大学统一身份认证登录（账号密码 + 拼图滑块）。"""
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from booking import config
from booking.slider import canvas_rendered, compute_drag_distance, drag_slider, read_canvases


def _set_input_value(driver, element, value):
    """用 JS 写入输入框，并触发 input/change 事件让前端框架感知。"""
    driver.execute_script("arguments[0].focus();", element)
    driver.execute_script("arguments[0].value = arguments[1];", element, value)
    driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", element)
    driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", element)


def submit_credentials(driver, wait, settings):
    print(">>> 正在打开南京大学统一身份认证页面...")
    driver.get(config.LOGIN_URL)

    print(">>> 正在定位账号密码输入框...")
    username_input = wait.until(EC.presence_of_element_located((By.XPATH, config.USERNAME_INPUT_XPATH)))
    password_input = wait.until(EC.presence_of_element_located((By.XPATH, config.PASSWORD_INPUT_XPATH)))

    print(">>> 正在通过底层 JS 强行写入账号密码...")
    _set_input_value(driver, username_input, settings.nju_username)
    _set_input_value(driver, password_input, settings.nju_password)
    print(">>> 账号密码写入完成，准备提交登录...")

    # 提交表单唤醒滑块
    try:
        print(">>> 尝试通过回车键直接唤醒表单提交...")
        password_input.send_keys(Keys.ENTER)
        print(">>> 回车键已发送，等待滑块弹出...")
    except Exception as e:
        print(f">>> 回车键发送失败，启动备用点击方案... 错误: {e}")
        login_button = driver.find_element(By.XPATH, config.LOGIN_BUTTON_XPATH)
        driver.execute_script("arguments[0].click();", login_button)


def _slider_passed(driver):
    try:
        WebDriverWait(driver, 3, poll_frequency=0.1).until(
            lambda d: (
                len(d.find_elements(By.ID, "sliderDiv")) == 0
                or not d.find_elements(By.ID, "sliderDiv")[0].is_displayed()
                or "authserver" not in d.current_url.lower()
            )
        )
        return True
    except Exception:
        return False


def _refresh_slider(driver):
    try:
        refresh_btn = driver.find_element(By.XPATH, config.SLIDER_REFRESH_XPATH)
        driver.execute_script("arguments[0].click();", refresh_btn)
        time.sleep(0.6)
    except Exception as ref_e:
        print(f"⚠️ 自动点击刷新按钮失败: {ref_e}")


def solve_slider(driver, wait, max_retries=config.SLIDER_MAX_RETRIES):
    """循环识别并拖动滑块，通过返回 True。"""
    for attempt in range(max_retries):
        print(f"\n>>> [第 {attempt + 1} 次尝试] 正在定位并处理动态滑块...")

        try:
            # 直接提取 Canvas 内存图像，绕过屏幕 DPI 缩放误差
            print("    -> 正在从 Canvas 提取原生图像数据...")
            bg_element = wait.until(EC.presence_of_element_located((By.XPATH, config.SLIDER_BG_XPATH)))
            block_element = wait.until(EC.presence_of_element_located((By.XPATH, config.SLIDER_BLOCK_XPATH)))
            bg_info, block_info, bg_bytes, block_bytes = read_canvases(driver, bg_element, block_element)

            if not canvas_rendered(bg_info, block_info, bg_bytes):
                print("    -> 检测到画布尚未渲染完成，暂停 1 秒后重试...")
                time.sleep(1.0)
                continue

            print("    -> 正在定位拖拽按钮...")
            slide_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, config.SLIDER_BUTTON_CSS)))

            print("    -> 正在使用拼图轮廓和页面坐标计算拖动距离...")
            target_x = compute_drag_distance(
                bg_info, block_info, bg_bytes, block_bytes, config.slider_fine_tune()
            )
            if target_x is None:
                print("    -> ⚠️ OpenCV 未找到拼图透明轮廓，跳过本次循环...")
                continue
            print(f"    -> 🌟 最终拖拽距离: {target_x} 像素")

            print("    -> 正在通过 CDP 内核协议模拟真实鼠标拖拽...")
            drag_slider(driver, slide_btn, target_x)
            print("    -> CDP 拖拽指令执行完毕，等待系统响应验证...")

            if _slider_passed(driver):
                print("✅ 登录成功！滑块验证已通过。")
                return True
            print("⚠️ 验证未通过，准备点击刷新按钮重置验证码...")
            _refresh_slider(driver)

        except Exception as loop_e:
            message = str(loop_e).lower()
            if "invalid session id" in message or "target window already closed" in message:
                print("❌ 浏览器连接已断开，停止自动重试。")
                break
            print(f"⚠️ 滑块处理异常: {loop_e}")
            time.sleep(0.6)

    return False


def login(driver, wait, settings):
    submit_credentials(driver, wait, settings)
    if solve_slider(driver, wait):
        return True

    print("❌ 自动登录失败。")
    print(">>> 请检查上方的匹配置信度和拖动距离日志。")
    print(">>> 若只差固定像素，可设置环境变量 SLIDER_FINE_TUNE，例如 2 或 -2。")
    return False
