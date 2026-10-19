@echo off
chcp 65001 > nul
cd /d "%~dp0"

rem 首次运行时用 Python 3.12 创建虚拟环境
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3.12 -m venv .venv
    if errorlevel 1 (
        echo 未找到 Python 3.12，请先安装： https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

rem 安装/更新依赖（已安装时很快跳过）
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt

if not exist "config.json" (
    echo 未找到 config.json，请复制 config.example.json 为 config.json 并填写账号信息。
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m booking

pause
