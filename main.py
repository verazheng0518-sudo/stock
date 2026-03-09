#!/usr/bin/env python3
"""
股票综合分析工具

功能:
  1. 查询股票当前价格
  2. 展示近20个交易日趋势与波动
  3. 技术指标分析（均线、MACD、RSI、布林带、KDJ、成交量）
  4. 查询今日重大政治事件和国家政策
  5. 结合消息面给出操作建议

使用示例:
  python main.py 600519          # 分析贵州茅台
  python main.py 000001          # 分析平安银行
  python main.py 300750          # 分析宁德时代
  python main.py --help
"""

import argparse
import math
import sys
from typing import Optional

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

from stock_analyzer.data_fetcher import StockDataFetcher
from stock_analyzer.technical_analyzer import TechnicalAnalyzer
from stock_analyzer.news_fetcher import NewsFetcher
from stock_analyzer.recommendation_engine import RecommendationEngine


# ============================================================
# 显示辅助函数
# ============================================================

def _separator(title: str = "", width: int = 70) -> str:
    if title:
        side = (width - len(title) - 2) // 2
        return "=" * side + f" {title} " + "=" * (width - side - len(title) - 2)
    return "=" * width


def _print_section(title: str) -> None:
    print()
    print(_separator(title))


def _print_current_price(spot: dict) -> None:
    """打印实时行情快照。"""
    _print_section("实时行情")
    change_sign = "▲" if spot["change"] >= 0 else "▼"
    change_color_start = "\033[91m" if spot["change"] < 0 else "\033[92m"
    color_end = "\033[0m"

    print(f"  股票代码  : {spot['symbol']}")
    print(f"  股票名称  : {spot['name']}")
    print(f"  最新价格  : {spot['current_price']:.2f} 元")
    print(
        f"  涨跌幅    : {change_color_start}{change_sign} "
        f"{abs(spot['change_pct']):.2f}%  ({change_sign}{abs(spot['change']):.2f}){color_end}"
    )
    print(f"  今日开盘  : {spot['open']:.2f}    昨日收盘: {spot['pre_close']:.2f}")
    print(f"  最高价    : {spot['high']:.2f}    最低价  : {spot['low']:.2f}")
    print(f"  成交量    : {spot['volume'] / 10000:.2f} 万手")
    print(f"  成交额    : {spot['amount'] / 1e8:.2f} 亿元")
    print(f"  换手率    : {spot['turnover_rate']:.2f}%")
    if spot["pe_ratio"]:
        print(f"  市盈率    : {spot['pe_ratio']:.2f}")
    if spot["market_cap"]:
        print(f"  总市值    : {spot['market_cap'] / 1e8:.2f} 亿元")
    print(f"  更新时间  : {spot['timestamp']}")


def _print_historical_trend(analyzer: TechnicalAnalyzer) -> None:
    """打印近20个交易日K线及指标数据。"""
    _print_section("近20个交易日 K线与技术指标")
    df = analyzer.get_recent_ohlcv()

    rows = []
    for _, row in df.iterrows():
        date_str = row["date"].strftime("%m-%d") if hasattr(row["date"], "strftime") else str(row["date"])[:5]
        pct = row["change_pct"]
        sign = "▲" if pct >= 0 else "▼"
        rows.append([
            date_str,
            f"{row['close']:.2f}",
            f"{sign}{abs(pct):.2f}%",
            f"{row['volume'] / 10000:.0f}万",
            f"{row['ma5']:.2f}" if not _isnan(row.get("ma5")) else "-",
            f"{row['ma10']:.2f}" if not _isnan(row.get("ma10")) else "-",
            f"{row['ma20']:.2f}" if not _isnan(row.get("ma20")) else "-",
            f"{row['rsi14']:.1f}" if not _isnan(row.get("rsi14")) else "-",
        ])

    headers = ["日期", "收盘价", "涨跌幅", "成交量", "MA5", "MA10", "MA20", "RSI14"]
    if HAS_TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="simple", numalign="right"))
    else:
        print("  " + "  ".join(f"{h:>8}" for h in headers))
        for r in rows:
            print("  " + "  ".join(f"{v:>8}" for v in r))


def _isnan(val) -> bool:
    try:
        return math.isnan(float(val))
    except Exception:
        return val is None or str(val) in ("nan", "NaN", "")


def _print_technical_analysis(result) -> None:
    """打印技术指标分析结果。"""
    _print_section("技术指标分析")

    signal_icon = {"看多": "🟢", "看空": "🔴", "中性": "⚪"}
    for sig in result.signals:
        icon = signal_icon.get(sig.signal, " ")
        print(f"  {icon} [{sig.name}]  {sig.value}")
        print(f"       {sig.description}")
        print()

    print(f"  📊 综合研判: {result.summary}")


