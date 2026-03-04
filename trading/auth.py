#!/usr/bin/env python3
"""
Polymarket 认证模块
基于官方文档: https://docs.polymarket.com/cn/api-reference/authentication

支持:
- L1 认证 (私钥签名)
- L2 认证 (API Key + HMAC-SHA256)
- EIP-712 签名
- 自动凭证管理
"""

import os
import json
import time
import hmac
import hashlib
import base64
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# 尝试导入以太坊相关库
try:
    from eth_account import Account
    from eth_account.messages import encode_typed_data
    ETH_AVAILABLE = True
except ImportError:
    ETH_AVAILABLE = False
    print("⚠️  eth-account 未安装，L1 签名功能受限")

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.signing.eip712 import sign_api_key_request
    from py_clob_client.signing.hmac import generate_hmac_signature
    CLOB_AVAILABLE = True
except ImportError:
    CLOB_AVAILABLE = False
    print("⚠️  py-clob-client 未安装")


@dataclass
class L1Credentials:
    """L1 认证凭证"""
    address: str
    private_key: str
    timestamp: int
    nonce: int
    signature: str


@dataclass
class L2Credentials:
    """L2 认证凭证 (API Key)"""
    api_key: str
    secret: str
    passphrase: str
    created_at: int


@dataclass
class AuthHeaders:
    """HTTP 请求头"""
    poly_address: str
    poly_signature: str
    poly_timestamp: str
    poly_api_key: Optional[str] = None
    poly_passphrase: Optional[str] = None


