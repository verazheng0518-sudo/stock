"""
技术指标分析模块

根据日K线数据计算常用技术指标并给出分析摘要：
- 移动平均线 (MA5 / MA10 / MA20)
- MACD (12-26-9)
- RSI (14日)
- 布林带 (20日, 2σ)
- 成交量趋势
- KDJ (9日)
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class TechnicalSignal:
    """单个技术指标的信号。"""

    name: str
    value: str
    signal: str          # "看多" / "看空" / "中性"
    description: str


@dataclass
class TechnicalAnalysisResult:
    """技术指标综合分析结果。"""

    signals: list[TechnicalSignal] = field(default_factory=list)
    trend: str = "中性"          # "上升趋势" / "下降趋势" / "震荡"
    trend_strength: str = "弱"   # "强" / "中" / "弱"
    support: Optional[float] = None
    resistance: Optional[float] = None
    summary: str = ""


class TechnicalAnalyzer:
    """对历史K线数据进行技术指标分析。"""

    def __init__(self, df: pd.DataFrame, recent_periods: int = 20) -> None:
        """
        Parameters
        ----------
        df : pd.DataFrame
            完整历史数据（含足够多行用于指标计算）。
            必须包含列: date, open, high, low, close, volume
        recent_periods : int
            展示的近期交易日数量，默认 20。
        """
        self._df = df.copy()
        self.recent_periods = recent_periods
        self._compute_indicators()

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def analyze(self) -> TechnicalAnalysisResult:
        """
        执行综合技术分析并返回结果对象。
        """
        result = TechnicalAnalysisResult()
        result.signals = self._build_signals()
        result.trend, result.trend_strength = self._determine_trend()
        result.support, result.resistance = self._support_resistance()
        result.summary = self._build_summary(result)
        return result

    def get_recent_ohlcv(self) -> pd.DataFrame:
        """返回近 recent_periods 个交易日的 OHLCV + 指标数据。"""
        return self._df.tail(self.recent_periods).reset_index(drop=True)

    # ------------------------------------------------------------------
    # 指标计算
    # ------------------------------------------------------------------

    def _compute_indicators(self) -> None:
        df = self._df
        close = df["close"]
        volume = df["volume"]

        # 移动平均线
        df["ma5"] = close.rolling(5).mean()
        df["ma10"] = close.rolling(10).mean()
        df["ma20"] = close.rolling(20).mean()

        # MACD (EMA12 - EMA26, signal=EMA9)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df["macd_dif"] = ema12 - ema26
        df["macd_dea"] = df["macd_dif"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = (df["macd_dif"] - df["macd_dea"]) * 2

        # RSI (14日)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["rsi14"] = 100 - (100 / (1 + rs))

        # 布林带 (20日, 2σ)
        df["bb_mid"] = close.rolling(20).mean()
        rolling_std = close.rolling(20).std(ddof=0)
        df["bb_upper"] = df["bb_mid"] + 2 * rolling_std
        df["bb_lower"] = df["bb_mid"] - 2 * rolling_std
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]

        # KDJ (9日)
        low_min = df["low"].rolling(9).min()
        high_max = df["high"].rolling(9).max()
        rsv = ((close - low_min) / (high_max - low_min).replace(0, np.nan)) * 100
        df["kdj_k"] = rsv.ewm(com=2, adjust=False).mean()
        df["kdj_d"] = df["kdj_k"].ewm(com=2, adjust=False).mean()
        df["kdj_j"] = 3 * df["kdj_k"] - 2 * df["kdj_d"]

        # 成交量移动均线
        df["vol_ma5"] = volume.rolling(5).mean()
        df["vol_ma20"] = volume.rolling(20).mean()

        self._df = df

    # ------------------------------------------------------------------
    # 信号生成
    # ------------------------------------------------------------------

    def _build_signals(self) -> list[TechnicalSignal]:
        df = self._df
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        signals: list[TechnicalSignal] = []

        # ---------- 均线系统 ----------
        ma5 = latest["ma5"]
        ma10 = latest["ma10"]
        ma20 = latest["ma20"]
        close = latest["close"]

        if pd.notna(ma5) and pd.notna(ma10) and pd.notna(ma20):
            if close > ma5 > ma10 > ma20:
                ma_signal = "看多"
                ma_desc = f"价格({close:.2f})站上均线多头排列(MA5={ma5:.2f}>MA10={ma10:.2f}>MA20={ma20:.2f})，趋势强劲"
            elif close < ma5 < ma10 < ma20:
                ma_signal = "看空"
                ma_desc = f"价格({close:.2f})跌破均线空头排列(MA5={ma5:.2f}<MA10={ma10:.2f}<MA20={ma20:.2f})，下行压力大"
            elif close > ma20:
                ma_signal = "看多"
                ma_desc = f"价格({close:.2f})站上MA20({ma20:.2f})，中期趋势偏多"
            else:
                ma_signal = "看空"
                ma_desc = f"价格({close:.2f})低于MA20({ma20:.2f})，中期趋势偏空"
            signals.append(
                TechnicalSignal("均线系统", f"MA5={ma5:.2f} MA10={ma10:.2f} MA20={ma20:.2f}", ma_signal, ma_desc)
            )

        # ---------- MACD ----------
        dif = latest["macd_dif"]
        dea = latest["macd_dea"]
        hist = latest["macd_hist"]
        prev_hist = prev["macd_hist"]
        if pd.notna(dif) and pd.notna(dea):
            if dif > dea and hist > 0:
                macd_signal = "看多"
            elif dif < dea and hist < 0:
                macd_signal = "看空"
            else:
                macd_signal = "中性"

            # 金叉/死叉判断
            if prev["macd_dif"] <= prev["macd_dea"] and dif > dea:
                cross = "出现金叉，"
            elif prev["macd_dif"] >= prev["macd_dea"] and dif < dea:
                cross = "出现死叉，"
            else:
                cross = ""

            # 红绿柱判断
            if pd.notna(prev_hist):
                bar_trend = "红柱放大" if hist > 0 and hist > prev_hist else (
                    "红柱缩小" if hist > 0 else (
                        "绿柱放大" if hist < 0 and hist < prev_hist else "绿柱缩小"
                    )
                )
            else:
                bar_trend = ""

            macd_desc = f"DIF={dif:.4f} DEA={dea:.4f} MACD柱={hist:.4f}，{cross}{bar_trend}"
            signals.append(TechnicalSignal("MACD", f"DIF={dif:.3f} DEA={dea:.3f}", macd_signal, macd_desc))

        # ---------- RSI ----------
        rsi = latest["rsi14"]
        if pd.notna(rsi):
            if rsi >= 70:
                rsi_signal = "看空"
                rsi_desc = f"RSI14={rsi:.1f}，处于超买区间(≥70)，有回调风险"
            elif rsi <= 30:
                rsi_signal = "看多"
                rsi_desc = f"RSI14={rsi:.1f}，处于超卖区间(≤30)，存在反弹机会"
            elif rsi > 50:
                rsi_signal = "看多"
                rsi_desc = f"RSI14={rsi:.1f}，位于强势区间(50-70)"
            else:
                rsi_signal = "看空"
                rsi_desc = f"RSI14={rsi:.1f}，位于弱势区间(30-50)"
            signals.append(TechnicalSignal("RSI", f"{rsi:.1f}", rsi_signal, rsi_desc))

        # ---------- 布林带 ----------
        bb_upper = latest["bb_upper"]
        bb_mid = latest["bb_mid"]
        bb_lower = latest["bb_lower"]
        bb_width = latest["bb_width"]
        if pd.notna(bb_upper):
            bb_pos = (close - bb_lower) / (bb_upper - bb_lower) * 100 if bb_upper != bb_lower else 50
            if close >= bb_upper:
                bb_signal = "看空"
                bb_desc = f"价格({close:.2f})触及布林上轨({bb_upper:.2f})，有回调压力"
            elif close <= bb_lower:
                bb_signal = "看多"
                bb_desc = f"价格({close:.2f})触及布林下轨({bb_lower:.2f})，有支撑反弹可能"
            elif bb_pos > 50:
                bb_signal = "看多"
                bb_desc = f"价格处于布林带上半区({bb_pos:.0f}%)，中轨={bb_mid:.2f}"
            else:
                bb_signal = "看空"
                bb_desc = f"价格处于布林带下半区({bb_pos:.0f}%)，中轨={bb_mid:.2f}"

            if bb_width < 0.05:
                bb_desc += "；布林带收窄，或将迎来方向性突破"
            signals.append(TechnicalSignal("布林带", f"上轨={bb_upper:.2f} 中轨={bb_mid:.2f} 下轨={bb_lower:.2f}", bb_signal, bb_desc))

        # ---------- KDJ ----------
        k = latest["kdj_k"]
        d = latest["kdj_d"]
        j = latest["kdj_j"]
        prev_k = prev["kdj_k"]
        prev_d = prev["kdj_d"]
        if pd.notna(k) and pd.notna(d):
            if k > d and prev_k <= prev_d:
                kdj_cross = "KDJ金叉，"
            elif k < d and prev_k >= prev_d:
                kdj_cross = "KDJ死叉，"
            else:
                kdj_cross = ""

            if j > 80:
                kdj_signal = "看空"
                kdj_desc = f"{kdj_cross}J值={j:.1f}超买(>80)，注意风险"
            elif j < 20:
                kdj_signal = "看多"
                kdj_desc = f"{kdj_cross}J值={j:.1f}超卖(<20)，关注反弹"
            elif k > d:
                kdj_signal = "看多"
                kdj_desc = f"{kdj_cross}K({k:.1f})>D({d:.1f})，短期偏多"
            else:
                kdj_signal = "看空"
                kdj_desc = f"{kdj_cross}K({k:.1f})<D({d:.1f})，短期偏空"
            signals.append(TechnicalSignal("KDJ", f"K={k:.1f} D={d:.1f} J={j:.1f}", kdj_signal, kdj_desc))

        # ---------- 成交量 ----------
        vol = latest["volume"]
        vol_ma5 = latest["vol_ma5"]
        vol_ma20 = latest["vol_ma20"]
        if pd.notna(vol_ma5) and pd.notna(vol_ma20):
            ratio5 = vol / vol_ma5 if vol_ma5 > 0 else 1
            if ratio5 >= 1.5:
                vol_signal = "看多" if close > prev["close"] else "看空"
                vol_desc = f"成交量放大({ratio5:.1f}倍5日均量)，{'价涨量增，趋势确认' if close > prev['close'] else '价跌量增，下行加速'}"
            elif ratio5 <= 0.5:
                vol_signal = "中性"
                vol_desc = f"成交量萎缩({ratio5:.1f}倍5日均量)，市场观望情绪浓厚"
            else:
                vol_signal = "中性"
                vol_desc = f"成交量正常({ratio5:.1f}倍5日均量)"
            signals.append(TechnicalSignal("成交量", f"量比={ratio5:.1f}", vol_signal, vol_desc))

        return signals

    def _determine_trend(self) -> tuple[str, str]:
        """根据均线和价格位置判断趋势方向和强弱。"""
        df = self._df
        recent = df.tail(self.recent_periods)
        latest = df.iloc[-1]

        close = recent["close"]
        ma20 = latest["ma20"]
        ma5 = latest["ma5"]

        if pd.isna(ma20) or pd.isna(ma5):
            return "震荡", "弱"

        # 判断趋势
        closes = close.values
        x = np.arange(len(closes))
        if len(closes) >= 2:
            slope = np.polyfit(x, closes, 1)[0]
            norm_slope = slope / closes.mean() * 100  # 标准化斜率(%)
        else:
            norm_slope = 0

        if norm_slope > 0.3:
            trend = "上升趋势"
        elif norm_slope < -0.3:
            trend = "下降趋势"
        else:
            trend = "震荡"

        # 判断强度
        rsi = latest["rsi14"]
        macd_hist = latest["macd_hist"]
        strength_score = 0
        if trend == "上升趋势":
            if pd.notna(rsi) and rsi > 60:
                strength_score += 1
            if pd.notna(macd_hist) and macd_hist > 0:
                strength_score += 1
            if latest["close"] > latest["ma5"] > latest["ma20"]:
                strength_score += 1
        elif trend == "下降趋势":
            if pd.notna(rsi) and rsi < 40:
                strength_score += 1
            if pd.notna(macd_hist) and macd_hist < 0:
                strength_score += 1
            if latest["close"] < latest["ma5"] < latest["ma20"]:
                strength_score += 1

        strength = "强" if strength_score >= 2 else ("中" if strength_score == 1 else "弱")
        return trend, strength

    def _support_resistance(self) -> tuple[Optional[float], Optional[float]]:
        """用近期最低价/最高价估算支撑和压力位。"""
        recent = self._df.tail(self.recent_periods)
        if recent.empty:
            return None, None
        support = float(recent["low"].min())
        resistance = float(recent["high"].max())
        return round(support, 2), round(resistance, 2)

    def _build_summary(self, result: TechnicalAnalysisResult) -> str:
        """生成技术面综合摘要文字。"""
        bullish = sum(1 for s in result.signals if s.signal == "看多")
        bearish = sum(1 for s in result.signals if s.signal == "看空")
        total = len(result.signals)

        if total == 0:
            return "数据不足，无法给出技术面判断。"

        latest = self._df.iloc[-1]
        close = latest["close"]

        if bullish > bearish:
            tech_view = f"技术面整体偏多（{bullish}多/{bearish}空/{total - bullish - bearish}中性）"
        elif bearish > bullish:
            tech_view = f"技术面整体偏空（{bullish}多/{bearish}空/{total - bullish - bearish}中性）"
        else:
            tech_view = f"技术面多空均衡（{bullish}多/{bearish}空/{total - bullish - bearish}中性）"

        summary = (
            f"{tech_view}。{result.trend}（{result.trend_strength}）。"
            f"近期支撑参考 {result.support}，压力参考 {result.resistance}。"
        )
        return summary
