# 南大羽毛球场地预约脚本

## 快速开始

1. 安装 Python 3.12（已装好）和 Chrome。
2. 复制 `config.example.json` 为 `config.json`，填写统一认证账号、超级鹰账号、同伴姓名。
   超级鹰账号也可以用环境变量 `CHAOJIYING_USERNAME / CHAOJIYING_PASSWORD / CHAOJIYING_SOFT_ID` 覆盖。
3. 双击 `run.bat`（首次会自动创建 `.venv` 并安装依赖），按提示输入场地优先级和时段。

也可以手动运行：`.venv\Scripts\python.exe -m booking`（或旧方式 `python wy.py`）。

滑块固定差几像素时，设置环境变量 `SLIDER_FINE_TUNE`，例如 `2` 或 `-2`。

## 目录结构

```
booking/                 抢场脚本（原 wy.py）
  __main__.py            入口：读取配置 → 等待唤醒时间 → 执行主流程
  config.py              config.json 读取、页面 XPath、时间节点等常量
  prompts.py             启动时输入场地与时段
  timing.py              时间解析与定时等待
  browser.py             Chrome 初始化
  login.py               统一认证登录（账号密码 + 滑块循环）
  slider.py              滑块缺口识别、拖动轨迹、CDP 拖拽
  venue.py               表头时段解析、空闲格定位、场地优先级选择
  click_captcha.py       提交后的文字点选验证码（超级鹰 9801）
  chaojiying.py          超级鹰客户端
  payment.py             跳转支付页并点击支付
  reservation.py         主流程编排
app/ + src/              文字点选识别服务（FastAPI + ONNX），与抢场脚本相互独立
```

## 识别服务（可选）

需要把 `pre_model_v7.onnx`、`best_v3.onnx` 放到 `model/` 目录，然后运行 `run_service.bat`，
接口文档在 http://127.0.0.1:8000/docs。

## 注意

`config.json` 含账号密码，已加入 `.gitignore`，不要分享或上传。
