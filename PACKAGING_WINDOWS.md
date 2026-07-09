# Windows 单文件 exe 打包说明

本文档用于把查宝（药店版）打包成一个 Windows 单文件程序：

```text
dist\ChaBao_Pharmacy.exe
```

## 1. 推荐环境

- Windows 10 或 Windows 11；
- Python 3.12；
- 项目目录名建议为 `ChaBao_Pharmacy`；
- 网络可以访问 Python 包源，用于安装依赖；
- 建议不要在路径中使用特殊符号。

如果电脑已经安装多个 Python，请先确认命令行里的版本：

```bat
python --version
```

建议输出为 Python 3.12.x。

## 2. 一键打包

在 Windows 上打开命令行，进入项目目录：

```bat
cd 路径\ChaBao_Pharmacy
```

执行：

```bat
build_windows.bat
```

脚本会自动完成：

1. 创建 `.venv` 虚拟环境；
2. 安装 `requirements.txt`；
3. 安装 PyInstaller；
4. 执行语法检查；
5. 执行单元测试；
6. 使用 PyInstaller 单文件模式打包；
7. 输出 `dist\ChaBao_Pharmacy.exe`。

## 3. 打包完成后怎么测试

双击：

```text
dist\ChaBao_Pharmacy.exe
```

正常情况：

1. 会出现一个命令行窗口；
2. 程序启动本地 Streamlit 服务；
3. 控制台打印本地访问地址 `http://127.0.0.1:8501`；
4. 用户手动打开浏览器并输入该地址；
5. 页面显示“查宝（药店版） designed by DriftMousie”；
6. 输入并验证 DeepSeek API Key 后开始对话。

注意：关闭命令行窗口会停止本地服务。

## 4. 为什么首次启动较慢

当前使用 PyInstaller `--onefile` 单文件模式。单文件 exe 启动时会先把 Python 运行环境、Streamlit、LangChain、pandas、openpyxl 等依赖解压到系统临时目录，再启动程序。

因此：

- 第一次启动可能较慢；
- 杀毒软件可能会扫描较久；
- 如果用户电脑安全策略严格，可能会拦截单文件自解压行为。

如果后续发现单文件启动慢或被误报，建议改用 `onedir` 模式再配安装程序。

## 5. DeepSeek API Key 保存在哪里

程序验证成功后，会在 exe 所在运行环境对应的程序目录中保存：

```text
deepseek_config.json
```

该文件包含可读取的 API Key，不要发给别人，也不要上传到代码仓库。

## 6. 用户业务文件放哪里

当前版本打包运行时，工作目录会自动设为 exe 所在文件夹。用户把销售端、医保端、处方端文件放在 exe 同一个文件夹内，程序就能识别。页面会显示该目录，并提供“打开工作目录”按钮。后续如需更规范的发布方式，可再改为固定的用户文档目录：

```text
Documents\ChaBao_Pharmacy_Workspace
```

当前内置资源包括：

```text
处方药目录：默认内置
resources\image.jpg
```

打包脚本已经把 `resources` 目录包含进 exe。

## 7. 常见问题

### 7.1 运行 build_windows.bat 提示找不到 Python

请安装 Python 3.12，并在安装时勾选：

```text
Add Python to PATH
```

安装后重新打开命令行。

### 7.2 安装依赖失败

通常是网络或包源问题。可以先手动执行：

```bat
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

如果下载慢，可以临时使用国内镜像源。

### 7.3 打包成功但浏览器打不开页面

程序不会自动弹出浏览器窗口。请看命令行窗口里的提示，手动打开浏览器访问地址。

- 如果提示端口 8501 被占用，请关闭其他 Streamlit 程序后重试；
- 如果页面暂时打不开，请等待 10-30 秒后刷新；
- 默认访问地址：

```text
http://127.0.0.1:8501
```

### 7.4 exe 很大是否正常

正常。单文件包含 Python 运行时、数据分析库和 Streamlit 相关依赖，体积通常会比较大。

### 7.5 杀毒软件提示风险

PyInstaller 单文件程序会自解压，部分杀毒软件可能误报。解决方案：

1. 优先使用自己电脑或可信环境打包；
2. 给 exe 做代码签名；
3. 如果误报严重，改用 `onedir` 打包模式。

## 8. 手工打包命令

如果不使用 `build_windows.bat`，可以在已安装依赖的虚拟环境中手工执行：

```bat
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
```

输出文件：

```text
dist\ChaBao_Pharmacy.exe
```


## 9. 程序图标

Windows exe 图标不能直接使用 JPG，PyInstaller 需要 `.ico` 文件。当前已将：

```text
resources\image.jpg
```

转换为：

```text
resources\app_icon.ico
```

`build_windows.bat` 已通过以下参数使用该图标：

```bat
--icon "resources\app_icon.ico"
```

如果以后更换头像图，请重新生成 `resources\app_icon.ico`，再重新运行 `build_windows.bat`。


### 7.6 启动超时或一直停在黑窗口

旧版启动器曾使用 `sys.executable -m streamlit` 启动子进程。打包为 PyInstaller `onefile` 后，`sys.executable` 指向当前 exe，自启动子进程容易导致 Streamlit 没有真正启动，表现为启动超时。

当前版本已改为在当前进程中直接调用 Streamlit CLI：

```python
from streamlit.web import cli as stcli
stcli.main()
```

因此重新打包前，请确认 `launcher.py` 已是新版，并重新运行 `build_windows.bat`。


### 7.7 server.port 与 developmentMode 冲突

如果打包运行时报错：

```text
RuntimeError: server.port does not work when global.developmentMode is true.
```

原因是 Streamlit 在 PyInstaller 打包环境中可能把自己识别为开发模式，而启动器又需要固定端口 `8501`。当前 `launcher.py` 已显式关闭开发模式：

```python
os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
```

并在 Streamlit CLI 参数中加入：

```text
--global.developmentMode false
```

修改后请重新运行 `build_windows.bat` 生成新的 exe。


### 7.8 页面显示 _MEI 临时目录

PyInstaller `onefile` 会把程序解压到系统临时目录，例如：

```text
C:\Users\Administrator\AppData\Local\Temp\_MEI213522
```

旧版 `app.py` 使用 `Path(__file__).parent` 作为工作目录，因此页面会显示这个临时目录。当前版本已修复：

- `launcher.py` 会把 exe 所在目录写入环境变量 `CHABAO_WORKSPACE`；
- `app.py` 优先使用 `CHABAO_WORKSPACE` 作为用户工作目录；
- 页面提供“打开工作目录”按钮。

修改后请重新运行 `build_windows.bat` 生成新的 exe。
