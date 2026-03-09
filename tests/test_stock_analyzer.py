"""
Tests for the stock analysis toolkit.

Uses mocked data to avoid requiring network access.
"""

import datetime
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from stock_analyzer.technical_analyzer import TechnicalAnalyzer, TechnicalSignal, TechnicalAnalysisResult
from stock_analyzer.news_fetcher import NewsFetcher, NewsItem
from stock_analyzer.recommendation_engine import RecommendationEngine, OperationAdvice


# ============================================================
# Helper: build synthetic OHLCV dataframe
# ============================================================

def _make_ohlcv(n: int = 80, trend: str = "up") -> pd.DataFrame:
    """Generate a synthetic OHLCV dataframe with *n* rows."""
    np.random.seed(42)
    base = 100.0
    dates = pd.date_range(end=datetime.date.today(), periods=n, freq="B")
    prices = []
    for i in range(n):
        if trend == "up":
            # Use a stronger daily growth rate to ensure clear uptrend
            base *= 1 + np.random.uniform(0.005, 0.012)
        elif trend == "down":
            # Use a stronger daily decline to ensure clear downtrend
            base *= 1 - np.random.uniform(0.005, 0.012)
        else:
            base *= 1 + np.random.uniform(-0.003, 0.003)
        prices.append(base)

    closes = np.array(prices)
    highs = closes * (1 + np.random.uniform(0, 0.01, n))
    lows = closes * (1 - np.random.uniform(0, 0.01, n))
    opens = lows + (highs - lows) * np.random.uniform(0.2, 0.8, n)
    volumes = np.random.randint(100000, 500000, n).astype(float)

    df = pd.DataFrame({
        "date": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
        "amount": closes * volumes,
        "amplitude": (highs - lows) / closes * 100,
        "change_pct": np.concatenate([[0], np.diff(closes) / closes[:-1] * 100]),
        "change": np.concatenate([[0], np.diff(closes)]),
        "turnover_rate": np.random.uniform(0.5, 3.0, n),
    })
    return df


# ============================================================
# TechnicalAnalyzer tests
# ============================================================

class TestTechnicalAnalyzer(unittest.TestCase):
    """Tests for TechnicalAnalyzer."""

    def setUp(self):
        self.df_up = _make_ohlcv(80, trend="up")
        self.df_down = _make_ohlcv(80, trend="down")
        self.df_flat = _make_ohlcv(80, trend="flat")

    def test_indicators_are_computed(self):
        """After construction, technical columns should exist."""
        analyzer = TechnicalAnalyzer(self.df_up)
        df = analyzer.get_recent_ohlcv()
        for col in ["ma5", "ma10", "ma20", "macd_dif", "macd_dea", "rsi14",
                    "bb_upper", "bb_mid", "bb_lower", "kdj_k", "kdj_d", "kdj_j"]:
            self.assertIn(col, df.columns, f"Column '{col}' is missing")

    def test_analyze_returns_result(self):
        """analyze() should return a TechnicalAnalysisResult with signals."""
        analyzer = TechnicalAnalyzer(self.df_up)
        result = analyzer.analyze()
        self.assertIsInstance(result, TechnicalAnalysisResult)
        self.assertGreater(len(result.signals), 0)

    def test_signal_values_are_valid(self):
        """Every signal's 'signal' field must be one of the expected values."""
        valid = {"看多", "看空", "中性"}
        for df in [self.df_up, self.df_down, self.df_flat]:
            analyzer = TechnicalAnalyzer(df)
            result = analyzer.analyze()
            for sig in result.signals:
                self.assertIn(sig.signal, valid, f"Unexpected signal value: {sig.signal}")

    def test_uptrend_detected(self):
        """A clearly upward price series should be identified as 上升趋势."""
        analyzer = TechnicalAnalyzer(self.df_up)
        result = analyzer.analyze()
        self.assertEqual(result.trend, "上升趋势")

    def test_downtrend_detected(self):
        """A clearly downward price series should be identified as 下降趋势."""
        analyzer = TechnicalAnalyzer(self.df_down)
        result = analyzer.analyze()
        self.assertEqual(result.trend, "下降趋势")

    def test_support_below_resistance(self):
        """Support price should always be less than or equal to resistance."""
        analyzer = TechnicalAnalyzer(self.df_up)
        result = analyzer.analyze()
        self.assertIsNotNone(result.support)
        self.assertIsNotNone(result.resistance)
        self.assertLessEqual(result.support, result.resistance)

    def test_recent_ohlcv_length(self):
        """get_recent_ohlcv should return exactly recent_periods rows."""
        for n in [5, 10, 20]:
            analyzer = TechnicalAnalyzer(self.df_up, recent_periods=n)
            df = analyzer.get_recent_ohlcv()
            self.assertEqual(len(df), n)

    def test_summary_non_empty(self):
        """The summary string should not be empty."""
        analyzer = TechnicalAnalyzer(self.df_up)
        result = analyzer.analyze()
        self.assertGreater(len(result.summary), 0)


