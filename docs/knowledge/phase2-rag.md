# 阶段 2：RAG 知识库检索

> 目标：让 Agent 能基于产品文档回答问题，从"通用闲聊"升级为"IntelliDesk 官方客服"。

---

## 1. 阶段 2 改了什么

### 新建文件

| 文件 | 职责 |
|---|---|
| `app/rag/loader.py` | 文档加载 → Markdown 按标题切分 → 向量化 → 存入 ChromaDB → 提供检索接口 |
| `app/tools/knowledge_search.py` | 将检索接口封装为 LangChain Tool，Agent 可自主调用 |

### 修改文件

| 文件 | 改动 |
|---|---|
| `app/agent.py` | System Prompt 从泛用客服 → IntelliDesk SaaS 产品专家；新增「先检索再回答」规则 |
| `app/routers/chat.py` | 新增 `POST /api/documents/reindex` 重建索引；Agent 初始化时注入 `search_knowledge_base` 工具 |
| `main.py` | 启动时自动调用 `build_index()` 构建知识库索引 |
| `requirements.txt` | 新增 `sentence-transformers`（本地 Embedding 模型） |

---

## 2. RAG 全链路详解

### 2.1 整体数据流

```
docs/products/*.md          ← 3 份产品文档
    │
    ▼
loader.py: _load_and_split_docs()
    │
    ├── MarkdownHeaderTextSplitter   # 按 # / ## / ### 标题边界切
    ├── RecursiveCharacterTextSplitter  # 超 500 字符再切一刀
    │
    ▼
[{content, metadata}, ...]   # 约 40-60 个文档块
    │
    ▼
loader.py: build_index()
    │
    ├── SentenceTransformerEmbeddingFunction("all-MiniLM-L6-v2")
    │       │
    │       └── 将文本块转为 384 维向量（本地运行，免费）
    │
    ├── Chroma.from_dicts() → 存入 ChromaDB
    │       │
    │       └── 持久化到 data/chroma_db/
    │
    ▼
search_knowledge(query)
    │
    ├── Chroma.similarity_search_with_score(query, k=3)
    │       │
    │       └── 用户问题也转成 384 维向量 → 余弦相似度 → Top-3
    │
    ▼
[{content, source, score}, ...]
    │
    ▼
Agent 基于检索结果生成最终回答
```

### 2.2 为什么用 TF-IDF 而不是向量 Embedding？

最初的方案是 ChromaDB + 本地 Embedding 模型（`all-MiniLM-L6-v2`），但实际踩了坑：

| 方案 | 问题 |
|---|---|
| `sentence-transformers`（PyTorch） | 依赖 PyTorch ~2GB，下载极慢 |
| ChromaDB ONNX Embedding | 模型 80MB，HuggingFace CDN 限速 ~30KB/s，需 40+ 分钟 |
| OpenAI `text-embedding-3-small` | 需要 OpenAI API Key（目前只有 DeepSeek Key） |
| DeepSeek Embedding | DeepSeek 不提供 Embedding API |

**最终方案：scikit-learn TF-IDF + 余弦相似度**

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# 构建索引
vectorizer = TfidfVectorizer(
    max_features=5000,        # 词汇表上限
    ngram_range=(1, 2),       # 单字 + 双字组合
    analyzer="char_wb",       # 字符级分析（中英文兼容）
)
tfidf_matrix = vectorizer.fit_transform([c["content"] for c in chunks])

# 检索
query_vec = vectorizer.transform([query])
scores = cosine_similarity(query_vec, tfidf_matrix)
top_k = np.argsort(scores)[::-1][:3]
```

**优点**：零网络依赖，启动瞬时完成（<0.1s），对产品文档这类关键词密集文本效果足够好。

**缺点**：无法理解同义词（"退款" 和 "退货" 被视为不同词），对长句语义理解不如 Embedding。

**实际效果**：58 个文档块，3281 词汇量，检索准确率满足当前需求。后续可平滑迁移到 Embedding 方案——只需替换 `loader.py` 中的 `build_index()` 和 `search_knowledge()`，其余代码不变。

### 2.3 两层切分策略

```
原始 Markdown 文档
    │
    ▼ 第一层：MarkdownHeaderTextSplitter
按标题层级切分
    ├── "# 产品概述" → 一个 chunk
    ├── "## 快速开始" → 一个 chunk
    │   └── "### 注册账号" → 一个 chunk
    └── ...
    │
    ▼ 第二层：RecursiveCharacterTextSplitter
超 500 字符的 chunk
    ├── chunk_size=500
    ├── chunk_overlap=50   ← 块间重叠 50 字符，防止一句话被切断
    └── separators=["\n\n", "\n", "。", ".", " ", ""]  ← 优先在自然边界切
```

### 2.4 索引存储

当前使用**内存级 TF-IDF 索引**（`_chunks` + `_vectorizer` + `_tfidf_matrix` 三个模块级变量），特点：

- **启动时自动构建**：`main.py` 的 `lifespan` 中调用 `build_index()`，每次启动重新构建
- **构建速度**：3 个文档 58 个块，<0.1 秒
- **检索速度**：毫秒级
- **文档更新后**：调 `POST /api/documents/reindex` 重建；重启服务也会自动重建

```python
# loader.py 中的全局状态
_chunks: list[dict] = []            # 所有文档块
_vectorizer: TfidfVectorizer = None  # TF-IDF 向量器
_tfidf_matrix = None                 # 文档-词频矩阵
_index_ready: bool = False           # 就绪标志
```

后续如需持久化避免每次启动重建，可添加 pickle 序列化到 `data/tfidf_index.pkl`，但当前文档量下无必要。

---

## 3. Agent 工具调用机制

### 3.1 Tool 定义

```python
@tool
def search_knowledge_base(query: str) -> str:
    """检索 IntelliDesk 产品知识库。

    当用户询问以下类型的问题时，**必须**调用此工具：
    - 产品功能、使用方法、操作步骤
    - 计费方案、价格、套餐差异
    - API 集成、技术文档
    ...
    """
