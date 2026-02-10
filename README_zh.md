# EasyPaper

**让学术论文变得简单易读。**

EasyPaper 是一个可本地部署的 Web 应用，帮助你更轻松地阅读英文学术论文：

- **翻译** — 将英文论文翻译为中文，保留原始排版、图片和公式
- **简化** — 将复杂英文词汇简化为 A2/B1 级别（英译英改写）

上传一个 PDF，获取一份干净、易读的版本 — 所有图表、公式和格式完整保留。

[English](README.md)

## 效果展示

### 翻译为中文
![翻译为中文](imgs/img-0.png)

### 简化英文
![简化英文](imgs/img-1.png)

### 保留排版技术
![排版分析](imgs/test.png)

## 功能特点

- PDF 输入，PDF 输出 — 保留原始排版、图片和数学公式
- 英文 → 中文翻译，格式不变
- 英文 → 简单英文词汇简化（CEFR A2/B1 级别）
- 实时处理进度展示
- 原文与处理结果并排对比阅读
- HTML 预览 + PDF 下载
- 本地部署，使用自己的 LLM API Key

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- 一个 LLM API Key（如 OpenRouter 或任何 OpenAI 兼容 API）

### 启动后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 配置
cp config/config.example.yaml config/config.yaml
# 编辑 config.yaml — 填入你的 API Key，选择模型

uvicorn app.main:app --reload
```

### 启动前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 http://localhost:5173 即可使用。

## 配置说明

编辑 `backend/config/config.yaml`：

```yaml
llm:
  api_key: "YOUR_API_KEY"        # 你的 LLM API Key
  base_url: "https://api.xxx.com/v1"  # API 地址
  model: "gemini-2.5-flash"      # 处理模型
  judge_model: "gemini-2.5-flash"
processing:
  max_pages: 100                  # 最大页数限制
  preview_html: true
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | FastAPI, PyMuPDF, ReportLab, pdf2zh |
| 前端 | React, TypeScript, Vite, Tailwind CSS, Radix UI |
| 数据库 | SQLite（默认） |

## 开源协议

MIT