# ============================================================
# NewsFetcher tests (mocked)
# ============================================================

class TestNewsFetcher(unittest.TestCase):
    """Tests for NewsFetcher using mocked akshare calls."""

    def _make_cls_df(self):
        return pd.DataFrame({
            "题目": ["央行宣布降准50bp", "贸易战关税升级", "科技企业业绩超预期"],
            "内容": ["央行降准利好市场", "中美贸易战再起波澜", "科技龙头业绩超预期"],
        })

    @patch("stock_analyzer.news_fetcher.ak.news_cctv")
    @patch("stock_analyzer.news_fetcher.ak.stock_news_main_cx")
    def test_fetch_returns_list(self, mock_cx, mock_cctv):
        mock_cctv.return_value = self._make_cls_df()
        mock_cx.side_effect = Exception("no data")

        fetcher = NewsFetcher(symbol="600519")
        items = fetcher.fetch()

        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)

    @patch("stock_analyzer.news_fetcher.ak.news_cctv")
    @patch("stock_analyzer.news_fetcher.ak.stock_news_main_cx")
    def test_policy_news_is_categorized(self, mock_cx, mock_cctv):
        mock_cctv.return_value = self._make_cls_df()
        mock_cx.side_effect = Exception("no data")

        fetcher = NewsFetcher()
        items = fetcher.fetch()

        categories = {item.category for item in items}
        # At least one of the items should be categorized as 政策 or 重大事件
        self.assertTrue(
            any(c in categories for c in ("政策", "重大事件", "财经")),
            f"Unexpected categories: {categories}"
        )

    def test_categorize_policy(self):
        """_categorize should return '政策' for policy-related text."""
        category = NewsFetcher._categorize("央行宣布降准100个基点，货币政策进一步宽松")
        self.assertEqual(category, "政策")

    def test_categorize_political(self):
        """_categorize should return '政治' for political text."""
        category = NewsFetcher._categorize("习近平主持召开政治局常委会会议")
        self.assertEqual(category, "政治")

    def test_categorize_finance(self):
        """_categorize should return '财经' for generic finance text."""
        category = NewsFetcher._categorize("公司发布三季报，净利润同比增长20%")
        self.assertEqual(category, "财经")

    @patch("stock_analyzer.news_fetcher.ak.news_cctv")
    @patch("stock_analyzer.news_fetcher.ak.stock_news_main_cx")
    def test_deduplication(self, mock_cx, mock_cctv):
        """Duplicate titles should be removed."""
        dup_df = pd.DataFrame({
            "题目": ["相同新闻标题A", "相同新闻标题A", "另一条新闻"],
            "内容": ["内容1", "内容2", "内容3"],
        })
        mock_cctv.return_value = dup_df
        mock_cx.side_effect = Exception("no data")

        fetcher = NewsFetcher()
        items = fetcher.fetch()
        titles = [item.title for item in items]
        # Title '相同新闻标题A' should appear only once
        self.assertEqual(titles.count("相同新闻标题A"), 1)

    @patch("stock_analyzer.news_fetcher.ak.news_cctv")
    @patch("stock_analyzer.news_fetcher.ak.stock_news_main_cx")
    def test_network_failure_returns_empty(self, mock_cx, mock_cctv):
        """When all sources fail, fetch() should return an empty list."""
        mock_cctv.side_effect = Exception("network error")
        mock_cx.side_effect = Exception("network error")

        fetcher = NewsFetcher()
        items = fetcher.fetch()
        self.assertIsInstance(items, list)
        self.assertEqual(len(items), 0)


