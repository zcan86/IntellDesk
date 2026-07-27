# 阶段 0：环境搭建与项目初始化

> 目标：把工具链配好，确保能跑通一个最简单的 FastAPI + LLM 调用。

---

## 1. 项目目录结构设计

```
D:/IntellDesk/
├── .env                      # 真实密钥（不提交 Git）
├── .env.example              # 配置模板（提交 Git）
├── .gitignore                # Git 忽略规则
├── requirements.txt          # 依赖清单
├── main.py                   # FastAPI 入口
├── test_llm.py               # LLM 连通性测试脚本
├── app/                      # 业务代码
│   ├── __init__.py
│   ├── config.py             # 全局配置
│   ├── routers/              # API 路由
│   │   ├── __init__.py
│   │   └── chat.py
│   ├── rag/                  # RAG 模块（阶段 2）
│   │   └── __init__.py
│   └── tools/                # Agent 工具（阶段 3）
│       └── __init__.py
├── static/                   # 前端静态文件（阶段 5）
│   └── index.html
├── data/                     # 运行时数据
│   └── uploads/              # 用户上传的文档
├── tests/                    # 测试
│   └── __init__.py
└── venv/                     # Python 虚拟环境（不提交 Git）
```

### 设计原则

- **`main.py` 放根目录**：FastAPI 惯例，`python main.py` 一键启动，不用 `cd` 到子目录
- **`app/` 是纯逻辑包**：不含启动入口，可以被 `main.py` 和 `test_llm.py` 等任何脚本引用
- **空 `__init__.py`**：把目录标记为 Python 包，允许 `from app.xxx import yyy`

---

## 2. Python 虚拟环境

### 为什么需要？

你电脑上可能有多个 Python 项目：

```
项目 A 需要 langchain==1.1.0
项目 B 需要 langchain==0.3.0
```

全局安装会冲突。**虚拟环境 = 每个项目有自己的独立 Python + 包**，互不影响。

### 操作步骤

```bash
# 1. 创建虚拟环境（只需一次）
cd D:/IntellDesk
python -m venv venv

# 2. 激活（每次开发前都要执行）
# Windows:
venv\Scripts\activate
# 终端前面出现 (venv) 即成功

# 3. 安装依赖
pip install -r requirements.txt

# 4. 退出虚拟环境
deactivate
```

### 核心依赖清单

| 类别 | 包 | 用途 |
|---|---|---|
| Web | `fastapi`, `uvicorn` | HTTP 服务和 ASGI 服务器 |
| 配置 | `pydantic`, `pydantic-settings`, `python-dotenv` | 从 `.env` 加载配置，自动校验 |
| LLM | `langchain`, `langchain-openai`, `openai`, `langgraph` | Agent 框架 + OpenAI 兼容 SDK |
| RAG | `chromadb`, `langchain-text-splitters`, `langchain-chroma`, `pypdf` | 向量数据库 + 文档切分 + PDF 解析 |
| 工具 | `requests`, `loguru` | HTTP 请求 + 结构化日志 |
| 测试 | `pytest`, `httpx` | 测试框架 + 异步 HTTP 测试客户端 |

---

## 3. 密钥管理：.env 与 .env.example

### .env.example（提交 Git）

告诉其他开发者需要配置哪些变量，但值都是占位符：

```ini
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_NAME=deepseek-chat
HOST=0.0.0.0
PORT=8000
```

### .env（不提交 Git）

从 `.env.example` 复制，填入真实密钥：

```ini
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx   # 真实密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_NAME=deepseek-chat
```

### .gitignore 中的规则

```gitignore
.env                    # 密钥不能泄露
venv/                   # 虚拟环境几百 MB，让其他人自己装
__pycache__/            # Python 编译缓存，每台机器不同
data/chroma_db/         # 向量库数据，运行时生成
*.log                   # 日志文件
```

---

## 4. 配置管理：pydantic-settings

### 为什么不用 `os.getenv()`？

```python
# 原始方式的问题：
api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:                    # 手动校验，每个文件都要写
    raise ValueError("...")
port = int(os.getenv("PORT", 8000)) # 类型要自己转
```

### pydantic-settings 方案

```python
class Settings(BaseSettings):
    DEEPSEEK_API_KEY: str = Field(...)    # ... = 必填，缺了就报错
    PORT: int = Field(8000)               # 自动 int 转换
    AGENT_TEMPERATURE: float = Field(0.7)

    model_config = ConfigDict(
        env_file=".env",                  # 指定 .env 文件路径
        extra="allow",                    # 允许额外字段
    )

settings = Settings()  # 创建时自动加载 .env 并校验
```

**核心价值**：启动时一次性校验所有配置，缺什么立刻报错，不会跑到一半才发现没配 API Key。

---

## 5. FastAPI 基础

### 为什么 FastAPI 而不是 Flask？

| | Flask | FastAPI |
|---|---|---|
| 并发模型 | 同步（一个请求占一个线程） | 异步（async/await，等待时不阻塞） |
| 流式响应 | 支持但复杂 | 原生 StreamingResponse |
| 自动文档 | 需要插件 | 自带 Swagger UI（`/docs`） |
| 数据校验 | 需要手动 | Pydantic 自动校验 |

Agent 后续要做 **SSE 流式输出**，连接要保持打开 10-30 秒，FastAPI 的异步模型更适合。

### 三个核心概念

```python
# 1. 路由：URL → 函数
@app.get("/api/health")
async def health():
    return {"status": "ok"}

# 2. 中间件：请求/响应的拦截层
app.add_middleware(CORSMiddleware, ...)  # 跨域

# 3. 生命周期：启动/关闭的回调
@asynccontextmanager
async def lifespan(app):
    # 启动时执行
    yield
    # 关闭时执行
```

### CORS 中间件

前端跑在 `localhost:5173`，后端跑在 `localhost:8000`。浏览器认为这是两个不同网站，默认禁止跨域请求。CORS 中间件告诉浏览器"允许跨域"：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 开发环境允许所有来源
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 6. LLM 连通性测试

`test_llm.py` 是独立脚本，不依赖 FastAPI，纯粹验证 API 能通：

```python
from openai import OpenAI

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "你是一个智能客服助手。"},
        {"role": "user", "content": "你好"},
    ],
)
print(response.choices[0].message.content)
```

### 为什么用 `openai` 包调 DeepSeek？

DeepSeek 的 API 故意设计成 **OpenAI 兼容格式**。你只改 `base_url` 就能切换厂商：

```python
# DeepSeek
client = OpenAI(base_url="https://api.deepseek.com", api_key="sk-xxx")

# Kimi
client = OpenAI(base_url="https://api.moonshot.cn/v1", api_key="sk-xxx")

# 阿里百炼
client = OpenAI(base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", api_key="sk-xxx")
```

这是行业事实标准，你只需要学一个 SDK。

---

## 阶段 0 检查清单

- [ ] `python -m venv venv` 创建虚拟环境
- [ ] `venv\Scripts\activate` 激活
- [ ] `pip install -r requirements.txt` 安装依赖
- [ ] 复制 `.env.example` → `.env`，填入 `DEEPSEEK_API_KEY`
- [ ] `python test_llm.py` 看到 `✅ DeepSeek API 连接成功`
- [ ] `python main.py` 启动服务，访问 `http://localhost:8000/docs` 看到 Swagger
- [ ] `curl http://localhost:8000/api/health` 返回 `{"status":"ok"}`
- [ ] `git init && git add . && git commit -m "init: phase 0"`（可选）
