"""识别服务：读取图片（URL 或 base64）、调用模型、绘制结果。"""
import base64
import io
import time

import aiohttp
import numpy as np
from PIL import Image

from src import captcha
from src.drawing import draw_boxes

s = time.time()
cap_model = captcha.TextSelectCaptcha()
print("加载模型耗时：", time.time() - s)
print("成功加载识别模型！")


async def fetch(url):
    timeout = aiohttp.ClientTimeout(
        total=10,  # 请求的总超时（秒）
        connect=5,  # 连接超时（秒）
        sock_read=5,  # 套接字读取超时（秒）
        sock_connect=5  # 套接字连接超时（秒）
    )
    async with aiohttp.ClientSession() as session:
        async with session.get(url, ssl=False, timeout=timeout) as response:
            return await response.read()


async def set_imageSource(dataType, imageSource):
    """dataType 1：imageSource 为链接；否则为不含头的 base64。返回图片字节。"""
    if dataType == 1:
        return await fetch(imageSource)
    return base64.b64decode(bytes(imageSource, 'utf-8'))


def drow_img(image_bytes, result):
    """返回绘制了识别框的 JPEG 字节。"""
    img = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
    img = draw_boxes(img, result)
    img_bytes = io.BytesIO()
    Image.fromarray(img).save(img_bytes, format='jpeg')
    return img_bytes.getvalue()


async def run(item):
    imageID = item.imageID if item.imageID else ""
    imageSource = await set_imageSource(item.dataType, item.imageSource)
    res = cap_model.run_dict(imageSource)
    return {"imageID": imageID, "res": res}


async def run_show(item):
    imageSource = await set_imageSource(item.dataType, item.imageSource)
    results = cap_model.run(imageSource)
    return drow_img(imageSource, results)
