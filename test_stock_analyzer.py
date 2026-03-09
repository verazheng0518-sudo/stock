import unittest

from stock_analyzer import (
    NewsItem,
    analyze_news_sentiment,
    analyze_stock,
    calculate_stock_metrics,
    generate_recommendation,
)


class StockAnalyzerTests(unittest.TestCase):
    def test_calculate_stock_metrics(self):
        closes = [100 + i for i in range(40)]
        metrics = calculate_stock_metrics("aapl", closes)
        self.assertEqual(metrics.symbol, "AAPL")
        self.assertEqual(metrics.current_price, 139)
        self.assertEqual(len(metrics.closes_20d), 20)
        self.assertGreater(metrics.trend_20d, 0)
        self.assertGreater(metrics.volatility_20d, 0)

    def test_analyze_news_sentiment(self):
        news = [
            NewsItem(title="国家政策支持科技创新提振市场", source="x", published=""),
            NewsItem(title="地缘冲突风险加剧市场紧张", source="y", published=""),
        ]
        sentiment = analyze_news_sentiment(news)
        self.assertLess(sentiment.score, 0)
        self.assertGreater(sentiment.positives, 0)
        self.assertGreater(sentiment.negatives, 0)

    def test_generate_recommendation_prefers_bullish(self):
        closes = [100 + i for i in range(40)]
        stock = calculate_stock_metrics("msft", closes)
        sentiment = analyze_news_sentiment(
            [NewsItem(title="政策支持带来增长利好", source="z", published="")]
        )
        recommendation, reasons = generate_recommendation(stock, sentiment)
        self.assertNotIn("偏空", recommendation)
        self.assertGreaterEqual(len(reasons), 4)

    def test_analyze_stock_supports_injected_sources(self):
        def fake_prices(symbol: str):
            self.assertEqual(symbol, "TSLA")
            return [200 + i for i in range(35)]

        def fake_news(_max_items: int):
            return (
                [NewsItem(title="重大政治事件保持稳定", source="a", published="")],
                [NewsItem(title="国家政策支持新能源发展", source="b", published="")],
            )

        result = analyze_stock("TSLA", price_provider=fake_prices, news_provider=fake_news)
        self.assertEqual(result.stock.symbol, "TSLA")
        self.assertTrue(result.recommendation)
        self.assertEqual(len(result.political_events), 1)
        self.assertEqual(len(result.policy_news), 1)

    def test_analyze_stock_fallback_when_price_source_unavailable(self):
        def broken_prices(_symbol: str):
            raise RuntimeError("network down")

        result = analyze_stock("NVDA", price_provider=broken_prices, news_provider=lambda _n: ([], []))
        self.assertEqual(result.stock.symbol, "NVDA")
        self.assertIn("内置示例", result.source_note)


if __name__ == "__main__":
    unittest.main()
