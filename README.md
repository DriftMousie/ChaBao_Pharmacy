# ChaBao_Pharmacy

查宝（药店版）是一款面向医保药店数据筛查的本地智能体工具。它通过简洁的网页对话界面，引导用户完成列名配置、退货冲销检查、销售端与医保端比对、处方端与医保端比对等工作，并将结果文件生成在本地工作目录中。

> 产品显示名：查宝（药店版）  
> Designed by DriftMousie

## ✨ 功能特点

- 对话式操作：用户不需要理解代码，通过聊天输入即可生成配置、执行检查和查看下一步建议。
- DeepSeek API 接入：用户填写并验证自己的 DeepSeek API Key 后，智能体开始工作。
- 列名配置生成：自动生成 `列名配置.xlsx`，普通用户只需要修改“用户录入列名”列。
- 退货冲销检查：识别销售端一正一负的冲销记录，辅助用户清理销售数据。
- 销售医保比对：按金额、时间和商品名称相似度进行多轮匹配，输出完全匹配、不完全匹配和未匹配结果。
- 处方医保综合比对：比对医保端与处方端数据，并结合内置处方药目录判断处方药风险。
- 本地文件处理：业务数据只在用户本机处理，不上传销售、医保或处方明细。
- 执行防重复提交：处理大文件时会禁用输入框并提示用户等待，避免重复执行。
- Windows 单文件打包：支持通过 PyInstaller 打包为 `ChaBao_Pharmacy.exe`。

## 📑 环境要求

源码运行建议环境：

- Python 3.12+
- Windows 10/11 或 macOS
- DeepSeek API Key
- 浏览器，例如 Chrome、Edge、Safari

主要 Python 依赖：

- pandas
- openpyxl
- streamlit
- langchain
- langgraph
- langchain-deepseek

完整依赖见：

```text
requirements.txt
```

## 🚀 安装与使用

### 安装

```bash
# 克隆仓库
git clone https://github.com/你的用户名/ChaBao_Pharmacy.git

# 进入项目目录
cd ChaBao_Pharmacy

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 安装依赖
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 启动智能体页面

```bash
python -m streamlit run app.py
```

启动后，浏览器页面会显示：

```text
查宝（药店版）
designed by DriftMousie
```

首次使用流程：

1. 输入 DeepSeek API Key；
2. 点击“保存并验证密钥”；
3. 验证成功后，查宝会发送自我介绍；
4. 把销售端、医保端、处方端文件复制到页面显示的本地工作目录；
5. 根据对话提示生成列名配置、执行冲销检查和数据比对。

### 命令行模式

如果只想运行原始命令行版本：

```bash
python pharmacy_analysis.py
```

菜单功能：

```text
1. 生成列名配置表
2. 退货冲销检查
3. 销售端与医保端比对
4. 处方端医保端比对
0. 退出
```

## 从源码部署为 EXE 文件

本项目已提供 Windows 单文件打包脚本：

```text
build_windows.bat
```

在 Windows 上进入项目目录后执行：

```bat
build_windows.bat
```

脚本会自动完成：

1. 创建 `.venv` 虚拟环境；
2. 安装项目依赖；
3. 安装 PyInstaller；
4. 执行语法检查；
5. 执行单元测试；
6. 使用 PyInstaller `--onefile` 打包；
7. 生成单文件程序。

打包结果：

```text
dist\ChaBao_Pharmacy.exe
```

运行 exe 后：

1. 控制台会显示本地访问地址，默认是：

```text
http://127.0.0.1:8501
```

2. 程序不会自动弹出浏览器，用户需要手动打开该地址；
3. 页面会显示当前工作目录；
4. 用户可以点击“打开工作目录”快速打开文件夹；
5. 销售端、医保端、处方端文件建议放在 exe 所在文件夹内。

说明：

- 单文件 exe 首次启动可能较慢，这是 PyInstaller 解压依赖导致的正常现象。
- 程序图标来自 `resources/image.jpg` 转换生成的 `resources/app_icon.ico`。
- 处方药目录默认已经内置；如需使用新版目录，可将 `处方药目录.xlsx` 放到工作目录顶层，程序会优先使用用户提供的目录。

## 使用建议

推荐筛查顺序：

1. 将药店销售端、医保端、处方端数据复制到工作目录；
2. 生成 `列名配置.xlsx`；
3. 按实际表头修改“用户录入列名”列；
4. 告诉查宝“我的列名配置修改好了”；
5. 执行退货冲销检查；
6. 根据冲销结果清理销售端数据；
7. 执行销售端与医保端比对；
8. 如需检查处方风险，再执行处方端医保端比对。

## 数据与隐私说明

- 销售、医保、处方明细均在本机读取和处理。
- DeepSeek 主要用于理解用户对话、生成引导和解释错误。
- 不应将完整业务明细发送给模型。
- API Key 验证成功后会保存到本地 `deepseek_config.json`，请不要上传或分享该文件。

## 项目状态

当前项目仍处于测试版本。建议在正式使用前，先用少量样例数据验证列名配置和输出结果是否符合预期。

欢迎提交 Issue 和 Pull Request。

## 联系方式

联系方式：etherhare@gmail.com
