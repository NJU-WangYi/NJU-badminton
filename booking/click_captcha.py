"""提交订单后的“请依次点击【字,字,字】”点选验证码。"""
import base64
import re

from selenium.webdriver.support.ui import WebDriverWait

from booking.chaojiying import create_client
from booking.config import CHAOJIYING_CODE_TYPE

# 验证码提示文字与图片都可见时，返回提示文本、图片 data URL 及尺寸；否则返回 null。
READ_CAPTCHA_JS = """
    const msg = document.querySelector("span.verify-msg")
        || Array.from(document.querySelectorAll("span, div"))
            .find(el => (el.innerText || el.textContent || "")
                .includes("请依次点击"));
    const img = document.querySelector(".verify-img-panel img")
        || document.querySelector(".verify-img-panel canvas");

    function visible(el) {
        if (!el) return false;
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        return rect.width > 0
            && rect.height > 0
            && style.display !== "none"
            && style.visibility !== "hidden";
    }

    if (!visible(msg) || !visible(img)) {
        return null;
    }

    const rect = img.getBoundingClientRect();
    let src = "";

    if (img.tagName === "CANVAS") {
        try {
            src = img.toDataURL("image/png");
        } catch (e) {
            return null;
        }
    } else {
        src = img.currentSrc || img.src || "";
    }

    if (!src.startsWith("data:image")) {
        return null;
    }

    return {
        text: (msg.innerText || msg.textContent || "").trim(),
        src,
        display_width: rect.width,
        display_height: rect.height,
        natural_width: img.naturalWidth || img.width || rect.width,
        natural_height: img.naturalHeight || img.height || rect.height
    };
"""

# 按原图坐标 × 显示缩放比例，依次在图片上派发鼠标事件。
CLICK_POINTS_JS = """
    const points = arguments[0];
    const img = document.querySelector(".verify-img-panel img")
        || document.querySelector(".verify-img-panel canvas");
    if (!img) return false;

    const rect = img.getBoundingClientRect();
    const naturalWidth = img.naturalWidth || img.width || rect.width || 1;
    const naturalHeight = img.naturalHeight || img.height || rect.height || 1;
    const scaleX = rect.width / naturalWidth;
    const scaleY = rect.height / naturalHeight;

    function clickAt(clientX, clientY) {
        const target = document.elementFromPoint(clientX, clientY) || img;
        const downOptions = {
            bubbles: true,
            cancelable: true,
            view: window,
            clientX,
            clientY,
            screenX: window.screenX + clientX,
            screenY: window.screenY + clientY,
            button: 0,
            buttons: 1
        };
        const upOptions = {...downOptions, buttons: 0};

        target.dispatchEvent(new MouseEvent("mousemove", downOptions));
        target.dispatchEvent(new MouseEvent("mousedown", downOptions));
        target.dispatchEvent(new MouseEvent("mouseup", upOptions));
        target.dispatchEvent(new MouseEvent("click", upOptions));
    }

    for (const point of points) {
        clickAt(
            rect.left + point[0] * scaleX,
            rect.top + point[1] * scaleY
        );
    }
    return true;
"""


def parse_target_chars(prompt_text):
    """从“请依次点击【字,字,字】”中提取汉字列表；没有【】时返回 None。"""
    match = re.search(r"【(.+?)】", prompt_text)
    if not match:
        return None
    return [
        char.strip()
        for char in re.split(r"[,，、\s]+", match.group(1))
        if char.strip()
    ]


def parse_points(coordinate_text):
    """'x1,y1|x2,y2' -> [[x1, y1], [x2, y2]]；格式错误时抛出 ValueError。"""
    points = []
    try:
        for item in coordinate_text.split("|"):
            x_text, y_text = item.strip().split(",")
            points.append([int(x_text), int(y_text)])
    except (TypeError, ValueError):
        raise ValueError(coordinate_text)
    return points


def click_chinese_captcha_by_chaojiying(driver, settings, timeout=10):
    """
    读取“请依次点击【字,字,字】”提示，调用超级鹰 9801 接口识别坐标，
    再按照验证码原图与网页显示尺寸的比例依次点击。
    """
    try:
        verify_payload = WebDriverWait(
            driver, timeout, poll_frequency=0.03
        ).until(lambda d: d.execute_script(READ_CAPTCHA_JS))
    except Exception as e:
        print(f"    -> ⚠️ 验证码区域未加载完成: {e}")
        return False

    target_chars = parse_target_chars(verify_payload["text"])
    if target_chars is None:
        print("    -> ⚠️ 未从验证码提示中提取到目标汉字。")
        return False
    if not target_chars:
        print("    -> ⚠️ 验证码提示中没有有效汉字。")
        return False

    print(f"    -> 需要依次点击的汉字: {target_chars}")

    try:
        _, encoded_data = verify_payload["src"].split(",", 1)
        image_bytes = base64.b64decode(encoded_data)
        instruction = f"{{8a:{','.join(target_chars)}/8a}}"
        result = create_client(settings).post_pic(
            image_bytes, CHAOJIYING_CODE_TYPE, instruction
        )
    except Exception as e:
        print(f"    -> ⚠️ 超级鹰识别请求失败: {e}")
        return False

    if result.get("err_no") not in (0, "0", None):
        print(
            "    -> ⚠️ 超级鹰返回错误: "
            f"{result.get('err_no')} {result.get('err_str', '')}"
        )
        return False

    coordinate_text = result.get("pic_str") or result.get("pic str")
    if not coordinate_text:
        print("    -> ⚠️ 超级鹰没有返回点击坐标。")
        return False

    try:
        points = parse_points(coordinate_text)
    except ValueError:
        print(f"    -> ⚠️ 无法解析超级鹰坐标: {coordinate_text}")
        return False

    if len(points) < len(target_chars):
        print(
            f"    -> ⚠️ 仅识别到 {len(points)} 个坐标，"
            f"但验证码要求点击 {len(target_chars)} 个汉字。"
        )
        return False

    points = points[:len(target_chars)]
    if not driver.execute_script(CLICK_POINTS_JS, points):
        print("    -> ⚠️ 验证码图片已消失，无法执行坐标点击。")
        return False

    print(f"    -> ✅ 已按顺序点击 {len(points)} 个验证码坐标。")
    return True
