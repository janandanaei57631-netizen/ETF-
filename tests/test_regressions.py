"""Run from the project root: python -m unittest discover -s tests -v."""
import ast
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load_core():
    """Execute real core definitions, without Streamlit UI or data fetching."""
    path = ROOT / "app.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    selected = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in {
            "smart_map_to_etf", "analyze_news"
        }:
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "SMART_MAPPING"
            for target in node.targets
        ):
            selected.append(node)
        elif isinstance(node, ast.Import):
            aliases = [alias for alias in node.names if alias.name == "logging"]
            if aliases:
                selected.append(ast.copy_location(ast.Import(names=aliases), node))
    namespace = {"__name__": "etf_core_under_test"}
    module = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
    exec(compile(module, str(path), "exec"), namespace)
    for name in ("SMART_MAPPING", "smart_map_to_etf", "analyze_news"):
        if name not in namespace:
            raise AssertionError(f"Missing core definition: {name}")
    return namespace


class ETFRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = load_core()

    def analyze_response(self, text):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
        )
        create = Mock(return_value=response)
        client = SimpleNamespace(chat=SimpleNamespace(
            completions=SimpleNamespace(create=create)
        ))
        factory = Mock(return_value=client)
        with patch.dict(self.core, {"api_key": "test-key", "OpenAI": factory}):
            result = self.core["analyze_news"]("测试新闻")
        factory.assert_called_once()
        create.assert_called_once()
        return result

    def test_mapping_empty_or_none_keyword(self):
        for keyword in (None, "", "   ", "无", " 无 "):
            with self.subTest(keyword=keyword):
                self.assertEqual(
                    self.core["smart_map_to_etf"](keyword), (None, None)
                )

    def test_mapping_unknown_or_single_character(self):
        for keyword in ("完全陌生领域", "车"):
            with self.subTest(keyword=keyword):
                self.assertEqual(
                    self.core["smart_map_to_etf"](keyword), (None, None)
                )

    def test_mapping_normal_and_longest_match(self):
        cases = [
            ("半导体", ("512480", "半导体ETF")),
            ("低空经济", ("512660", "军工龙头")),
            ("飞行汽车", ("512660", "军工龙头")),
            ("汽车", ("516110", "汽车ETF")),
        ]
        for keyword, expected in cases:
            with self.subTest(keyword=keyword):
                self.assertEqual(self.core["smart_map_to_etf"](keyword), expected)

    def test_analysis_preserves_valid_fields_including_unmatched(self):
        cases = [
            (" 利好 | 半导体 | 大涨 \n",
             ("利好", "半导体", "512480", "半导体ETF", "大涨")),
            ("中性|无|无", ("中性", "无", None, None, "无")),
            ("利空|完全陌生领域|微跌",
             ("利空", "完全陌生领域", None, None, "微跌")),
        ]
        keys = ("dir", "concept", "etf_code", "etf_name", "impact")
        for raw, values in cases:
            with self.subTest(raw=raw):
                self.assertEqual(self.analyze_response(raw), dict(zip(keys, values)))

    def test_analysis_bad_format_is_rejected_and_logged(self):
        cases = [
            None, "", "没有分隔符", "利好|半导体",
            "利好|半导体|大涨|额外字段", "利好||大涨",
            "看多|半导体|大涨", "利好|半导体|未知",
        ]
        for raw in cases:
            with self.subTest(raw=raw):
                with self.assertLogs(level="WARNING") as logs:
                    self.assertIsNone(self.analyze_response(raw))
                self.assertTrue(any(
                    "AI 返回格式异常" in record.getMessage()
                    for record in logs.records
                ))

    def test_analysis_broken_envelope_is_logged(self):
        factory = Mock()
        factory.return_value.chat.completions.create.return_value = (
            SimpleNamespace(choices=[])
        )
        with patch.dict(self.core, {"api_key": "test-key", "OpenAI": factory}):
            with self.assertLogs(level="ERROR") as logs:
                self.assertIsNone(self.core["analyze_news"]("测试新闻"))
        self.assertTrue(any(
            "AI 分析失败" in record.getMessage() for record in logs.records
        ))

    def test_analysis_api_failure_is_logged(self):
        factory = Mock()
        factory.return_value.chat.completions.create.side_effect = RuntimeError(
            "模拟调用失败"
        )
        with patch.dict(self.core, {"api_key": "test-key", "OpenAI": factory}):
            with self.assertLogs(level="ERROR") as logs:
                self.assertIsNone(self.core["analyze_news"]("测试新闻"))
        self.assertTrue(any(
            "AI 分析失败" in record.getMessage() and record.exc_info
            for record in logs.records
        ))

    def test_missing_key_skips_api(self):
        factory = Mock(side_effect=AssertionError("API must not be called"))
        with patch.dict(self.core, {"api_key": None, "OpenAI": factory}):
            self.assertIsNone(self.core["analyze_news"]("测试新闻"))
        factory.assert_not_called()

    def test_pytz_is_explicitly_declared(self):
        text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        # This project has a flat requirements.txt; do not rely on transitive deps.
        declarations = [
            line.split("#", 1)[0].strip() for line in text.splitlines()
        ]
        self.assertTrue(
            any(re.match(r"^pytz(?=[<>=!~;\[\s]|$)", line, re.I)
                for line in declarations),
            "requirements.txt must explicitly declare pytz",
        )


if __name__ == "__main__":
    unittest.main()