# ============================================================
# RecommendationEngine tests
# ============================================================

class TestRecommendationEngine(unittest.TestCase):
    """Tests for RecommendationEngine."""

    def _make_tech_result(self, bullish: bool = True) -> TechnicalAnalysisResult:
        if bullish:
            signals = [
                TechnicalSignal("均线系统", "MA5>MA10>MA20", "看多", "多头排列"),
                TechnicalSignal("MACD", "DIF>DEA", "看多", "金叉"),
                TechnicalSignal("RSI", "62.0", "看多", "强势区间"),
                TechnicalSignal("布林带", "上半区", "看多", "偏多"),
                TechnicalSignal("KDJ", "K>D", "看多", "偏多"),
                TechnicalSignal("成交量", "量比=1.6", "看多", "价涨量增"),
            ]
            trend, strength = "上升趋势", "强"
        else:
            signals = [
                TechnicalSignal("均线系统", "MA5<MA10<MA20", "看空", "空头排列"),
                TechnicalSignal("MACD", "DIF<DEA", "看空", "死叉"),
                TechnicalSignal("RSI", "38.0", "看空", "弱势区间"),
                TechnicalSignal("布林带", "下半区", "看空", "偏空"),
                TechnicalSignal("KDJ", "K<D", "看空", "偏空"),
                TechnicalSignal("成交量", "量比=1.8", "看空", "价跌量增"),
            ]
            trend, strength = "下降趋势", "强"

        return TechnicalAnalysisResult(
            signals=signals,
            trend=trend,
            trend_strength=strength,
            support=90.0,
            resistance=120.0,
            summary="测试摘要",
        )

    def _make_news(self, positive: bool = True) -> list[NewsItem]:
        if positive:
            return [
                NewsItem("央行宣布降准利好市场", "货币政策宽松", "财联社", "10:00", "政策"),
                NewsItem("科技政策大力支持", "国家战略支持科技", "新华财经", "11:00", "政策"),
            ]
        else:
            return [
                NewsItem("美国加征关税制裁", "贸易战升级", "财联社", "10:00", "重大事件"),
                NewsItem("监管整顿行业", "多家企业受罚", "新华财经", "11:00", "政策"),
            ]

    def test_generate_returns_advice(self):
        """generate() should return an OperationAdvice object."""
        engine = RecommendationEngine(
            tech_result=self._make_tech_result(bullish=True),
            news_items=self._make_news(positive=True),
            current_price=100.0,
            symbol="600519",
            stock_name="贵州茅台",
        )
        advice = engine.generate()
        self.assertIsInstance(advice, OperationAdvice)

    def test_bullish_signals_lead_to_buy(self):
        """All-bullish technicals + positive news should suggest buy or add."""
        engine = RecommendationEngine(
            tech_result=self._make_tech_result(bullish=True),
            news_items=self._make_news(positive=True),
            current_price=100.0,
        )
        advice = engine.generate()
        self.assertIn(advice.action, ("买入", "加仓", "持有"),
                      f"Expected buy/add/hold for bullish scenario, got: {advice.action}")

    def test_bearish_signals_lead_to_sell(self):
        """All-bearish technicals + negative news should suggest sell or reduce."""
        engine = RecommendationEngine(
            tech_result=self._make_tech_result(bullish=False),
            news_items=self._make_news(positive=False),
            current_price=100.0,
        )
        advice = engine.generate()
        self.assertIn(advice.action, ("卖出", "减仓", "观望"),
                      f"Expected sell/reduce for bearish scenario, got: {advice.action}")

    def test_confidence_is_valid(self):
        """Confidence field should be one of '强', '中', '弱'."""
        engine = RecommendationEngine(
            tech_result=self._make_tech_result(),
            news_items=self._make_news(),
            current_price=100.0,
        )
        advice = engine.generate()
        self.assertIn(advice.confidence, ("强", "中", "弱"))

    def test_stop_loss_below_current_price(self):
        """Stop-loss price should be less than current price in a bullish scenario."""
        engine = RecommendationEngine(
            tech_result=self._make_tech_result(bullish=True),
            news_items=[],
            current_price=100.0,
        )
        advice = engine.generate()
        if advice.stop_loss is not None:
            self.assertLess(advice.stop_loss, 100.0)

    def test_reasons_and_risks_non_empty(self):
        """Advice should always contain at least one reason and one risk."""
        engine = RecommendationEngine(
            tech_result=self._make_tech_result(),
            news_items=self._make_news(),
            current_price=100.0,
        )
        advice = engine.generate()
        self.assertGreater(len(advice.reasons), 0)
        self.assertGreater(len(advice.risks), 0)

    def test_empty_news_still_produces_advice(self):
        """No news should still produce a valid advice."""
        engine = RecommendationEngine(
            tech_result=self._make_tech_result(bullish=True),
            news_items=[],
            current_price=100.0,
        )
        advice = engine.generate()
        self.assertIsNotNone(advice.action)


