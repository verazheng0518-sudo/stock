# stock

一个用于快速分析股票行情与消息面的命令行工具：

- 查询股票当前价格
- 分析近 20 个交易日趋势和波动率
- 计算常见技术指标（SMA、RSI、MACD）
- 汇总今日重大政治事件与国家政策相关新闻（基于公开 RSS）
- 结合技术面与消息面给出操作建议

## 使用方式

```bash
python stock_analyzer.py AAPL
```

> 支持通过 `STOCK_NEWS_MAX_ITEMS` 环境变量控制新闻条数（默认每类 5 条）。
