from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import statistics
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from io import StringIO
from os import getenv
from typing import Callable, Iterable, List, Sequence, Tuple

MIN_CLOSES_FOR_INDICATORS = 34
FALLBACK_BASE_PRICE = 100.0
FALLBACK_TREND_STEP = 0.4
FALLBACK_OSCILLATION = 0.2
FALLBACK_DATA_POINTS = 40
NEWS_TIME_WINDOW = "1d"
BULLISH_THRESHOLD = 3
BEARISH_THRESHOLD = -2
POSITIVE_WORDS = ("增长", "突破", "支持", "利好", "复苏", "提振", "上调")
NEGATIVE_WORDS = ("冲突", "制裁", "风险", "下调", "紧张", "危机", "下滑")


@dataclass(frozen=True)
class StockMetrics:
    symbol: str
    current_price: float
    closes_20d: List[float]
    volatility_20d: float
    trend_20d: float
    sma5: float
    sma10: float
    rsi14: float
    macd: float
    macd_signal: float


@dataclass(frozen=True)
class NewsItem:
    title: str
    source: str
    published: str


@dataclass(frozen=True)
class NewsSentiment:
    score: int
    positives: int
    negatives: int


@dataclass(frozen=True)
class AnalysisResult:
    stock: StockMetrics
    sentiment: NewsSentiment
    political_events: List[NewsItem]
    policy_news: List[NewsItem]
    recommendation: str
    reasons: List[str]
    source_note: str


def fetch_stooq_prices(symbol: str) -> List[float]:
    normalized = symbol.lower()
    if "." not in normalized:
        normalized = f"{normalized}.us"
    url = f"https://stooq.com/q/d/l/?s={normalized}&i=d"
    with urllib.request.urlopen(url, timeout=10) as response:
        csv_text = response.read().decode("utf-8", errors="ignore")
    reader = csv.DictReader(StringIO(csv_text))
    closes: List[float] = []
    for row in reader:
        value = row.get("Close")
        if not value:
            continue
        try:
            close = float(value)
            if close <= 0:
                continue
            closes.append(close)
        except ValueError:
            continue
    if len(closes) < MIN_CLOSES_FOR_INDICATORS:
        raise ValueError(f"股票 {symbol} 历史数据不足 {MIN_CLOSES_FOR_INDICATORS} 个交易日，无法分析")
    return closes


def _ema(values: Sequence[float], period: int) -> float:
    if len(values) < period:
        raise ValueError("EMA 计算所需数据不足")
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for price in values[period:]:
        ema = (price - ema) * k + ema
    return ema


def _ema_series(values: Sequence[float], period: int) -> List[float]:
    if len(values) < period:
        raise ValueError("EMA 计算所需数据不足")
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    series = [ema]
    for price in values[period:]:
        ema = (price - ema) * k + ema
        series.append(ema)
    return series


def _rsi14(values: Sequence[float]) -> float:
    if len(values) < 15:
        raise ValueError("RSI 计算所需数据不足")
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(delta, 0) for delta in deltas]
    losses = [max(-delta, 0) for delta in deltas]
    avg_gain = sum(gains[:14]) / 14
    avg_loss = sum(losses[:14]) / 14

    for i in range(14, len(deltas)):
        avg_gain = ((avg_gain * 13) + gains[i]) / 14
        avg_loss = ((avg_loss * 13) + losses[i]) / 14

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_stock_metrics(symbol: str, closes: Sequence[float]) -> StockMetrics:
    if len(closes) < MIN_CLOSES_FOR_INDICATORS:
        raise ValueError(f"技术指标分析至少需要 {MIN_CLOSES_FOR_INDICATORS} 个交易日数据")
    closes_20d = list(closes[-20:])
    current_price = closes_20d[-1]
    returns = [
        (closes_20d[i] - closes_20d[i - 1]) / closes_20d[i - 1]
        for i in range(1, len(closes_20d))
    ]
    volatility_20d = statistics.pstdev(returns) * math.sqrt(252)
    trend_20d = (closes_20d[-1] - closes_20d[0]) / closes_20d[0]
    sma5 = sum(closes[-5:]) / 5
    sma10 = sum(closes[-10:]) / 10
    ema12_series = _ema_series(closes, 12)
    ema26_series = _ema_series(closes, 26)
    macd_series = [
        ema12_series[i + (26 - 12)] - ema26_series[i]
        for i in range(len(ema26_series))
    ]
    macd = macd_series[-1]
    macd_signal = _ema(macd_series, 9)
    rsi14 = _rsi14(closes)
    return StockMetrics(
        symbol=symbol.upper(),
        current_price=current_price,
        closes_20d=closes_20d,
        volatility_20d=volatility_20d,
        trend_20d=trend_20d,
        sma5=sma5,
        sma10=sma10,
        rsi14=rsi14,
        macd=macd,
        macd_signal=macd_signal,
    )


