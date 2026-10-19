"""登录页拼图滑块：从 Canvas 读取图像、计算缺口距离、用 CDP 模拟拖动。"""
import base64
import random
import time
from io import BytesIO

import cv2
import numpy as np
from PIL import Image

# 同时读取 Canvas 原图尺寸和网页坐标。背景与拼图 Canvas
# 不一定同宽、同位置，不能只用一个 width 比例换算。
READ_CANVAS_JS = """
    function canvasInfo(canvas) {
        const rect = canvas.getBoundingClientRect();
        return {
            base64: canvas.toDataURL("image/png").split(",", 2)[1],
            left: rect.left,
            top: rect.top,
            css_width: rect.width,
            css_height: rect.height,
            pixel_width: canvas.width,
            pixel_height: canvas.height
        };
    }

    return {
        background: canvasInfo(arguments[0]),
        block: canvasInfo(arguments[1])
    };
"""

BUTTON_POSITION_JS = """
    var btn = arguments[0];
    var rect = btn.getBoundingClientRect();
    var container = btn.closest(".sliderContainer") || btn.parentElement;
    var containerRect = container
        ? container.getBoundingClientRect()
        : null;
    return {
        x: rect.left + rect.width / 2,
        y: rect.top + rect.height / 2,
        max_drag: containerRect
            ? Math.max(0, containerRect.right - rect.right)
            : 0
    };
"""


def read_canvases(driver, bg_element, block_element):
    """返回 (背景信息, 拼图信息, 背景 PNG 字节, 拼图 PNG 字节)。"""
    canvas_data = driver.execute_script(READ_CANVAS_JS, bg_element, block_element)
    bg_info = canvas_data["background"]
    block_info = canvas_data["block"]
    return (
        bg_info,
        block_info,
        base64.b64decode(bg_info["base64"]),
        base64.b64decode(block_info["base64"]),
    )


def canvas_rendered(bg_info, block_info, bg_bytes):
    bg_img = Image.open(BytesIO(bg_bytes))
    return not (
        bg_img.width <= 10
        or bg_img.height <= 10
        or bg_info["css_width"] <= 10
        or block_info["css_width"] <= 0
    )


