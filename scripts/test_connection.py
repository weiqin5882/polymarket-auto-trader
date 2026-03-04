#!/usr/bin/env python3
"""
Polymarket API 连接测试脚本
验证所有认证配置是否正确
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv


def check_environment():
    """检查环境变量"""
    print("🔍 检查环境变量...")
    print()
    
    required_vars = {
        'POLY_PRIVATE_KEY': 'L1 私钥（必需）',
        'POLY_API_KEY': 'L2 API Key（可选，可自动生成）',
        'POLY_API_SECRET': 'L2 Secret（可选，可自动生成）',
        'POLY_API_PASSPHRASE': 'L2 Passphrase（可选，可自动生成）',
        'TRADING_MODE': '交易模式（默认 dry-run）'
    }
    
    all_present = True
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value and not value.startswith('your_'):
            # 安全显示：只显示前10个字符
            display = value[:10] + '...' if len(value) > 10 else value
            print(f"  ✅ {var}: {display}")
            print(f"     ({description})")
        else:
            if var == 'POLY_PRIVATE_KEY':
                print(f"  ❌ {var}: 未配置")
                print(f"     ({description}) - 必须配置")
                all_present = False
            else:
                print(f"  ⚠️  {var}: 未配置")
                print(f"     ({description}) - 将尝试自动生成")
        print()
    
    return all_present


def test_l1_auth():
    """测试 L1 认证"""
    print("\n🔄 测试 L1 认证...")
    print()
    
    try:
        from eth_account import Account
        
        private_key = os.getenv('POLY_PRIVATE_KEY')
        if not private_key:
            print("  ❌ 未找到 POLY_PRIVATE_KEY")
            return False
        
        # 验证私钥格式
        if not private_key.startswith('0x') or len(private_key) != 66:
            print(f"  ❌ 私钥格式错误")
            print(f"     期望: 0x + 64位十六进制 (共66字符)")
            print(f"     实际: {len(private_key)} 字符")
            return False
        
        # 尝试加载账户
        account = Account.from_key(private_key)
        address = account.address
        
        print(f"  ✅ 私钥格式正确")
        print(f"     地址: {address}")
        
        return address
        
    except ImportError:
        print("  ❌ 未安装 eth-account")
        print("     运行: pip install eth-account")
        return False
    except Exception as e:
        print(f"  ❌ L1 认证失败: {e}")
        return False


def test_l2_auth(address):
    """测试 L2 认证"""
    print("\n🔄 测试 L2 认证...")
    print()
    
    # 检查现有凭证
    creds_file = "config/.api_credentials.json"
    if os.path.exists(creds_file):
        print(f"  ✅ 发现缓存凭证: {creds_file}")
        try:
            import json
            with open(creds_file, 'r') as f:
                cached = json.load(f)
            
            # 验证地址匹配
            if cached.get('address', '').lower() == address.lower():
                print(f"  ✅ 凭证地址匹配")
                print(f"     API Key: {cached['api_key'][:20]}...")
                return True
            else:
                print(f"  ⚠️  凭证地址不匹配，需要重新生成")
                return False
        except Exception as e:
            print(f"  ⚠️  读取缓存失败: {e}")
    
    # 检查环境变量中的凭证
    api_key = os.getenv('POLY_API_KEY')
    api_secret = os.getenv('POLY_API_SECRET')
    api_passphrase = os.getenv('POLY_API_PASSPHRASE')
    
    if all([api_key, api_secret, api_passphrase]):
        if not api_key.startswith('your_'):
            print(f"  ✅ 环境变量中存在 L2 凭证")
            print(f"     API Key: {api_key[:20]}...")
            return True
    
    print("  ⚠️  未找到 L2 凭证，需要生成")
    print("     运行: python scripts/generate_credentials.py")
    return False


def test_api_connection():
    """测试 API 连接"""
    print("\n🔄 测试 API 连接...")
    print()
    
    try:
        from trading.auth import PolymarketAuth
        
        auth = PolymarketAuth()
        
        if not auth.is_authenticated():
            print("  ❌ 未认证")
            return False
        
        print(f"  ✅ 认证成功")
        print(f"     地址: {auth.get_address()}")
        
        # 测试公开 API
        try:
            from py_clob_client.client import ClobClient
            client = ClobClient("https://clob.polymarket.com", 137)
            
            # 获取一个市场
            markets = client.get_markets()[:1]
            print(f"  ✅ 公开 API 连接成功")
            print(f"     可访问市场数: {len(markets)}")
            
        except Exception as e:
            print(f"  ⚠️  公开 API 测试失败: {e}")
        
        # 测试认证 API
        try:
            client = auth.get_clob_client()
            # 尝试获取余额
            balance = client.get_balance()
            print(f"  ✅ 认证 API 连接成功")
            print(f"     账户余额: {balance} USDC")
        except Exception as e:
            print(f"  ⚠️  认证 API 测试失败: {e}")
            print(f"     可能需要 USDC 存款或完成 KYC")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ 缺少依赖: {e}")
        return False
    except Exception as e:
        print(f"  ❌ API 连接失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 70)
    print("   🔐 Polymarket API 连接测试")
    print("=" * 70)
    print()
    
    # 加载环境变量
    load_dotenv('config/.env')
    
    # 检查环境变量
    has_private_key = check_environment()
    
    if not has_private_key:
        print()
        print("❌ 缺少必需的配置")
        print()
        print("请完成以下步骤：")
        print("  1. 从 Polymarket 导出私钥")
        print("  2. 复制 config/.env.example 为 config/.env")
        print("  3. 在 config/.env 中填写 POLY_PRIVATE_KEY")
        print()
        return 1
    
    # 测试 L1 认证
    address = test_l1_auth()
    if not address:
        return 1
    
    # 测试 L2 认证
    has_l2 = test_l2_auth(address)
    if not has_l2:
        print()
        print("💡 建议运行: python scripts/generate_credentials.py")
        print("   自动生成 L2 API 凭证")
    
    # 测试 API 连接
    connected = test_api_connection()
    
    # 总结
    print()
    print("=" * 70)
    if connected:
        print("✅ 所有测试通过！可以开始交易")
        print("=" * 70)
        print()
        print("下一步：")
        mode = os.getenv('TRADING_MODE', 'dry-run')
        if mode == 'live':
            print("  ⚠️  当前是实盘模式，请注意风险")
        else:
            print("  当前是模拟模式（dry-run）")
            print("  测试无误后，修改 TRADING_MODE=live 启用实盘")
        print()
        print("  启动系统: python main.py")
    else:
        print("⚠️  部分测试未通过")
        print("=" * 70)
        print()
        print("请检查：")
        print("  - 私钥是否正确导出")
        print("  - 是否完成 KYC 验证")
        print("  - 账户是否有 USDC 余额")
    
    return 0 if connected else 1


if __name__ == "__main__":
    sys.exit(main())
