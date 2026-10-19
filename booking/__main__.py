"""入口：python -m booking"""
import datetime

from booking import config
from booking.prompts import read_reservation_options
from booking.reservation import nju_venue_reservation
from booking.timing import wait_until


def main():
    settings = config.load_settings()
    options = read_reservation_options()

    current_time = datetime.datetime.now().time()
    # 22:00 至次日 07:57 处于休眠时段；唤醒前逐秒校准到 07:57。
    if current_time >= config.SLEEP_TIME or current_time < config.WAKE_TIME:
        wait_until(config.WAKE_TIME)
    else:
        print(">>> 🚀 当前处于 07:57 - 22:00，可直接启动主脚本！")

    nju_venue_reservation(settings, options)


if __name__ == "__main__":
    main()
