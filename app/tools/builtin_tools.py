# -*- coding: utf-8 -*-
"""Agent 内置工具 — calculator + current_time"""

from datetime import datetime

from langchain.tools import tool
from loguru import logger


@tool
def calculator(expression: str) -> str:
    """执行数学计算。

    当用户需要进行数学运算时调用，支持加减乘除、乘方、括号等基本运算。
    例如："123 * 456 等于多少？""计算 (3.14 * 2) ^ 3"

    Args:
        expression: 数学表达式字符串，如 "123 * 456"、"sqrt(16)"、"2 ** 10"

    Returns:
        计算结果
    """
    logger.info(f" 计算: {expression}")

    try:
        # 安全的白名单函数
        safe_globals = {
            "__builtins__": {},
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "pow": pow,
            "int": int,
            "float": float,
        }

        # 从 math 引入常用函数
        import math
        safe_globals.update({
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "log10": math.log10,
            "pi": math.pi,
            "e": math.e,
            "ceil": math.ceil,
            "floor": math.floor,
        })

        result = eval(expression, safe_globals, {})

        # 格式化输出
        if isinstance(result, float):
            result_str = f"{result:.6f}".rstrip("0").rstrip(".")
        else:
            result_str = str(result)

        return f" {expression} = {result_str}"

    except SyntaxError:
        return f"表达式「{expression}」语法错误，请输入合法的数学表达式。"
    except ZeroDivisionError:
        return "除数不能为零。"
    except Exception as e:
        return f"计算失败: {str(e)[:200]}"


@tool
def get_current_time(format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前的日期和时间。

    当用户询问当前时间、日期、星期几等信息时调用。
    例如："现在几点了？""今天是几号？""今天星期几？"

    Args:
        format_str: 时间格式字符串，一般不需要传，使用默认值即可

    Returns:
        当前日期时间的格式化字符串
    """
    logger.info(" 查询当前时间")

    now = datetime.now()
    weekday_map = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

    return (
        f" 当前时间：{now.strftime(format_str)}\n"
        f"   {weekday_map[now.weekday()]}"
    )
