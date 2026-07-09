@echo off
setlocal

cd /d "%~dp0"

echo ========================================
echo  ChaBao_Pharmacy Windows Onefile Builder
echo ========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 没有找到 python。请先安装 Python 3.12，并勾选 Add Python to PATH。
    pause
    exit /b 1
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
if errorlevel 1 (
    echo [错误] 当前 Python 版本低于 3.12。建议使用 Python 3.12。
    python --version
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [信息] 正在创建虚拟环境 .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败。
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [错误] 激活虚拟环境失败。
    pause
    exit /b 1
)

echo [信息] 正在升级 pip ...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [错误] pip 升级失败。
    pause
    exit /b 1
)

echo [信息] 正在安装项目依赖 ...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 安装 requirements.txt 失败。
    pause
    exit /b 1
)

echo [信息] 正在安装 PyInstaller ...
python -m pip install pyinstaller
if errorlevel 1 (
    echo [错误] 安装 PyInstaller 失败。
    pause
    exit /b 1
)

echo [信息] 正在做语法检查 ...
python -m compileall -q app.py launcher.py agent services models pharmacy_analysis.py
if errorlevel 1 (
    echo [错误] 语法检查失败。
    pause
    exit /b 1
)

echo [信息] 正在运行单元测试 ...
python -m unittest discover -s tests -v
if errorlevel 1 (
    echo [错误] 单元测试失败，已停止打包。
    pause
    exit /b 1
)

echo [信息] 正在清理旧构建文件 ...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "ChaBao_Pharmacy.spec" del /q "ChaBao_Pharmacy.spec"

echo [信息] 正在打包单文件 exe，首次构建可能需要较长时间 ...
pyinstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --name ChaBao_Pharmacy ^
  --icon "resources\app_icon.ico" ^
  --add-data "app.py;." ^
  --add-data "pharmacy_analysis.py;." ^
  --add-data "requirements.txt;." ^
  --add-data ".streamlit;.streamlit" ^
  --add-data "agent;agent" ^
  --add-data "services;services" ^
  --add-data "models;models" ^
  --add-data "knowledge;knowledge" ^
  --add-data "resources;resources" ^
  --collect-all streamlit ^
  --collect-all langchain ^
  --collect-all langchain_core ^
  --collect-all langgraph ^
  --collect-all langchain_deepseek ^
  --collect-all pydantic ^
  --hidden-import streamlit.web.cli ^
  --hidden-import langchain_deepseek ^
  launcher.py

if errorlevel 1 (
    echo [错误] PyInstaller 打包失败。
    pause
    exit /b 1
)

echo.
echo [完成] 单文件 exe 已生成：
echo   %CD%\dist\ChaBao_Pharmacy.exe
echo.
echo 建议现在双击 dist\ChaBao_Pharmacy.exe 做一次完整手工测试。
pause
exit /b 0
