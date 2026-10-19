"""场地表格解析：按时段定位空闲格，并按优先级选择场地。"""
import re

from selenium.webdriver.common.by import By

from booking.timing import parse_clock_time

TIME_TEXT_PATTERN = r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)"


def parse_header_cells(cells):
    """
    把表头单元格转换为 [(列起始位置, colspan, [时间分钟数...])]，只保留含时间的单元格。

    cells 中每项为 (单元格文字, colspan 属性值)，列位置从 1 开始并累计 colspan。
    """
    time_cells = []
    column_position = 1

    for text, colspan in cells:
        try:
            column_span = max(1, int(colspan or 1))
        except (TypeError, ValueError):
            column_span = 1

        time_texts = re.findall(TIME_TEXT_PATTERN, text.replace("：", ":"))
        times = [int(hour) * 60 + int(minute) for hour, minute in time_texts]
        if times:
            time_cells.append((column_position, column_span, times))
        column_position += column_span

    return time_cells


def columns_within(time_cells, start_minutes, end_minutes):
    """返回完整落在 [start, end] 内的所有时段列号。"""
    start_markers = [times[0] for _, _, times in time_cells]
    marker_steps = [
        later - earlier
        for earlier, later in zip(start_markers, start_markers[1:])
        if later > earlier
    ]
    inferred_step = min(marker_steps) if marker_steps else None

    column_indexes = []
    for index, (position, column_span, times) in enumerate(time_cells):
        slot_start = times[0]
        if len(times) >= 2:
            slot_end = times[1]
        elif index + 1 < len(time_cells) and time_cells[index + 1][2][0] > slot_start:
            slot_end = time_cells[index + 1][2][0]
        elif inferred_step:
            slot_end = slot_start + inferred_step
        else:
            continue

        if start_minutes <= slot_start and slot_end <= end_minutes:
            column_indexes.extend(range(position, position + column_span))

    return column_indexes


def free_slot_xpath(column_indexes):
    position_condition = " or ".join(
        f"position() = {index}" for index in column_indexes
    )
    return (
        f"//tr/td[{position_condition}]"
        f"[contains(normalize-space(.), '空闲')]"
    )


def build_target_time_xpath(driver, start_time, end_time):
    """根据页面表头的时间文字，生成目标时段内空闲场地的 XPath。"""
    start_minutes = parse_clock_time(start_time)
    end_minutes = parse_clock_time(end_time)
    if start_minutes >= end_minutes:
        raise ValueError("TARGET_START_TIME 必须早于 TARGET_END_TIME。")

    best_column_indexes = []
    for row in driver.find_elements(By.XPATH, "//thead/tr | //tr[th]"):
        cells = [
            (cell.text, cell.get_attribute("colspan"))
            for cell in row.find_elements(By.XPATH, "./th | ./td")
        ]
        column_indexes = columns_within(parse_header_cells(cells), start_minutes, end_minutes)
        if len(column_indexes) > len(best_column_indexes):
            best_column_indexes = column_indexes

    if not best_column_indexes:
        raise ValueError(
            f"页面表头中没有完整落在 [{start_time} - {end_time}] 内的时间列，"
            "请检查配置是否与页面时段一致。"
        )
    return free_slot_xpath(best_column_indexes)


def normalize_venue_key(venue_name):
    """把“1”“1号”“羽毛球1号场”等统一为可比较的场地键。"""
    normalized = re.sub(r"\s+", "", str(venue_name or ""))
    number_match = re.search(r"(\d+)号?", normalized)
    if number_match:
        return number_match.group(1)
    return normalized


def pick_preferred(slot_records, preferred_venues, allow_other=True):
    """
    slot_records: [(点击目标, 场地名称, 场地键)]，按页面顺序排列。
    返回 (点击目标, 场地名称, 是否为优先场)；没有可选场地时返回 (None, None, False)。
    """
    preferred_keys = [normalize_venue_key(name) for name in preferred_venues]

    for preferred_key in preferred_keys:
        for click_target, venue_name, venue_key in slot_records:
            if venue_key == preferred_key:
                return click_target, venue_name, True

    if allow_other and slot_records:
        click_target, venue_name, _ = slot_records[0]
        return click_target, venue_name, False

    return None, None, False


def _visible_free_label(cell):
    """在 td 内寻找真正显示“空闲”的可见元素；“空闲”直接写在 td 中时退回 td 本身。"""
    clickable_elements = cell.find_elements(
        By.XPATH,
        ".//*[contains(normalize-space(text()), '空闲')]"
    )
    for element in reversed(clickable_elements):
        try:
            if (
                element.is_displayed()
                and element.size["width"] > 0
                and element.size["height"] > 0
            ):
                return element
        except Exception:
            continue
    return cell


def collect_slot_records(free_slots):
    """把“空闲”元素去重到所属 td，并读取所在行第一列的场地名称。"""
    slot_records = []
    seen_element_ids = set()

    for slot in free_slots:
        try:
            cell = slot.find_element(By.XPATH, "./ancestor-or-self::td[1]")
            if cell.id in seen_element_ids:
                continue
            seen_element_ids.add(cell.id)

            venue_name = cell.find_element(By.XPATH, "./ancestor::tr/td[1]").text.strip()
            slot_records.append(
                (_visible_free_label(cell), venue_name, normalize_venue_key(venue_name))
            )
        except Exception:
            continue

    return slot_records


def choose_venue_slot(free_slots, preferred_venues, allow_other=True):
    """
    按配置顺序选择空闲格。

    返回：(真正点击的元素, 场地名称, 是否为优先场)
    """
    return pick_preferred(collect_slot_records(free_slots), preferred_venues, allow_other)
