# 阶段 3：外部工具调用

> 目标：给 Agent 加入天气查询、数学计算、当前时间三个外部工具，实现多工具路由。

---

## 1. 阶段 3 改了什么

### 新建文件

| 文件 | 职责 |
|---|---|
| `app/tools/builtin_tools.py` | 三个通用工具：`get_weather`、`calculator`、`get_current_time` |

### 修改文件

| 文件 | 改动 |
|---|---|
| `app/agent.py` | System Prompt 新增工具列表 + 调用规则 |
| `app/routers/chat.py` | Agent 初始化时注入 4 个工具（知识库 + 3 个通用） |

---

## 2. 三个工具详解

### 2.1 get_weather（天气查询）

**数据源**：[wttr.in](https://wttr.in) — 免费天气 API，无需注册和 API Key。

**调用方式**：`GET https://wttr.in/{city}?format=j1`

```python
@tool
def get_weather(city: str) -> str:
    resp = requests.get(f"https://wttr.in/{city}", params={"format": "j1"}, timeout=10)
    data = resp.json()
    current = data["current_condition"][0]
    return f"{city} 当前天气：{weather_desc}，温度 {temp_c}°C..."
```

**设计要点**：
- `timeout=10`：网络请求不能无限等待，10 秒超时就报错
- `Accept-Language: zh-CN`：让 wttr.in 返回中文天气描述
- 异常处理分两层：网络异常（`RequestException`）和 JSON 解析异常（通用 `Exception`）

### 2.2 calculator（数学计算）

**核心问题**：`eval()` 是危险的——`eval("__import__('os').system('rm -rf /')")` 会执行恶意代码。

**安全方案**：白名单沙箱。

```python
safe_globals = {
    "__builtins__": {},          # 禁用所有内置函数（import/open/exec 等）
    "abs": abs,                  # 只放行安全函数
    "round": round,
    "sqrt": math.sqrt,
    "pi": math.pi,
    ...
}
result = eval(expression, safe_globals, {})  # 第三个参数 {} 禁用局部变量
```

**设计要点**：
- `__builtins__` 设为空字典，彻底封锁 `__import__`、`open`、`exec` 等危险函数
- 手动从 `math` 模块引入 `sqrt`、`sin`、`cos`、`pi`、`log` 等常用函数
- 异常分类处理：语法错误、除零错误、其他异常分别给出不同提示

### 2.3 get_current_time（当前时间）

**实现**：最简单的工具，直接用 Python 标准库 `datetime`。

```python
@tool
def get_current_time(format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    now = datetime.now()
    return f"当前时间：{now.strftime(format_str)}，{weekday_map[now.weekday()]}"
```

**设计要点**：
- 参数设了默认值，LLM 不传参数也能正常返回
- 返回中文星期名，比纯数字更友好
- 无网络依赖，零延迟

---

## 3. Agent 工具路由机制

### 3.1 多工具列表

```python
# chat.py
agent = create_intellidesk_agent(
    tools=[
        search_knowledge_base,  # 产品知识库
        get_weather,            # 天气
        calculator,             # 计算
        get_current_time,       # 时间
    ]
)
```

四个工具同时注入 Agent。LangChain 把每个工具的 name + docstring + 参数 schema 发给 LLM，LLM 根据用户问题自主选择。

### 3.2 System Prompt 中的路由指引

```markdown
| 工具 | 使用场景 |
| `search_knowledge_base` | 查询 IntelliDesk 产品文档 |
| `get_weather` | 查询某个城市的天气 |
| `calculator` | 执行数学计算 |
| `get_current_time` | 获取当前日期和时间 |

调用规则：
- 产品相关问题 → 必须调 search_knowledge_base
- 天气 → 调 get_weather
- 数学计算 → 调 calculator
- 时间 → 调 get_current_time
- 闲聊 → 不调任何工具，直接回复
```

### 3.3 路由决策流程

```
用户: "今天北京天气怎么样？"
    │
    ▼
LLM 分析: 关键词"天气"+"北京" → 匹配 get_weather
    │
    ▼
调用 get_weather(city="Beijing")
    │
    ▼
返回天气数据 → LLM 综合 → 回复用户


用户: "345 + 678 * 2 等于多少？"
    │
    ▼
LLM 分析: 包含数字和运算符 → 匹配 calculator
    │
    ▼
调用 calculator(expression="345 + 678 * 2")
    │
    ▼
返回 1701 → LLM → 回复用户


用户: "你好，你是谁？"
    │
    ▼
LLM 分析: 闲聊，不匹配任何工具
    │
    ▼
直接基于 System Prompt 回复（不调工具）
```

---

## 4. 验证结果

| 问题 | 调用工具 | 结果 |
|---|---|---|
| 「免费版能上传多大的文件？」 | `search_knowledge_base` | 单文件 5MB，知识库 10MB ✅ |
| 「345 + 678 × 2 等于多少？」 | `calculator` | 1701 ✅ |
| 「今天星期几？」 | `get_current_time` | 2026年7月24日，星期五 ✅ |
| 「北京天气怎么样？」 | `get_weather` | Smoky haze, 30°C ✅ |

---

## 5. 阶段 3 检查清单

- [x] `get_weather` 能正常调用 wttr.in 并返回天气数据
- [x] `calculator` 能安全执行数学表达式，恶意代码被沙箱拦截
- [x] `get_current_time` 返回正确日期和中文星期
- [x] Agent 能根据用户问题自动选择正确的工具
- [x] 产品问题仍走 search_knowledge_base（不被新工具干扰）
- [x] 闲聊场景不调任何工具
