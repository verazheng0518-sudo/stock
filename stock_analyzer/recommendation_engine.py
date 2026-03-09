"""
操作建议生成模块

综合技术面分析结果和消息面（新闻/政策），给出操作建议。
"""

from dataclasses import dataclass, field
from typing import Optional

from .technical_analyzer import TechnicalAnalysisResult
from .news_fetcher import NewsItem


# 操作建议枚举
ADVICE_BUY = "买入"
ADVICE_ADD = "加仓"
ADVICE_HOLD = "持有"
ADVICE_REDUCE = "减仓"
ADVICE_SELL = "卖出"
ADVICE_WAIT = "观望"

# 消息面评分时最多参考的新闻条数
_NEWS_SCORE_LIMIT = 20


@dataclass
class OperationAdvice:
    """操作建议结果。"""

    action: str              # 主要建议: 买入/加仓/持有/减仓/卖出/观望
    confidence: str          # 信心程度: 强/中/弱
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    stop_loss: Optional[float] = None    # 止损参考价
    target_price: Optional[float] = None  # 目标价参考
    summary: str = ""


class RecommendationEngine:
    """
    综合技术面指标和消息面信息，生成操作建议。
    """

    def __init__(
        self,
        tech_result: TechnicalAnalysisResult,
        news_items: list[NewsItem],
        current_price: float,
        symbol: str = "",
        stock_name: str = "",
    ) -> None:
        self.tech_result = tech_result
        self.news_items = news_items
        self.current_price = current_price
        self.symbol = symbol
        self.stock_name = stock_name

    def generate(self) -> OperationAdvice:
        """执行分析并返回操作建议。"""
        tech_score = self._score_technical()
        news_score = self._score_news()
        total_score = tech_score * 0.6 + news_score * 0.4

        action, confidence = self._score_to_action(total_score)
        reasons = self._build_reasons(tech_score, news_score)
        risks = self._build_risks()
        stop_loss, target_price = self._calc_price_levels()

        summary = self._build_summary(action, confidence, tech_score, news_score, reasons, risks, stop_loss, target_price)

        return OperationAdvice(
            action=action,
            confidence=confidence,
            reasons=reasons,
            risks=risks,
            stop_loss=stop_loss,
            target_price=target_price,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # 评分方法
    # ------------------------------------------------------------------

    def _score_technical(self) -> float:
        """
        对技术面信号打分，返回 -1.0 ~ +1.0 的分数。
        正数偏多，负数偏空。
        """
        signals = self.tech_result.signals
        if not signals:
            return 0.0

        score = 0.0
        weights = {
            "均线系统": 0.25,
            "MACD": 0.20,
            "RSI": 0.15,
            "布林带": 0.15,
            "KDJ": 0.15,
            "成交量": 0.10,
        }

        for sig in signals:
            w = weights.get(sig.name, 0.1)
            if sig.signal == "看多":
                score += w
            elif sig.signal == "看空":
                score -= w

        # 趋势强度加成
        if self.tech_result.trend == "上升趋势":
            bonus = 0.1 if self.tech_result.trend_strength == "强" else 0.05
            score += bonus
        elif self.tech_result.trend == "下降趋势":
            bonus = 0.1 if self.tech_result.trend_strength == "强" else 0.05
            score -= bonus

        return max(-1.0, min(1.0, score))

    def _score_news(self) -> float:
        """
        对消息面打分，返回 -1.0 ~ +1.0 的分数。
        """
        if not self.news_items:
            return 0.0

        positive_keywords = [
            "利好", "提振", "刺激", "扩张", "增长", "好于预期", "超预期",
            "降准", "降息", "宽松", "支持", "补贴", "减税", "降费",
            "涨", "上涨", "上升", "新高", "突破", "改善",
            "批准", "通过", "落地", "实施",
        ]
        negative_keywords = [
            "利空", "打压", "收紧", "减少", "下降", "不及预期", "低于预期",
            "加息", "加征", "关税", "制裁", "风险", "违约", "债务",
            "跌", "下跌", "下降", "新低", "破位",
            "调查", "处罚", "整顿", "暂停", "禁止",
            "战争", "冲突", "紧张",
        ]

        pos_count = 0
        neg_count = 0
        checked = 0

        for item in self.news_items[:_NEWS_SCORE_LIMIT]:
            text = item.title + item.content
            for kw in positive_keywords:
                if kw in text:
                    pos_count += 1
                    break
            for kw in negative_keywords:
                if kw in text:
                    neg_count += 1
                    break
            checked += 1

        if checked == 0:
            return 0.0

        net = (pos_count - neg_count) / checked
        return max(-1.0, min(1.0, net * 2))  # 放大后截断

    def _score_to_action(self, score: float) -> tuple[str, str]:
        """将综合分数转换为操作建议和置信度。"""
        if score >= 0.5:
            action = ADVICE_BUY
            confidence = "强" if score >= 0.7 else "中"
        elif score >= 0.2:
            action = ADVICE_ADD
            confidence = "中"
        elif score >= -0.1:
            action = ADVICE_HOLD
            confidence = "中" if abs(score) < 0.05 else "弱"
        elif score >= -0.3:
            action = ADVICE_REDUCE
            confidence = "中"
        elif score >= -0.5:
            action = ADVICE_SELL
            confidence = "中"
        else:
            action = ADVICE_SELL
            confidence = "强" if score <= -0.7 else "中"

        return action, confidence

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _build_reasons(self, tech_score: float, news_score: float) -> list[str]:
        """整理主要推荐依据。"""
        reasons: list[str] = []

        # 技术面依据
        bullish_signals = [s for s in self.tech_result.signals if s.signal == "看多"]
        bearish_signals = [s for s in self.tech_result.signals if s.signal == "看空"]
        if tech_score > 0 and bullish_signals:
            reasons.append(f"技术面：{self.tech_result.trend}（{self.tech_result.trend_strength}），" +
                           "、".join(s.name for s in bullish_signals) + "等指标偏多")
        elif tech_score < 0 and bearish_signals:
            reasons.append(f"技术面：{self.tech_result.trend}（{self.tech_result.trend_strength}），" +
                           "、".join(s.name for s in bearish_signals) + "等指标偏空")
        else:
            reasons.append(f"技术面：{self.tech_result.trend}（{self.tech_result.trend_strength}），多空信号均衡")

        # 消息面依据
        policy_news = [n for n in self.news_items if n.category in ("政策", "政治", "重大事件")]
        if policy_news:
            titles = [n.title[:30] for n in policy_news[:3]]
            reasons.append(f"消息面：今日重要资讯包括：{'；'.join(titles)}")
        else:
            reasons.append("消息面：暂无重大政策性事件")

        return reasons

    def _build_risks(self) -> list[str]:
        """识别主要风险点。"""
        risks: list[str] = []

        # 技术面风险
        rsi_signal = next((s for s in self.tech_result.signals if s.name == "RSI"), None)
        if rsi_signal:
            if "超买" in rsi_signal.description:
                risks.append("RSI超买，短期存在回调风险")
            elif "超卖" in rsi_signal.description:
                risks.append("RSI超卖，空头力量较强，建议谨慎抄底")

        if self.tech_result.trend == "下降趋势" and self.tech_result.trend_strength == "强":
            risks.append("处于强下降趋势，逆势操作风险较高")

        # 消息面风险
        risk_keywords = ["制裁", "关税", "战争", "违约", "危机", "监管", "整顿", "处罚"]
        for item in self.news_items[:15]:
            for kw in risk_keywords:
                if kw in item.title:
                    risks.append(f"关注消息面风险：{item.title[:40]}")
                    break

        if not risks:
            risks.append("市场波动风险，注意仓位管理")

        return risks[:5]  # 最多5条风险提示

    def _calc_price_levels(self) -> tuple[Optional[float], Optional[float]]:
        """计算止损和目标价参考位。"""
        price = self.current_price
        support = self.tech_result.support
        resistance = self.tech_result.resistance

        if support is None or resistance is None:
            return None, None

        # 止损参考：支撑位下方2%
        stop_loss = round(support * 0.98, 2)
        # 目标价参考：阻力位
        target_price = resistance

        return stop_loss, target_price

    def _build_summary(
        self,
        action: str,
        confidence: str,
        tech_score: float,
        news_score: float,
        reasons: list[str],
        risks: list[str],
        stop_loss: Optional[float],
        target_price: Optional[float],
    ) -> str:
        """生成完整操作建议摘要文字。"""
        lines = [
            f"【操作建议】 {action}（置信度：{confidence}）",
            "",
            f"当前价格: {self.current_price:.2f}",
        ]

        if stop_loss:
            lines.append(f"止损参考: {stop_loss:.2f}")
        if target_price:
            lines.append(f"目标价参考: {target_price:.2f}")

        lines += ["", "主要依据:"]
        for r in reasons:
            lines.append(f"  • {r}")

        lines += ["", "风险提示:"]
        for r in risks:
            lines.append(f"  ⚠ {r}")

        return "\n".join(lines)