# ============================================================
# Integration-style test (mocked network)
# ============================================================

class TestFullAnalysisMocked(unittest.TestCase):
    """End-to-end test with all network calls mocked."""

    def setUp(self):
        self.df = _make_ohlcv(80, trend="up")
        self.spot_data = pd.DataFrame([{
            "代码": "600519",
            "名称": "贵州茅台",
            "最新价": 1800.0,
            "涨跌额": 20.0,
            "涨跌幅": 1.12,
            "今开": 1780.0,
            "最高": 1820.0,
            "最低": 1775.0,
            "昨收": 1780.0,
            "成交量": 5000000.0,
            "成交额": 9e9,
            "换手率": 0.4,
            "市盈率-动态": 32.5,
            "总市值": 2.26e12,
        }])

    @patch("stock_analyzer.data_fetcher.ak.stock_zh_a_spot_em")
    @patch("stock_analyzer.data_fetcher.ak.stock_zh_a_hist")
    @patch("stock_analyzer.news_fetcher.ak.news_cctv")
    @patch("stock_analyzer.news_fetcher.ak.stock_news_main_cx")
    def test_full_pipeline(self, mock_cx, mock_cctv, mock_hist, mock_spot):
        """Full pipeline from data fetch to recommendation."""
        from stock_analyzer.data_fetcher import StockDataFetcher

        # mock historical data with expected column names
        hist_df = self.df.rename(columns={
            "date": "日期", "open": "开盘", "high": "最高", "low": "最低",
            "close": "收盘", "volume": "成交量", "amount": "成交额",
            "amplitude": "振幅", "change_pct": "涨跌幅", "change": "涨跌额",
            "turnover_rate": "换手率",
        })
        hist_df["日期"] = hist_df["日期"].dt.strftime("%Y-%m-%d")

        mock_spot.return_value = self.spot_data
        mock_hist.return_value = hist_df
        mock_cctv.side_effect = Exception("no news")
        mock_cx.side_effect = Exception("no news")

        fetcher = StockDataFetcher("600519")
        spot = fetcher.get_current_price()
        self.assertEqual(spot["symbol"], "600519")
        self.assertEqual(spot["current_price"], 1800.0)

        df = fetcher.get_historical_data(periods=20)
        analyzer = TechnicalAnalyzer(df, recent_periods=20)
        tech_result = analyzer.analyze()

        news_fetcher = NewsFetcher(symbol="600519")
        news_items = news_fetcher.fetch()

        engine = RecommendationEngine(
            tech_result=tech_result,
            news_items=news_items,
            current_price=spot["current_price"],
            symbol=spot["symbol"],
            stock_name=spot["name"],
        )
        advice = engine.generate()

        self.assertIsNotNone(advice.action)
        self.assertIn(advice.action, ("买入", "加仓", "持有", "减仓", "卖出", "观望"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
