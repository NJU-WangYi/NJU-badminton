"""超级鹰打码平台客户端。"""
import hashlib

import requests

from booking.config import CHAOJIYING_UPLOAD_URL

REPORT_ERROR_URL = "http://upload.chaojiying.net/Upload/ReportError.php"


class ChaojiyingClient:
    """超级鹰点选验证码客户端。题目类型参考 http://www.chaojiying.com/price.html"""

    def __init__(self, username, password, soft_id):
        self.base_params = {
            "user": username,
            "pass2": hashlib.md5(password.encode("utf-8")).hexdigest(),
            "softid": soft_id,
        }
        self.headers = {
            "Connection": "Keep-Alive",
            "User-Agent": "Mozilla/5.0",
        }

    def post_pic(self, image_bytes, code_type, str_debug=""):
        params = {"codetype": code_type, **self.base_params}
        if str_debug:
            params["str_debug"] = str_debug

        response = requests.post(
            CHAOJIYING_UPLOAD_URL,
            data=params,
            files={"userfile": ("captcha.png", image_bytes)},
            headers=self.headers,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def post_pic_base64(self, base64_str, code_type):
        params = {"codetype": code_type, "file_base64": base64_str, **self.base_params}
        response = requests.post(
            CHAOJIYING_UPLOAD_URL, data=params, headers=self.headers, timeout=15
        )
        response.raise_for_status()
        return response.json()

    def report_error(self, im_id):
        """im_id: 报错题目的图片 ID"""
        params = {"id": im_id, **self.base_params}
        response = requests.post(
            REPORT_ERROR_URL, data=params, headers=self.headers, timeout=15
        )
        response.raise_for_status()
        return response.json()


def create_client(settings):
    if not settings.chaojiying_username or not settings.chaojiying_password or not settings.chaojiying_soft_id:
        raise RuntimeError(
            "未配置超级鹰账号。请在 config.json 中填写，或设置 CHAOJIYING_USERNAME、"
            "CHAOJIYING_PASSWORD 和 CHAOJIYING_SOFT_ID 环境变量。"
        )
    return ChaojiyingClient(
        settings.chaojiying_username,
        settings.chaojiying_password,
        settings.chaojiying_soft_id,
    )
