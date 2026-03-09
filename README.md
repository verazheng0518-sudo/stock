# stock

A股股票综合分析工具：查询股票当前价格和近20个交易日的趋势波动，对技术性指标进行分析，查询今日的重大政治性事件和国家政策，并结合消息面给出操作建议。

## 功能

- **实时行情**：查询股票当前价格、涨跌幅、成交量、市值等关键指标
- **趋势分析**：展示近20个交易日（可配置）的K线数据及波动情况
- **技术指标**：
  - 移动平均线（MA5 / MA10 / MA20）
  - MACD（12-26-9）金叉/死叉/红绿柱
  - RSI（14日）超买/超卖判断
  - 布林带（20日，2σ）支撑/压力位
  - KDJ（9日）K/D/J 金叉死叉
  - 成交量趋势（量比分析）
- **政策资讯**：
  - 新闻联播文字稿（重大政治事件/政策）
  - 财新网最新报道
  - 个股相关新闻（东方财富）
- **操作建议**：综合技术面（60%权重）和消息面（40%权重），给出买入/加仓/持有/减仓/卖出/观望建议，并提供止损和目标价参考

## 安装

```bash
pip install -r requirements.txt
```

## 使用

```bash
# 分析贵州茅台
python main.py 600519

# 分析平安银行
python main.py 000001

# 分析宁德时代，查看近30个交易日
python main.py 300750 -n 30

# 查看帮助
python main.py --help
```

## 项目结构

```
stock/
├── main.py                          # 主入口（CLI）
├── requirements.txt                 # 依赖包
├── stock_analyzer/
│   ├── __init__.py
│   ├── data_fetcher.py              # A股数据获取（akshare）
│   ├── technical_analyzer.py        # 技术指标计算与分析
│   ├── news_fetcher.py              # 政策/政治新闻抓取
│   └── recommendation_engine.py     # 综合操作建议生成
└── tests/
    └── test_stock_analyzer.py       # 单元测试
```

## 运行测试

```bash
python -m pytest tests/ -v
```

## 免责声明

本工具仅供学习和参考，不构成投资建议。股市有风险，投资需谨慎。
