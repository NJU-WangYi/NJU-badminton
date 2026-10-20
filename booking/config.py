"""运行配置：个人账号信息来自 config.json，页面定位与时间常量集中在这里。"""
import datetime
import json
import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"

# ================= 页面地址 =================
LOGIN_URL = (
    "https://authserver.nju.edu.cn/authserver/login?service=https%3A%2F%2Fggtypt.nju.edu.cn%2Fvenue%2FLogin"
)
CHAOJIYING_UPLOAD_URL = "http://upload.chaojiying.net/Upload/Processing.php"
CHAOJIYING_CODE_TYPE = 9801

# ================= 时间节点 =================
# 22:00 至次日 07:57 处于休眠时段；唤醒前逐秒校准到 07:57。
WAKE_TIME = datetime.time(7, 57)
SLEEP_TIME = datetime.time(22, 0)
# 在此时段之外登录完成后，等待到 PAGE_OPEN_TIME 再点击预约入口。
PAGE_OPEN_TIME = datetime.time(8, 0, 1)
PAGE_CLOSE_TIME = datetime.time(22, 0)

SCAN_INTERVAL = 0.01  # 刷新频率（秒）
SLIDER_MAX_RETRIES = 5

# ================= 页面元素定位 =================
USERNAME_INPUT_XPATH = "//input[@id='username' or @name='username' or @type='text']"
PASSWORD_INPUT_XPATH = "//input[@id='password' or @name='password' or @type='password']"
LOGIN_BUTTON_XPATH = (
    "//button[@type='button' or @type='submit' or contains(text(), '登录')]"
    " | //div[contains(@class, 'login-button')]//button"
)

SLIDER_BG_XPATH = '//*[@id="sliderDiv"]/canvas[1]'
SLIDER_BLOCK_XPATH = '//*[@id="sliderDiv"]/canvas[@class="block"]'
SLIDER_BUTTON_CSS = (
    "#sliderDiv .sliderContainer .sliderBtn, #sliderDiv .sliderContainer .slider,"
    " #sliderDiv .sliderContainer > div:last-child"
)
SLIDER_REFRESH_XPATH = '//*[@id="sliderDiv"]//i[contains(@class, "refreshIcon")]'

VENUE_LINK_XPATH = "/html/body/div[1]/div[1]/div/div[2]/div[3]/div/a"
VENUE_HOME_ENTRY_XPATH = '//*[@id="homePage"]/div[3]/div[1]/div[2]'
RESERVATION_ENTRY_XPATH = (
    "/html/body/div[1]/div[1]/div/div[3]/div[2]/div/div[2]/div[4]/div[2]/div[2]/div[1]"
)
CONFIRM_DIALOG_XPATH = (
    "//*[(self::button or self::a or self::span or self::div)"
    " and (contains(text(), '确定') or contains(text(), '确 定'))]"
)
SSO_BUTTON_XPATH = "//*[contains(text(), '统一身份认证登录')]"
AGREE_XPATH = "//*[contains(text(), '已阅读并同意')]"
SUBMIT_XPATH = "//*[(self::button or self::div) and contains(text(), '提交')]"

PAYMENT_MODAL_XPATH = (
    "//div[contains(@class,'ivu-modal-confirm-footer')]"
    "//button[normalize-space(.)='支付'"
    " or normalize-space(.)='确认支付']"
)
# 首项保留 zzk.py 中已经使用的绝对 XPath，其余为页面变化时的备用定位。
PAYMENT_BUTTON_XPATHS = [
    "/html/body/div[1]/div/div/div[3]/div[2]/div/div[2]/div[2]/div[2]",
    (
        "//button[normalize-space(.)='支付'"
        " or contains(normalize-space(.),'立即支付')"
        " or contains(normalize-space(.),'确认支付')]"
    ),
    (
        "//a[normalize-space(.)='支付'"
        " or contains(normalize-space(.),'立即支付')"
        " or contains(normalize-space(.),'确认支付')]"
    ),
    (
        "//*[@role='button' and "
        "(normalize-space(.)='支付'"
        " or contains(normalize-space(.),'立即支付')"
        " or contains(normalize-space(.),'确认支付'))]"
    ),
    (
        "//*[contains(@class,'payHandleItem')"
        " and contains(normalize-space(.),'支付')]"
    ),
]


def companion_xpath(name):
    return f"//*[(self::div or self::span or self::button) and contains(text(), '{name}')]"


@dataclass
class Settings:
    nju_username: str
    nju_password: str
    chaojiying_username: str
    chaojiying_password: str
    chaojiying_soft_id: str
    companion_name: str
    # True：指定场都没有空闲时，选择其他空闲场；
    # False：只等待指定场，其他场即使空闲也继续刷新。
    allow_other_venues: bool = True


@dataclass
class ReservationOptions:
    """启动时输入的场地优先级（从高到低）与扫描时段（含开始，不含结束）。"""
    preferred_venues: list
    start_time: str
    end_time: str


def load_settings(path=CONFIG_PATH):
    """读取 config.json；超级鹰账号仍可由环境变量覆盖。"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"未找到配置文件 {path}。请复制 config.example.json 为 config.json 并填写账号信息。"
        )
    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    nju = data.get("nju", {})
    chaojiying = data.get("chaojiying", {})
    return Settings(
        nju_username=str(nju.get("username", "")),
        nju_password=str(nju.get("password", "")),
        chaojiying_username=os.environ.get(
            "CHAOJIYING_USERNAME", str(chaojiying.get("username", ""))
        ).strip(),
        chaojiying_password=os.environ.get(
            "CHAOJIYING_PASSWORD", str(chaojiying.get("password", ""))
        ).strip(),
        chaojiying_soft_id=os.environ.get(
            "CHAOJIYING_SOFT_ID", str(chaojiying.get("soft_id", ""))
        ).strip(),
        companion_name=str(data.get("companion_name", "")),
        allow_other_venues=bool(data.get("allow_other_venues", True)),
    )


def slider_fine_tune():
    """滑块固定像素偏差，可通过环境变量 SLIDER_FINE_TUNE 设置，例如 2 或 -2。"""
    try:
        return float(os.environ.get("SLIDER_FINE_TUNE", "0").strip() or "0")
    except ValueError:
        return 0.0