def _print_news(news_items: list) -> None:
    """打印重大政治/政策新闻。"""
    _print_section("今日重大政治事件与国家政策")
    if not news_items:
        print("  暂未获取到相关重大政策/政治事件资讯。")
        return

    category_icon = {
        "政治": "🏛 ",
        "政策": "📋",
        "重大事件": "⚡",
        "财经": "📈",
    }

    shown = 0
    for item in news_items[:15]:  # 最多显示15条
        icon = category_icon.get(item.category, "  ")
        print(f"  {icon} [{item.category}] {item.title}")
        if item.content and item.content.strip():
            # 摘要截断显示
            content_preview = item.content.strip().replace("\n", " ")[:80]
            print(f"       {content_preview}...")
        print(f"       来源: {item.source}  时间: {item.time}")
        print()
        shown += 1
        if shown >= 15:
            break


def _print_recommendation(advice) -> None:
    """打印操作建议。"""
    _print_section("操作建议")

    action_icon = {
        "买入": "🔥",
        "加仓": "📈",
        "持有": "✋",
        "减仓": "📉",
        "卖出": "❌",
        "观望": "👀",
    }
    icon = action_icon.get(advice.action, "▶")

    print(f"  {icon}  操作建议: 【{advice.action}】   置信度: {advice.confidence}")
    print()
    stop_str = f"{advice.stop_loss:.2f}" if advice.stop_loss else "—"
    target_str = f"{advice.target_price:.2f}" if advice.target_price else "—"
    print(f"  止损参考: {stop_str}   目标价参考: {target_str}")
    print()
    print("  主要依据:")
    for r in advice.reasons:
        print(f"    • {r}")
    print()
    print("  风险提示:")
    for r in advice.risks:
        print(f"    ⚠  {r}")


# ============================================================
# 主流程
# ============================================================

def analyze(symbol: str, periods: int = 20) -> None:
    """
    对指定股票执行完整分析并打印报告。

    Parameters
    ----------
    symbol : str
        股票代码，如 ``"600519"`` 或 ``"sz000001"``。
    periods : int
        展示的近期交易日数量，默认 20。
    """
    print()
    print(_separator("股票综合分析报告", 70))
    print(f"  分析股票: {symbol}    数据周期: 近{periods}个交易日")
    print(_separator(width=70))

    # 1. 获取实时行情
    print("\n  ⏳ 正在获取实时行情...")
    fetcher = StockDataFetcher(symbol)
    spot = fetcher.get_current_price()
    _print_current_price(spot)

    # 2. 获取历史数据并计算技术指标
    print("\n  ⏳ 正在获取历史K线数据及计算技术指标...")
    df = fetcher.get_historical_data(periods=periods)
    analyzer = TechnicalAnalyzer(df, recent_periods=periods)
    _print_historical_trend(analyzer)

    # 3. 技术指标分析
    tech_result = analyzer.analyze()
    _print_technical_analysis(tech_result)

    # 4. 获取今日重大新闻
    print("\n  ⏳ 正在获取今日重大政治/政策资讯...")
    news_fetcher = NewsFetcher(symbol=fetcher.symbol)
    news_items = news_fetcher.fetch()
    _print_news(news_items)

    # 5. 操作建议
    engine = RecommendationEngine(
        tech_result=tech_result,
        news_items=news_items,
        current_price=spot["current_price"],
        symbol=spot["symbol"],
        stock_name=spot["name"],
    )
    advice = engine.generate()
    _print_recommendation(advice)

    print()
    print(_separator(width=70))
    print("  ⚠  免责声明: 本报告仅供参考，不构成投资建议。股市有风险，投资需谨慎。")
    print(_separator(width=70))
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="A股股票综合分析工具：技术指标 + 消息面 + 操作建议",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py 600519          # 贵州茅台
  python main.py 000001          # 平安银行
  python main.py 300750          # 宁德时代
  python main.py 601318 -n 30    # 中国平安，近30个交易日
        """,
    )
    parser.add_argument(
        "symbol",
        help="股票代码（6位数字，如 600519 / 000001）",
    )
    parser.add_argument(
        "-n",
        "--periods",
        type=int,
        default=20,
        metavar="N",
        help="展示近N个交易日数据，默认 20",
    )

    args = parser.parse_args()

    try:
        analyze(args.symbol, periods=args.periods)
    except ValueError as e:
        print(f"\n错误: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n已中断。")
        sys.exit(0)
    except Exception as e:
        print(f"\n分析过程中发生错误: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
