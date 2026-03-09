"""
重大政治事件和国家政策资讯获取模块

数据来源:
1. 新闻联播文字稿 (akshare: news_cctv) — 最权威的政治/政策资讯
2. 东方财富个股新闻 (akshare: stock_news_em)
3. 财新网最新报道 (akshare: stock_news_main_cx)

通过关键词过滤出与政策/政治相关的新闻。
"""

import datetime
from dataclasses import dataclass, field
from typing import Optional

import akshare as ak
import pandas as pd


@dataclass
class NewsItem:
    """单条新闻/资讯条目。"""

    title: str
    content: str
    source: str
    time: str
    category: str = "财经"       # 财经 / 政策 / 政治 / 重大事件


_LIMIT_PER_SOURCE = 10   # 每个数据源最多保留条数


class NewsFetcher:
    """从多个数据源抓取当日重大政治/政策新闻。"""

    def __init__(self, symbol: Optional[str] = None) -> None:
        """
        Parameters
        ----------
        symbol : str, optional
            股票代码（6位数字）。若提供，则额外抓取该股票相关的个股新闻。
        """
        self.symbol = symbol
        self._today = datetime.date.today().strftime("%Y%m%d")

    def fetch(self) -> list[NewsItem]:
        """
        抓取今日重大政策/政治事件新闻。

        Returns
        -------
        list[NewsItem]
            按相关性排序的新闻列表。
        """
        items: list[NewsItem] = []

        items += self._fetch_cctv_news()
        items += self._fetch_caixin_news()
        if self.symbol:
            items += self._fetch_individual_stock_news()

        # 去重（按标题前30字符）
        seen: set[str] = set()
        unique: list[NewsItem] = []
        for item in items:
            key = item.title[:30]
            if key not in seen:
                seen.add(key)
                unique.append(item)

        # 优先展示政策/政治类
        policy = [i for i in unique if i.category in ("政策", "政治", "重大事件")]
        others = [i for i in unique if i.category not in ("政策", "政治", "重大事件")]

        return policy + others

    # ------------------------------------------------------------------
    # 各数据源抓取方法
    # ------------------------------------------------------------------

    def _fetch_cctv_news(self) -> list[NewsItem]:
        """新闻联播文字稿（最权威的政策/政治资讯）。"""
        try:
            df = ak.news_cctv(date=self._today)
            items = []
            for _, row in df.iterrows():
                title = str(row.get("题目", "") or row.get("title", ""))
                content = str(row.get("内容", "") or row.get("content", ""))
                time_str = self._today
                if not title:
                    continue
                category = self._categorize(title + content)
                items.append(
                    NewsItem(
                        title=title,
                        content=content[:200],
                        source="新闻联播",
                        time=time_str,
                        category=category,
                    )
                )
            return items[:_LIMIT_PER_SOURCE]
        except Exception:
            return []

    def _fetch_caixin_news(self) -> list[NewsItem]:
        """财新网最新报道。"""
        try:
            df = ak.stock_news_main_cx()
            items = []
            for _, row in df.head(30).iterrows():
                title = str(row.get("标题", "") or row.get("title", ""))
                content = str(row.get("摘要", "") or row.get("summary", "") or row.get("content", ""))
                time_str = str(row.get("时间", "") or row.get("time", ""))
                if not title:
                    continue
                category = self._categorize(title + content)
                items.append(
                    NewsItem(
                        title=title,
                        content=content[:200],
                        source="财新网",
                        time=time_str,
                        category=category,
                    )
                )
            return items[:_LIMIT_PER_SOURCE]
        except Exception:
            return []

    def _fetch_individual_stock_news(self) -> list[NewsItem]:
        """个股相关新闻（东方财富）。"""
        if not self.symbol:
            return []
        try:
            df = ak.stock_news_em(symbol=self.symbol)
            items = []
            for _, row in df.head(_LIMIT_PER_SOURCE).iterrows():
                title = str(row.get("新闻标题", "") or row.get("title", ""))
                content = str(row.get("新闻内容", "") or row.get("content", ""))
                time_str = str(row.get("发布时间", "") or row.get("time", ""))
                if not title:
                    continue
                category = self._categorize(title + content)
                items.append(
                    NewsItem(
                        title=title,
                        content=content[:200],
                        source="东方财富个股",
                        time=time_str,
                        category=category,
                    )
                )
            return items
        except Exception:
            return []

    # ------------------------------------------------------------------
    # 分类
    # ------------------------------------------------------------------

    @staticmethod
    def _categorize(text: str) -> str:
        """根据关键词对文本分类。"""
        political_keywords = [
            "政治局", "习近平", "李强", "国家主席", "全国人大", "政协",
            "中央", "国务院", "国防", "军事", "战争", "冲突", "制裁",
        ]
        policy_keywords = [
            "政策", "央行", "降准", "降息", "加息", "MLF", "LPR", "利率",
            "证监会", "财政部", "发改委", "监管", "会议", "规划", "战略",
        ]
        major_keywords = ["重大", "突发", "紧急", "重要", "关税", "贸易战"]

        for kw in political_keywords:
            if kw in text:
                return "政治"
        for kw in major_keywords:
            if kw in text:
                return "重大事件"
        for kw in policy_keywords:
            if kw in text:
                return "政策"
        return "财经"