class PolymarketAuth:
    """
    Polymarket 认证管理器
    
    实现官方文档中的两级认证:
    - L1: 私钥签名 (EIP-712)
    - L2: API Key + HMAC-SHA256
    """
    
    # API 端点
    CLOB_HOST = "https://clob.polymarket.com"
    CHAIN_ID = 137  # Polygon Mainnet
    
    def __init__(self, private_key: Optional[str] = None):
        """
        初始化认证管理器
        
        Args:
            private_key: 钱包私钥 (0x 开头)
        """
        self.private_key = private_key or os.getenv('POLY_PRIVATE_KEY')
        self.l1_creds: Optional[L1Credentials] = None
        self.l2_creds: Optional[L2Credentials] = None
        self.cached_creds_file = "config/.api_credentials.json"
        
        if self.private_key:
            self._load_or_create_credentials()
    
    def _load_or_create_credentials(self):
        """加载或创建 API 凭证"""
        # 尝试从缓存加载
        if os.path.exists(self.cached_creds_file):
            try:
                with open(self.cached_creds_file, 'r') as f:
                    cached = json.load(f)
                
                self.l2_creds = L2Credentials(
                    api_key=cached['api_key'],
                    secret=cached['secret'],
                    passphrase=cached['passphrase'],
                    created_at=cached.get('created_at', int(time.time()))
                )
                
                # 加载 L1 信息
                self.l1_creds = L1Credentials(
                    address=cached.get('address', ''),
                    private_key=self.private_key,
                    timestamp=cached.get('timestamp', 0),
                    nonce=cached.get('nonce', 0),
                    signature=''
                )
                
                print("✅ 已从缓存加载 API 凭证")
                return
                
            except Exception as e:
                print(f"⚠️  加载缓存凭证失败: {e}")
        
        # 创建新凭证
        if CLOB_AVAILABLE:
            self.create_l2_credentials()
    
    def create_l1_signature(self, nonce: int = 0) -> L1Credentials:
        """
        创建 L1 EIP-712 签名
        
        用于创建/派生 API Key
        """
        if not self.private_key:
            raise ValueError("未提供私钥")
        
        if not ETH_AVAILABLE:
            raise RuntimeError("需要安装 eth-account: pip install eth-account")
        
        # 获取当前时间戳
        timestamp = str(int(time.time()))
        
        # EIP-712 域
        domain = {
            "name": "ClobAuthDomain",
            "version": "1",
            "chainId": self.CHAIN_ID
        }
        
        # EIP-712 类型
        types = {
            "ClobAuth": [
                {"name": "address", "type": "address"},
                {"name": "timestamp", "type": "string"},
                {"name": "nonce", "type": "uint256"},
                {"name": "message", "type": "string"}
            ]
        }
        
        # 签名数据
        account = Account.from_key(self.private_key)
        address = account.address
        
        value = {
            "address": address,
            "timestamp": timestamp,
            "nonce": nonce,
            "message": "This message attests that I control the given wallet"
        }
        
        # 生成签名
        signable_message = encode_typed_data(domain, types, value)
        signed_message = account.sign_message(signable_message)
        signature = signed_message.signature.hex()
        
        self.l1_creds = L1Credentials(
            address=address,
            private_key=self.private_key,
            timestamp=int(timestamp),
            nonce=nonce,
            signature=signature
        )
        
        return self.l1_creds
    
    def create_l2_credentials(self) -> L2Credentials:
        """
        创建 L2 API 凭证
        
        使用 py-clob-client 自动生成
        """
        if not CLOB_AVAILABLE:
            raise RuntimeError("需要安装 py-clob-client")
        
        if not self.private_key:
            raise ValueError("未提供私钥")
        
        print("🔄 创建 API 凭证...")
        
        client = ClobClient(
            host=self.CLOB_HOST,
            chain_id=self.CHAIN_ID,
            key=self.private_key
        )
        
        # 创建或派生 API Key
        creds = client.create_or_derive_api_creds()
        
        self.l2_creds = L2Credentials(
            api_key=creds['apiKey'],
            secret=creds['secret'],
            passphrase=creds['passphrase'],
            created_at=int(time.time())
        )
        
        # 同时获取 L1 地址
        if not self.l1_creds:
            from eth_account import Account
            account = Account.from_key(self.private_key)
            self.l1_creds = L1Credentials(
                address=account.address,
                private_key=self.private_key,
                timestamp=0,
                nonce=0,
                signature=''
            )
        
        # 缓存凭证
        self._cache_credentials()
        
        print("✅ API 凭证创建成功")
        print(f"   API Key: {self.l2_creds.api_key[:20]}...")
        
        return self.l2_creds
    
    def _cache_credentials(self):
        """缓存凭证到文件"""
        if not self.l2_creds or not self.l1_creds:
            return
        
        cache = {
            'api_key': self.l2_creds.api_key,
            'secret': self.l2_creds.secret,
            'passphrase': self.l2_creds.passphrase,
            'created_at': self.l2_creds.created_at,
            'address': self.l1_creds.address,
            'timestamp': self.l1_creds.timestamp,
            'nonce': self.l1_creds.nonce
        }
        
        # 确保目录存在
        os.makedirs(os.path.dirname(self.cached_creds_file), exist_ok=True)
        
        with open(self.cached_creds_file, 'w') as f:
            json.dump(cache, f, indent=2)
        
        print(f"💾 凭证已缓存到 {self.cached_creds_file}")
    
    def generate_l2_headers(self, method: str = "GET", path: str = "/") -> Dict[str, str]:
        """
        生成 L2 认证 HTTP Headers
        
        Args:
            method: HTTP 方法 (GET, POST, etc.)
            path: API 路径
            
        Returns:
            包含 5 个必要 header 的字典
        """
        if not self.l2_creds or not self.l1_creds:
            raise ValueError("L2 凭证未初始化")
        
        # 获取当前时间戳
        timestamp = str(int(time.time()))
        
        # 生成 HMAC 签名
        message = timestamp + method.upper() + path
        signature = self._generate_hmac_signature(message)
        
        return {
            "POLY_ADDRESS": self.l1_creds.address,
            "POLY_SIGNATURE": signature,
            "POLY_TIMESTAMP": timestamp,
            "POLY_API_KEY": self.l2_creds.api_key,
            "POLY_PASSPHRASE": self.l2_creds.passphrase
        }
    
    def _generate_hmac_signature(self, message: str) -> str:
        """生成 HMAC-SHA256 签名"""
        if not self.l2_creds:
            raise ValueError("L2 凭证未初始化")
        
        secret = self.l2_creds.secret
        
        # Base64 解码 secret
        try:
            secret_bytes = base64.b64decode(secret)
        except:
            secret_bytes = secret.encode()
        
        # HMAC-SHA256
        signature = hmac.new(
            secret_bytes,
            message.encode(),
            hashlib.sha256
        ).digest()
        
        # Base64 编码结果
        return base64.b64encode(signature).decode()
    
    def get_clob_client(self, signature_type: int = 1, funder: Optional[str] = None):
        """
        获取配置好的 CLOB 客户端
        
        Args:
            signature_type: 
                0 = EOA (MetaMask)
                1 = POLY_PROXY (Magic Link) - 默认
                2 = GNOSIS_SAFE (多签)
            funder: 资金地址（代理钱包地址）
        """
        if not CLOB_AVAILABLE:
            raise RuntimeError("需要安装 py-clob-client")
        
        if not self.l2_creds:
            self.create_l2_credentials()
        
        return ClobClient(
            host=self.CLOB_HOST,
            chain_id=self.CHAIN_ID,
            key=self.private_key,
            creds={
                'api_key': self.l2_creds.api_key,
                'api_secret': self.l2_creds.secret,
                'passphrase': self.l2_creds.passphrase
            },
            signature_type=signature_type,
            funder=funder or self.l1_creds.address if self.l1_creds else None
        )
    
    def is_authenticated(self) -> bool:
        """检查是否已完成认证"""
        return self.l2_creds is not None and self.l1_creds is not None
    
    def get_address(self) -> Optional[str]:
        """获取钱包地址"""
        return self.l1_creds.address if self.l1_creds else None
    
    def get_env_config(self) -> str:
        """生成 .env 文件内容"""
        if not self.is_authenticated():
            return "# 请先完成认证"
        
        return f"""# Polymarket API 配置
# 生成时间: {datetime.fromtimestamp(self.l2_creds.created_at)}

# L1: 钱包私钥 (最高敏感)
POLY_PRIVATE_KEY={self.private_key}

# L2: API 凭证
POLY_API_KEY={self.l2_creds.api_key}
POLY_API_SECRET={self.l2_creds.secret}
POLY_API_PASSPHRASE={self.l2_creds.passphrase}

# 钱包地址
POLY_ADDRESS={self.l1_creds.address}
"""


def setup_authentication():
    """
    交互式设置认证
    
    引导用户完成完整的认证流程
    """
    print("=" * 60)
    print("🔐 Polymarket 认证设置")
    print("=" * 60)
    print()
    
    # 检查环境变量
    private_key = os.getenv('POLY_PRIVATE_KEY')
    
    if not private_key:
        print("❌ 未找到 POLY_PRIVATE_KEY 环境变量")
        print()
        print("请从 Polymarket 导出私钥：")
        print("  1. 访问 https://polymarket.com")
        print("  2. Settings → Security → Export Private Key")
        print()
        private_key = input("请输入私钥 (0x...): ").strip()
    else:
        print(f"✅ 从环境变量读取私钥: {private_key[:10]}...")
    
    if not private_key.startswith('0x'):
        print("❌ 私钥格式错误，应以 0x 开头")
        return False
    
    # 创建认证管理器
    auth = PolymarketAuth(private_key)
    
    if auth.is_authenticated():
        print()
        print("✅ 认证完成！")
        print(f"   地址: {auth.get_address()}")
        print()
        print("环境变量配置：")
        print(auth.get_env_config())
        return True
    else:
        print("❌ 认证失败")
        return False


if __name__ == "__main__":
    setup_authentication()