```

关键点：
- **`@tool` 装饰器**：LangChain 自动把函数签名 + docstring 转成 OpenAI Function Calling 格式
- **docstring 就是 Prompt**：Agent 根据 docstring 中的描述决定何时调用该工具
- **返回值是字符串**：Agent 把工具返回的文本作为上下文，再生成最终回复

### 3.2 Agent 决策流程（ReAct 模式）

```
用户: "免费版能用 API 吗？"
    │
    ▼
Agent 思考: 用户问的是产品功能问题，必须调用 search_knowledge_base
    │
    ▼
Agent 调用: search_knowledge_base(query="免费版 API 访问 限制")
    │
    ├── 检索 pricing.md → 找到"免费版无 API 访问"
    ├── 检索 faq.md      → 找到"免费版能用 API 吗？不能。"
    │
    ▼
工具返回: 两段相关文档内容
    │
    ▼
Agent 综合: "根据 IntelliDesk 的计费规则，免费版**不支持 API 访问**。
           API 功能是 Pro 版及以上才有的..."
    │
    ▼
返回用户
```

### 3.3 System Prompt 的关键约束

```markdown
## 核心规则（必须遵守）

1. **先检索，再回答**：回答任何关于 IntelliDesk 产品的问题前，
   **必须先调用 search_knowledge_base 工具**检索知识库。

2. **诚实原则**：如果知识库中没有找到相关信息，请如实告知用户。
   不要猜测、编造或提供不确定的答案。
```

这是两条**硬约束**——没有它们，Agent 可能凭训练数据中的"常识"回答，导致信息不准确。

---

## 4. 从阶段 1 到阶段 2 的身份转变

| | 阶段 1 | 阶段 2 |
|---|---|---|
| **角色** | 通用客服"小智" | IntelliDesk 官方客服"小智" |
| **回答范围** | 退换货、售后等通用话题 | IntelliDesk 产品功能、计费、API |
| **知识来源** | LLM 训练数据（可能过时/不准确） | 知识库文档（可控制、可更新） |
| **工具** | 无 | `search_knowledge_base` |
| **回答可靠性** | 低（会编造退货政策） | 高（基于真实文档） |
| **System Prompt** | 泛用模板 | 产品特化 + 严格约束 |

---

## 5. 新增 API 接口

### POST /api/documents/reindex

**用途**：修改产品文档后，调用此接口重建向量索引。

```bash
curl -X POST http://localhost:8000/api/documents/reindex
```

响应：
```json
{
  "status": "success",
  "message": "索引重建完成，共 52 个文档块",
  "chunk_count": 52
}
```

### GET /api/health（增强版）

现在返回知识库状态：
```json
{
  "status": "ok",
  "service": "IntelliDesk",
  "knowledge_base": "52 chunks"
}
```

---

## 6. 踩坑记录

### 6.1 DeepSeek 没有 Embedding API

原本计划用 `openai` 包调 DeepSeek 的 Embedding API，但查了 DeepSeek 文档后发现他们**不提供 Embedding 服务**。

**解决方案**：改用 `sentence-transformers` 的 `all-MiniLM-L6-v2` 本地模型。优点是免费且无需额外 API Key；缺点是首次运行要下载 ~120MB 模型文件。

### 6.2 MarkdownHeaderTextSplitter 需要额外配置

`langchain-text-splitters` 包中的 `MarkdownHeaderTextSplitter` 需要显式声明 `headers_to_split_on`，否则不会自动识别标题：

```python
# 正确写法
MarkdownHeaderTextSplitter(
    headers_to_split_on=[
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
    ]
)
```

---

## 7. 阶段 2 检查清单

- [x] scikit-learn TF-IDF 可用，无需下载模型
- [x] 启动服务时日志显示"TF-IDF 索引就绪"
- [x] `GET /api/health` 返回 `"knowledge_base": "58 chunks"`
- [x] `POST /api/chat {"message": "免费版能用 API 吗？"}` → Agent 调 `search_knowledge_base`，基于文档回答"不能，Pro 版才支持"
- [x] `POST /api/chat {"message": "你好，你是谁？"}` → Agent 不调工具，基于 System Prompt 自我介绍
- [x] `POST /api/documents/reindex` → 返回成功 + chunk_count
- [x] Agent 未编造不存在的信息

### 踩坑记录

1. **sentence-transformers 下载超时**：PyTorch ~2GB，网络环境下载极慢。换 scikit-learn TF-IDF 解决。
2. **ChromaDB ONNX Embedding 下载慢**：HuggingFace CDN 限速 ~30KB/s，80MB 模型需 40+ 分钟。同样用 TF-IDF 替代。
3. **DeepSeek 无 Embedding API**：原计划用 OpenAI 格式调 DeepSeek Embedding，但 DeepSeek 不提供此服务。
4. **scikit-learn 实际已安装**：作为 chromadb 的依赖已在 venv 中，不需要额外安装。
