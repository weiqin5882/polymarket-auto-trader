# Polymarket Auto Trader

基于 Polymarket CLOB API 的自动化交易系统，支持多策略套利、做市返佣和智能跟单。

## ✨ 核心功能

- 🤖 **多策略并行** - Dutch Book套利、负风险套利、做市返佣、动量交易、智能跟单
- 💰 **动态金额管理** - 根据信号质量自适应调整交易金额
- 🛡️ **严格风控** - 6层风控过滤，自动止损
- 📊 **实时监控** - 订单状态跟踪，风险报告
- 🚀 **自动执行** - 检测信号后自动触发交易

## 🏗️ 架构

```
polymarket-auto-trader/
├── trading/           # 核心交易模块
│   ├── core.py       # 策略基类和数据模型
│   ├── executor.py   # 订单执行引擎
│   ├── amount_calculator.py  # 动态金额计算
│   └── risk_manager.py       # 风控管理
├── strategies/        # 策略实现
│   ├── advanced_arbitrage.py
│   ├── bands_market_maker.py
│   ├── unusual_volume.py
│   └── copy_trading.py
├── api/              # API接口
│   └── config_api.py # 配置管理API
├── config/           # 配置文件
│   ├── system.json
│   └── trading_config.json
└── docs/             # 文档
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API 密钥

```bash
cp config/.env.example config/.env
# 编辑 .env 填入你的 Polymarket API 凭证
```

### 3. 配置交易策略

```bash
# 编辑交易配置
nano config/trading_config.json
```

### 4. 启动系统

```bash
# 模拟模式（测试）
python main.py --dry-run

# 实盘交易
python main.py --live
```

## 📊 策略详情

### Dutch Book 套利
```python
# 条件：同一事件所有Yes价格之和 < 1
# 利润：1 - sum(prices)
# 风险：极低（无风险套利）
```

### 负风险套利
```python
# 机制：1个No token → 转换其他所有Yes
# 套利：No价格 < 其他Yes价格之和
```

### 做市返佣
```python
# Crypto市场：1.56%费率 × 20%返佣
# Sports市场：0.44%费率 × 25%返佣
```

## ⚙️ 配置说明

### 动态金额配置

```json
{
  "auto_trading": {
    "enabled": true,
    "mode": "adaptive",
    "adaptive": {
      "base_amount_usd": 500,
      "max_amount_usd": 2000,
      "min_amount_usd": 100,
      "confidence_multiplier": {
        "low": 0.5,
        "medium": 1.0,
        "high": 1.5,
        "very_high": 2.0
      }
    }
  }
}
```

### 风控配置

```json
{
  "risk": {
    "max_position_usd": 10000,
    "max_daily_loss_usd": 500,
    "max_order_size_usd": 1000,
    "max_slippage_bps": 100
  }
}
```

## 📈 预期收益

| 策略 | 月收益 | 风险 | 资金要求 |
|------|--------|------|----------|
| Dutch Book | 1-3% | ⭐ | $5k+ |
| 负风险套利 | 2-5% | ⭐⭐ | $10k+ |
| 做市返佣 | 3-8% | ⭐⭐ | $20k+ |
| 组合策略 | **5-15%** | ⭐⭐ | $10k+ |

## ⚠️ 风险提示

- 预测市场交易存在风险
- 过往表现不代表未来收益
- 请遵守当地法律法规
- 建议先用小额资金测试

## 📄 许可证

MIT License

## 🙏 致谢

- Polymarket 官方 SDK
- 开源社区的各种策略参考
