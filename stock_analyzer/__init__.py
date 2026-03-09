"""
股票分析工具包 - Stock Analysis Toolkit

提供以下功能:
- 查询股票当前价格及近20个交易日的趋势波动
- 技术指标分析 (MA, MACD, RSI, 布林带, 成交量)
- 重大政治事件和国家政策资讯查询
- 结合消息面给出操作建议
"""

from .data_fetcher import StockDataFetcher
from .technical_analyzer import TechnicalAnalyzer
from .news_fetcher import NewsFetcher
from .recommendation_engine import RecommendationEngine

__all__ = [
    "StockDataFetcher",
    "TechnicalAnalyzer",
    "NewsFetcher",
    "RecommendationEngine",
]