def compute_drag_distance(bg_info, block_info, bg_bytes, block_bytes, fine_tune_offset=0.0):
    """
    使用拼图透明轮廓匹配背景缺口，返回页面上的拖动像素数（已加微调）。

    拼图没有透明轮廓时返回 None；图像或匹配结果不可用时抛出 RuntimeError。
    """
    bg_cv = cv2.imdecode(np.frombuffer(bg_bytes, np.uint8), cv2.IMREAD_COLOR)
    if bg_cv is None:
        raise RuntimeError("背景 Canvas 图像解码失败")

    bg_gray = cv2.cvtColor(bg_cv, cv2.COLOR_BGR2GRAY)
    bg_gray = cv2.GaussianBlur(bg_gray, (3, 3), 0)
    bg_edge = cv2.Canny(bg_gray, 60, 180)

    block_cv = cv2.imdecode(np.frombuffer(block_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
    if block_cv is None or len(block_cv.shape) != 3 or block_cv.shape[2] < 4:
        raise RuntimeError("拼图 Canvas 没有可用的透明通道")

    alpha = block_cv[:, :, 3]
    _, thresh = cv2.threshold(alpha, 10, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    contour = max(contours, key=cv2.contourArea)
    piece_x, piece_y, piece_w, piece_h = cv2.boundingRect(contour)
    block_scale_x = block_info["css_width"] / block_info["pixel_width"]
    block_scale_y = block_info["css_height"] / block_info["pixel_height"]
    bg_scale_x = bg_info["css_width"] / bg_info["pixel_width"]
    bg_scale_y = bg_info["css_height"] / bg_info["pixel_height"]

    # 将拼图轮廓缩放到背景 Canvas 的原图像素坐标系。
    template_width = max(8, round(piece_w * block_scale_x / bg_scale_x))
    template_height = max(8, round(piece_h * block_scale_y / bg_scale_y))
    piece_mask = thresh[piece_y:piece_y + piece_h, piece_x:piece_x + piece_w]
    piece_mask = cv2.resize(
        piece_mask,
        (template_width, template_height),
        interpolation=cv2.INTER_NEAREST
    )
    template_edge = cv2.Canny(piece_mask, 30, 120)

    # 根据两个 Canvas 各自在页面中的 top 坐标确定搜索行。
    piece_page_top = block_info["top"] + piece_y * block_scale_y
    expected_bg_y = round((piece_page_top - bg_info["top"]) / bg_scale_y)
    vertical_margin = max(4, template_height // 5)
    search_top = max(0, expected_bg_y - vertical_margin)
    search_bottom = min(
        bg_edge.shape[0],
        expected_bg_y + template_height + vertical_margin
    )

    # 拼图通常从左侧向右拖动；排除起点左侧区域，减少误匹配。
    piece_page_left = block_info["left"] + piece_x * block_scale_x
    initial_bg_x = round((piece_page_left - bg_info["left"]) / bg_scale_x)
    search_left = max(0, initial_bg_x + template_width // 2)
    search_area = bg_edge[search_top:search_bottom, search_left:]

    if (
        search_area.shape[0] < template_edge.shape[0]
        or search_area.shape[1] < template_edge.shape[1]
    ):
        raise RuntimeError("滑块缺口搜索区域小于拼图模板")

    match_result = cv2.matchTemplate(search_area, template_edge, cv2.TM_CCOEFF_NORMED)
    _, confidence, _, max_loc = cv2.minMaxLoc(match_result)
    gap_x_in_bg = search_left + max_loc[0]

    # 分别换算背景缺口和拼图起点的页面绝对坐标，再相减。
    gap_page_left = bg_info["left"] + gap_x_in_bg * bg_scale_x
    true_drag_css = gap_page_left - piece_page_left
    target_x = int(round(true_drag_css + fine_tune_offset))

    print(f"    -> 缺口位置: {gap_x_in_bg}px，匹配置信度: {confidence:.3f}")
    print(f"    -> 背景比例: {bg_scale_x:.4f}，拼图比例: {block_scale_x:.4f}")
    print(f"    -> 页面拖动距离: {true_drag_css:.2f}px，微调: {fine_tune_offset:+.1f}px")

    if target_x <= 0:
        raise RuntimeError(f"计算出的拖动距离无效: {target_x}px")
    if confidence < 0.10:
        raise RuntimeError(f"拼图轮廓匹配置信度过低: {confidence:.3f}")

    return target_x


# ================= 模拟人类拖动轨迹算法 =================
def get_track(distance):
    """
    生成分段的人类式拖动轨迹：起步慢、中段快、末段减速。
    每一步带有随机变化，同时保证总位移严格等于目标距离。
    """
    distance = int(round(distance))
    if distance <= 0:
        return []

    track = []
    current = 0

    # 每次拖动随机划分三个阶段，避免轨迹形状完全固定。
    acceleration_end = max(1, int(distance * random.uniform(0.15, 0.22)))
    deceleration_start = max(
        acceleration_end + 1,
        int(distance * random.uniform(0.68, 0.78))
    )
    cruising_step = max(4, min(12, distance // 18))

    while current < distance:
        remaining = distance - current

        if current < acceleration_end:
            # 起步阶段：从 1～2 像素的小步逐渐加速。
            phase_progress = current / acceleration_end
            step_max = max(2, int(2 + cruising_step * phase_progress * 0.6))
            move = random.randint(1, step_max)
        elif current < deceleration_start:
            # 中段阶段：使用较大的随机步长连续推进。
            move = random.randint(
                max(3, cruising_step - 3),
                cruising_step + 2
            )
        else:
            # 收尾阶段：距离越近，步长越小，模拟人工对准缺口。
            slowing_distance = max(1, distance - deceleration_start)
            slowing_ratio = remaining / slowing_distance
            step_max = max(2, int(cruising_step * slowing_ratio))
            move = random.randint(1, step_max)

        move = min(move, remaining)
        track.append(move)
        current += move

    return track


def _mouse_event(driver, event_type, x, y, buttons, **extra):
    driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
        "type": event_type,
        "x": x,
        "y": y,
        "button": "left",
        "buttons": buttons,
        **extra,
    })


def drag_slider(driver, slide_btn, target_x):
    """通过 CDP 内核级鼠标事件，把滑块从中心点拖动 target_x 像素（不超出轨道）。"""
    btn_pos = driver.execute_script(BUTTON_POSITION_JS, slide_btn)
    start_x = btn_pos["x"]
    start_y = btn_pos["y"]

    max_drag = float(btn_pos.get("max_drag") or 0)
    if max_drag > 0 and target_x > max_drag:
        print(f"    -> ⚠️ 计算距离 {target_x}px 超出轨道，限制为 {max_drag:.1f}px")
        target_x = int(round(max_drag))

    target_absolute_x = start_x + target_x

    # 在滑块中心点按下鼠标左键
    _mouse_event(driver, "mousePressed", start_x, start_y, 1, clickCount=1)
    time.sleep(random.uniform(0.1, 0.2))

    # 按照轨迹发送 mouseMoved 事件
    current_x = start_x
    for move in get_track(target_x):
        current_x += move
        jitter_y = start_y + random.choice([-1, 0, 1])
        _mouse_event(driver, "mouseMoved", current_x, jitter_y, 1)
        time.sleep(random.uniform(0.012, 0.025))

    # 松手前强制移动到绝对终点，消除轨迹累加漂移
    _mouse_event(driver, "mouseMoved", target_absolute_x, start_y, 1)
    time.sleep(random.uniform(0.1, 0.3))

    # 在绝对坐标上松开鼠标左键
    _mouse_event(driver, "mouseReleased", target_absolute_x, start_y, 0, clickCount=1)