def fetch_google_news(query: str, max_items: int = 5) -> List[NewsItem]:
    encoded = urllib.parse.quote_plus(query)
    rss_url = (
        "https://news.google.com/rss/search"
        f"?q={encoded}+when:{NEWS_TIME_WINDOW}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    )
    with urllib.request.urlopen(rss_url, timeout=10) as response:
        xml_text = response.read()

    root = ET.fromstring(xml_text)
    items = []
    for item in root.findall(".//item")[:max_items]:
        title = (item.findtext("title") or "").strip()
        source = (item.findtext("source") or "未知来源").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if title:
            items.append(NewsItem(title=title, source=source, published=pub))
    return items


def fetch_political_and_policy_news(max_items: int = 5) -> Tuple[List[NewsItem], List[NewsItem]]:
    political = fetch_google_news("重大 政治 事件", max_items=max_items)
    policy = fetch_google_news("国家 政策 发布", max_items=max_items)
    return political, policy


def analyze_news_sentiment(news: Iterable[NewsItem]) -> NewsSentiment:
    score = 0
    positives = 0
    negatives = 0
    for item in news:
        title = item.title
        pos = sum(word in title for word in POSITIVE_WORDS)
        neg = sum(word in title for word in NEGATIVE_WORDS)
        positives += pos
        negatives += neg
        score += pos - neg
    return NewsSentiment(score=score, positives=positives, negatives=negatives)


def generate_recommendation(stock: StockMetrics, sentiment: NewsSentiment) -> tuple[str, List[str]]:
    score = 0
    reasons: List[str] = []

    if stock.sma5 > stock.sma10:
        score += 1
        reasons.append("短期均线（SMA5）高于中期均线（SMA10），趋势偏强。")
    else:
        score -= 1
        reasons.append("短期均线（SMA5）低于中期均线（SMA10），趋势偏弱。")

    if stock.macd > stock.macd_signal:
        score += 1
        reasons.append("MACD 位于信号线上方，动量偏多。")
    else:
        score -= 1
        reasons.append("MACD 位于信号线下方，动量偏空。")

    if stock.rsi14 > 70:
        score -= 1
        reasons.append("RSI 超过 70，存在短线过热风险。")
    elif stock.rsi14 < 30:
        score += 1
        reasons.append("RSI 低于 30，存在超跌反弹机会。")
    else:
        reasons.append("RSI 处于中性区间。")

    if stock.trend_20d > 0:
        score += 1
        reasons.append("近 20 个交易日总体上涨。")
    else:
        score -= 1
        reasons.append("近 20 个交易日总体下跌。")

    if sentiment.score > 0:
        score += 1
        reasons.append("消息面整体偏正向。")
    elif sentiment.score < 0:
        score -= 1
        reasons.append("消息面整体偏负向。")
    else:
        reasons.append("消息面中性。")

    if score >= BULLISH_THRESHOLD:
        recommendation = "偏多（可考虑分批买入）"
    elif score <= BEARISH_THRESHOLD:
        recommendation = "偏空（建议控制仓位或观望）"
    else:
        recommendation = "中性（建议等待更明确信号）"
    return recommendation, reasons


def analyze_stock(
    symbol: str,
    price_provider: Callable[[str], Sequence[float]] = fetch_stooq_prices,
    news_provider: Callable[[int], Tuple[List[NewsItem], List[NewsItem]]] = fetch_political_and_policy_news,
) -> AnalysisResult:
    source_note = "数据来源：在线行情与公开新闻 RSS"
    try:
        closes = list(price_provider(symbol))
    except Exception:
        closes = [
            FALLBACK_BASE_PRICE + i * FALLBACK_TREND_STEP + ((-1) ** i) * FALLBACK_OSCILLATION
            for i in range(FALLBACK_DATA_POINTS)
        ]
        source_note = "数据来源：在线行情不可用，已切换为内置示例行情数据"
    stock = calculate_stock_metrics(symbol, closes)

    max_items = int(getenv("STOCK_NEWS_MAX_ITEMS", "5"))
    try:
        political, policy = news_provider(max_items)
    except Exception:
        political, policy = [], []
    sentiment = analyze_news_sentiment([*political, *policy])
    recommendation, reasons = generate_recommendation(stock, sentiment)
    return AnalysisResult(
        stock=stock,
        sentiment=sentiment,
        political_events=political,
        policy_news=policy,
        recommendation=recommendation,
        reasons=reasons,
        source_note=source_note,
    )


def _format_news(items: Sequence[NewsItem]) -> str:
    if not items:
        return "  - 今日暂无可用新闻数据（或抓取失败）"
    return "\n".join(f"  - {item.title} [{item.source}]" for item in items)


def render_report(result: AnalysisResult) -> str:
    stock = result.stock
    lines = [
        f"股票: {stock.symbol}",
        f"当前价格: {stock.current_price:.2f}",
        f"20日趋势: {stock.trend_20d:.2%}",
        f"20日年化波动率: {stock.volatility_20d:.2%}",
        f"SMA5/SMA10: {stock.sma5:.2f}/{stock.sma10:.2f}",
        f"RSI14: {stock.rsi14:.2f}",
        f"MACD/Signal: {stock.macd:.4f}/{stock.macd_signal:.4f}",
        "",
        "今日重大政治事件:",
        _format_news(result.political_events),
        "",
        "今日国家政策相关新闻:",
        _format_news(result.policy_news),
        "",
        f"消息面情绪得分: {result.sentiment.score} (正向关键词: {result.sentiment.positives}, 负向关键词: {result.sentiment.negatives})",
        f"操作建议: {result.recommendation}",
        result.source_note,
        "建议依据:",
        *[f"- {reason}" for reason in result.reasons],
        f"分析时间: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="股票技术面 + 消息面综合分析工具")
    parser.add_argument("symbol", help="股票代码，如 AAPL、MSFT")
    args = parser.parse_args()
    result = analyze_stock(args.symbol)
    print(render_report(result))


if __name__ == "__main__":
    main()
