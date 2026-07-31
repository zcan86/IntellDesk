# -*- coding: utf-8 -*-
"""计算器工具 — 安全沙箱 eval"""

from math import sqrt, sin, cos, tan, log, log10, pi, e, ceil, floor


def calculate(expression: str) -> str:
    """安全沙箱数学计算"""
    safe = {
        "__builtins__": {},
        "abs": abs, "round": round, "min": min, "max": max,
        "sum": sum, "pow": pow, "int": int, "float": float,
        "sqrt": sqrt, "sin": sin, "cos": cos, "tan": tan,
        "log": log, "log10": log10, "pi": pi, "e": e,
        "ceil": ceil, "floor": floor,
    }
    try:
        result = eval(expression, safe, {})
        s = f"{result:.6f}".rstrip("0").rstrip(".") if isinstance(result, float) else str(result)
        return f"📐 {expression} = {s}"
    except SyntaxError:
        return f"表达式「{expression}」语法错误。"
    except ZeroDivisionError:
        return "除数不能为零。"
    except Exception as e:
        return f"计算失败: {str(e)[:200]}"
