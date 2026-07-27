# -*- coding: utf-8 -*-
"""工具模块测试：计算器、时间、天气"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.tools.builtin_tools import calculator, get_current_time


class TestCalculator:
    """数学计算器测试"""

    def test_basic_arithmetic(self):
        result = calculator.invoke("1 + 2")
        assert "3" in result

    def test_multiplication(self):
        result = calculator.invoke("456 * 789")
        assert "359784" in result

    def test_complex_expression(self):
        result = calculator.invoke("(100 + 200) * 3")
        assert "900" in result

    def test_sqrt(self):
        result = calculator.invoke("sqrt(16)")
        assert "4" in result

    def test_division_by_zero(self):
        result = calculator.invoke("1 / 0")
        assert "除数不能为零" in result

    def test_syntax_error(self):
        result = calculator.invoke("1 + * 2")
        assert "语法错误" in result

    def test_no_dangerous_code(self):
        """沙箱测试：危险代码不应执行"""
        result = calculator.invoke("__import__('os').system('ls')")
        # 应返回错误或被拦截
        assert "计算失败" in result or "语法错误" in result


class TestGetCurrentTime:
    """时间工具测试"""

    def test_returns_time(self):
        result = get_current_time.invoke({"format_str": "%Y-%m-%d"})
        assert "2026" in result  # 当前是 2026 年

    def test_returns_weekday(self):
        result = get_current_time.invoke({"format_str": "%Y-%m-%d"})
        assert "星期" in result
