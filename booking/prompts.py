"""启动时的命令行输入。"""
import re

from booking.config import ReservationOptions
from booking.timing import parse_clock_time


class TimeCountError(ValueError):
    """输入的时间个数不是两个。"""


def parse_venues(venue_input):
    """'7 8 9' -> ['7号', '8号', '9号']；非纯数字的输入原样保留。"""
    venues = [item for item in re.split(r"[\s,，]+", venue_input.strip()) if item]
    return [
        f"{venue}号" if re.fullmatch(r"\d+", venue) else venue
        for venue in venues
    ]


def parse_time_range(time_input):
    """'21 22' 或 '21:00 22:00' -> ('21:00', '22:00')；输入有误时抛出 ValueError。"""
    time_values = [
        item for item in re.split(r"[\s,，]+", time_input.strip().replace("：", ":")) if item
    ]
    if len(time_values) != 2:
        raise TimeCountError("请依次输入两个时间：开始时间 结束时间，例如 21 22。")

    minutes = [
        parse_clock_time(f"{value}:00" if re.fullmatch(r"\d{1,2}", value) else value)
        for value in time_values
    ]
    if any(value % 60 != 0 for value in minutes):
        raise ValueError("时间只能是整点，例如 21 22 或 21:00 22:00。")
    if minutes[0] >= minutes[1]:
        raise ValueError("开始时间必须早于结束时间。")

    start_time, end_time = [
        f"{value // 60:02d}:{value % 60:02d}" for value in minutes
    ]
    return start_time, end_time


def read_reservation_options():
    """启动时读取场地优先级和始末时间，并自动补齐格式。"""
    while True:
        preferred_venues = parse_venues(input(
            "请输入场地（按优先顺序，用空格分隔，例如 7 8 9）："
        ))
        if preferred_venues:
            break
        print("请至少输入一个场地。")

    while True:
        time_input = input(
            "请输入开始和结束时间（仅限整点，用空格分隔，例如 21 22 或 21:00 22:00）："
        )
        try:
            start_time, end_time = parse_time_range(time_input)
        except TimeCountError as error:
            print(error)
            continue
        except ValueError as error:
            print(f"输入有误：{error} 请重新输入。")
            continue

        print(f">>> 场地优先级：{preferred_venues}；扫描时段：{start_time} - {end_time}")
        return ReservationOptions(preferred_venues, start_time, end_time)
