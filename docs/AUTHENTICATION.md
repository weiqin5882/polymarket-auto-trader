# Polymarket 身份验证指南

基于官方文档: https://docs.polymarket.com/cn/api-reference/authentication

## 概述

Polymarket CLOB API 使用**两级身份验证**：

```
┌─────────────────────────────────────────────┐
│              两级认证架构                    │
├─────────────────────────────────────────────┤
│                                             │
│  L1: 区块链层 (私钥)      L2: API层        │
│  ├─ POLY_PRIVATE_KEY      ├─ POLY_API_KEY   │
│  │   (钱包私钥)            │   (API标识)    │
│  │                         ├─ POLY_API_SECRET│
│  │                         │   (签名密钥)    │
│  │                         └─ POLY_API_PASSPHRASE
│  │                             (访问密码)    │
│  │                                            │
│  用途：签名交易          用途：API请求认证    │
│  方法：EIP-712          方法：HMAC-SHA256    │
│                                             │
└─────────────────────────────────────────────┘
```

## 认证级别说明

### L1 认证 - 私钥签名

**用途：**
- 创建 API 凭证
- 派生现有 API 凭证
- 本地签署和创建用户订单

**方法：** EIP-712 结构化数据签名

```python
domain = {
    "name": "ClobAuthDomain",
    "version": "1",
    "chainId": 137  # Polygon
}

types = {
    "ClobAuth": [
        {"name": "address", "type": "address"},
        {"name": "timestamp", "type": "string"},
        {"name": "nonce", "type": "uint256"},
        {"name": "message", "type": "string"}
    ]
}

value = {
    "address": "你的地址",
    "timestamp": "1712345678",
    "nonce": 0,
    "message": "This message attests that I control the given wallet"
}
```

### L2 认证 - API 凭证

**用途：**
- 取消或获取用户的活跃订单
- 检查用户的余额和授权
- 提交用户签名的订单

**方法：** HMAC-SHA256 请求签名

**5个必需的 HTTP Header：**

| Header | 说明 |
|--------|------|
| `POLY_ADDRESS` | Polygon 签名者地址 |
| `POLY_SIGNATURE` | 请求的 HMAC 签名 |
| `POLY_TIMESTAMP` | 当前 UNIX 时间戳 |
| `POLY_API_KEY` | 用户的 API `apiKey` |
| `POLY_PASSPHRASE` | 用户的 API `passphrase` |

## 快速开始

### 1. 获取私钥

```
1. 登录 https://polymarket.com
2. Settings → Security & Privacy
3. Export Private Key
4. 保存显示的私钥（只显示一次！）
```

### 2. 生成 API 凭证

```bash
# 方式1：使用脚本（推荐）
python scripts/generate_credentials.py

# 方式2：代码生成
from trading.auth import PolymarketAuth

auth = PolymarketAuth("0x你的私钥")
auth.create_l2_credentials()
```

### 3. 配置环境变量

创建 `config/.env` 文件：

```bash
# L1 认证
POLY_PRIVATE_KEY=0x你的私钥

# L2 认证（运行脚本后生成）
POLY_API_KEY=550e8400-e29b-41d4-a716-446655440000
POLY_API_SECRET=你的Secret
POLY_API_PASSPHRASE=你的Passphrase

# 派生地址
POLY_ADDRESS=0x你的地址

# 交易模式
TRADING_MODE=dry-run
```

### 4. 验证连接

```bash
python scripts/test_connection.py
```

## API 端点分类

### 公开端点（无需认证）

| 端点 | 用途 |
|------|------|
| `GET /markets` | 获取市场列表 |
| `GET /book/{token_id}` | 获取订单簿 |
| `GET /prices-history` | 获取价格历史 |
| `GET /leaderboard` | 获取排行榜 |
| `GET /trades` | 获取公开交易 |

### 需要认证端点

| 端点 | 用途 |
|------|------|
| `POST /order` | 提交订单 |
| `DELETE /order/{id}` | 取消订单 |
| `GET /positions` | 获取持仓 |
| `GET /balance` | 获取余额 |
| `POST /cancel-all` | 取消所有订单 |

## 签名类型

初始化客户端时必须指定：

| 类型 | 值 | 说明 |
|------|-----|------|
| EOA | 0 | 标准 Ethereum 钱包（MetaMask） |
| POLY_PROXY | 1 | Magic Link 代理钱包（默认） |
| GNOSIS_SAFE | 2 | Gnosis Safe 多签钱包 |

## 代码示例

### 初始化客户端

```python
from trading.auth import PolymarketAuth

# 创建认证实例
auth = PolymarketAuth()

# 生成 L2 Headers
headers = auth.generate_l2_headers(
    method="POST",
    path="/order"
)

# 获取 CLOB 客户端
client = auth.get_clob_client(
    signature_type=1,  # POLY_PROXY
    funder="你的代理地址"
)
```

### 发送认证请求

```python
import requests

# 使用生成的 headers
headers = auth.generate_l2_headers("GET", "/positions")

response = requests.get(
    "https://clob.polymarket.com/positions",
    headers=headers
)

positions = response.json()
```

## 安全最佳实践

### ✅ 正确做法

1. **使用环境变量存储密钥**
   ```python
   private_key = os.getenv('POLY_PRIVATE_KEY')
   ```

2. **不要将私钥提交到 Git**
   ```bash
   echo "config/.env" >> .gitignore
   echo "config/.api_credentials.json" >> .gitignore
   ```

3. **设置文件权限**
   ```bash
   chmod 600 config/.env
   chmod 600 config/.api_credentials.json
   ```

4. **定期更换凭证**
   ```bash
   rm config/.api_credentials.json
   python scripts/generate_credentials.py
   ```

### ❌ 错误做法

```python
# 永远不要这样做！
private_key = "0xabc123..."  # 硬编码
api_key = "550e8400..."      # 提交到GitHub
```

## 故障排除

### 错误：INVALID_SIGNATURE

**原因：** 私钥不正确或格式不对

**解决：**
- 验证私钥是有效的十六进制字符串（以 "0x" 开头）
- 确保使用目标地址对应的正确密钥
- 检查密钥是否具有正确的权限

### 错误：NONCE_ALREADY_USED

**原因：** Nonce 已被用于创建 API key

**解决：**
- 使用相同的 nonce 调用 `derive_api_key()` 获取现有凭证
- 或使用不同的 nonce 调用 `create_api_key()`

### 错误：Invalid Funder Address

**原因：** Funder 地址不正确或与钱包不匹配

**解决：**
- 在 [polymarket.com/settings](https://polymarket.com/settings) 查看个人资料地址
- 如果地址不存在，先登录 Polymarket.com 部署代理钱包

### 错误：Rate Limit Exceeded

**原因：** API 调用太频繁

**解决：**
- 降低请求频率
- 实现指数退避重试
- 联系 Polymarket 提高限制

## 参考资源

- [Polymarket 官方文档 - 身份验证](https://docs.polymarket.com/cn/api-reference/authentication)
- [Python SDK](https://github.com/Polymarket/py-clob-client)
- [TypeScript SDK](https://github.com/Polymarket/clob-client)
- [EIP-712 标准](https://eips.ethereum.org/EIPS/eip-712)
