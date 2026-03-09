"""
股票数据获取模块

使用 akshare 获取 A 股实时行情及历史行情数据。
"""

import datetime
from typing import Optional

import akshare as ak
import pandas as pd


class StockDataFetcher:
    """获取 A 股股票数据（实时行情 + 历史K线）。"""

    # 东方财富行情代码前缀映射（用于实时快照查询）
    _MARKET_PREFIX = {
        "sh": "1.",
        "sz": "0.",
        "bj": "0.",
    }

    def __init__(self, symbol: str) -> None:
        """
        初始化。

        Parameters
        ----------
        symbol : str
            股票代码，支持格式：
            - 纯数字，如 ``"600519"``、``"000001"``
            - 带市场前缀，如 ``"sh600519"``、``"sz000001"``
        """
        self.symbol = self._normalize_symbol(symbol)
        self._spot_cache: Optional[dict] = None

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def get_current_price(self) -> dict:
        """
        获取股票实时行情快照。

        Returns
        -------
        dict
            包含以下字段：
            symbol, name, current_price, change, change_pct,
            open, high, low, pre_close, volume, amount, turnover_rate,
            pe_ratio, market_cap, timestamp
        """
        spot = self._fetch_spot()
        return spot

    def get_historical_data(self, periods: int = 20) -> pd.DataFrame:
        """
        获取近 ``periods`` 个交易日的日K线数据。

        Parameters
        ----------
        periods : int
            返回交易日数量，默认 20。

        Returns
        -------
        pd.DataFrame
            列：date, open, high, low, close, volume, amount,
                 amplitude, change_pct, change, turnover_rate
        """
        # 取稍多一些数据以保证在剔除非交易日后仍有足够行数（用于指标计算）
        fetch_periods = max(periods + 60, 80)
        end_date = datetime.date.today().strftime("%Y%m%d")
        start_date = (
            datetime.date.today() - datetime.timedelta(days=fetch_periods * 2)
        ).strftime("%Y%m%d")

        df = ak.stock_zh_a_hist(
            symbol=self.symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",  # 前复权
        )

        df = df.rename(
            columns={
                "日期": "date",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
                "成交额": "amount",
                "振幅": "amplitude",
                "涨跌幅": "change_pct",
                "涨跌额": "change",
                "换手率": "turnover_rate",
            }
        )
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        # 只保留最近 periods + 60 行（多余数据用于指标计算，最后 slice 出 periods 行）
        return df

    def get_stock_name(self) -> str:
        """返回股票名称（中文）。"""
        spot = self._fetch_spot()
        return spot.get("name", self.symbol)

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    def _normalize_symbol(self, symbol: str) -> str:
        """去掉市场前缀，只保留6位数字代码。"""
        symbol = symbol.strip()
        if symbol.lower().startswith(("sh", "sz", "bj")):
            return symbol[2:]
        return symbol

    def _fetch_spot(self) -> dict:
        """获取并缓存实时行情快照。"""
        if self._spot_cache is not None:
            return self._spot_cache

        df = ak.stock_zh_a_spot_em()
        df.columns = df.columns.str.strip()

        row = df[df["代码"] == self.symbol]
        if row.empty:
            raise ValueError(
                f"未找到股票代码 '{self.symbol}'，请检查代码是否正确。"
            )

        r = row.iloc[0]
        self._spot_cache = {
            "symbol": self.symbol,
            "name": str(r.get("名称", "")),
            "current_price": float(r.get("最新价", 0)),
            "change": float(r.get("涨跌额", 0)),
            "change_pct": float(r.get("涨跌幅", 0)),
            "open": float(r.get("今开", 0)),
            "high": float(r.get("最高", 0)),
            "low": float(r.get("最低", 0)),
            "pre_close": float(r.get("昨收", 0)),
            "volume": float(r.get("成交量", 0)),
            "amount": float(r.get("成交额", 0)),
            "turnover_rate": float(r.get("换手率", 0)),
            "pe_ratio": float(r.get("市盈率-动态", 0) or 0),
            "market_cap": float(r.get("总市值", 0)),
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return self._spot_cache
