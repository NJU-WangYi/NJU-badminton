"""时间解析与定时等待。"""
import datetime
import re
import sys
import time


def parse_clock_time(value):
    """把 HH:MM 格式的时间转换为从零点开始的分钟数。"""
    match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", str(value))
    if not match:
        raise ValueError(f"时间格式错误: {value!r}，请使用 HH:MM，例如 19:00。")

    hour, minute = map(int, match.groups())
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"时间超出有效范围: {value!r}")
    return hour * 60 + minute


def format_clock(value):
    """datetime.time -> HH:MM:SS，带微秒时保留到有效小数位。"""
    if value.microsecond:
        return value.strftime("%H:%M:%S.%f").rstrip("0")
    return value.strftime("%H:%M:%S")


def wait_for_target_time(
        target_hour,
        target_minute,
        target_second=0,
        target_microsecond=0
):
    """
    等待直到指定的时间 (默认今天，如果已过则等明天)
    """
    now = datetime.datetime.now()
    target_time = now.replace(
        hour=target_hour,
        minute=target_minute,
        second=target_second,
        microsecond=target_microsecond
    )
    target_clock = format_clock(target_time.time())

    if now >= target_time:
        print(
            f">>> ℹ️ 今天的 {target_clock} "
            "已过，自动将计划延后至明天的同一时间。"
        )
        target_time += datetime.timedelta(days=1)

    print(f">>> 🎯 计划启动时间锁定为: {target_time.strftime('%Y-%m-%d %H:%M:%S')}")

    while True:
        now = datetime.datetime.now()
        if now >= target_time:
            print("\n>>> 🚀 时间到！引擎点火，开始执行抢场任务！")
            break

        # 动态倒计时打印（\r 回车符实现单行刷新）
        left_seconds = (target_time - now).total_seconds()
        sys.stdout.write(f"\r>>> ⏳ 挂机等待中... 距离唤醒浏览器还有 {left_seconds:.0f} 秒 ")
        sys.stdout.flush()
        time.sleep(min(1, max(0.01, left_seconds)))


def wait_until(clock):
    """等待到给定的 datetime.time（今天已过则等明天）。"""
    wait_for_target_time(clock.hour, clock.minute, clock.second, clock.microsecond)
