#!/usr/bin/env python3
"""
Polymarket API 凭证生成脚本
基于官方文档规范

使用方法:
    python scripts/generate_credentials.py

输出:
    - 生成 L1/L2 认证凭证
    - 保存到 config/.api_credentials.json
    - 显示 .env 配置内容
"""

import os
import sys
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from trading.auth import PolymarketAuth, setup_authentication


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("   🤖 Polymarket Auto Trader - API 凭证生成工具")
    print("=" * 70)
    print()
    
    # 检查依赖
    try:
        import eth_account
        from py_clob_client.client import ClobClient
    except ImportError as e:
        print("❌ 缺少必要依赖：")
        print(f"   {e}")
        print()
        print("请安装依赖：")
        print("   pip install eth-account py-clob-client")
        sys.exit(1)
    
    # 检查现有凭证
    creds_file = "config/.api_credentials.json"
    if os.path.exists(creds_file):
        print(f"⚠️  检测到现有凭证文件: {creds_file}")
        choice = input("   是否重新生成? [y/N]: ").strip().lower()
        if choice != 'y':
            print("   使用现有凭证")
            # 加载并显示
            with open(creds_file, 'r') as f:
                cached = json.load(f)
            print(f"\n   API Key: {cached['api_key'][:20]}...")
            print(f"   地址: {cached.get('address', 'Unknown')}")
            print()
            print_env_config(cached)
            return
    
    # 运行认证设置
    success = setup_authentication()
    
    if success:
        print()
        print("=" * 70)
        print("✅ 认证设置完成！")
        print("=" * 70)
        print()
        print("下一步：")
        print("  1. 复制上面的环境变量到 config/.env 文件")
        print("  2. 运行测试脚本: python scripts/test_connection.py")
        print("  3. 启动交易系统: python main.py --dry-run")
    else:
        print()
        print("❌ 认证设置失败")
        sys.exit(1)


def print_env_config(cached):
    """打印环境变量配置"""
    print()
    print("=" * 70)
    print("📋 环境变量配置 (.env)")
    print("=" * 70)
    print()
    print("请将这些行添加到 config/.env 文件：")
    print()
    print("# Polymarket API 配置")
    print(f"POLY_PRIVATE_KEY=你的私钥")
    print(f"POLY_API_KEY={cached['api_key']}")
    print(f"POLY_API_SECRET={cached['secret']}")
    print(f"POLY_API_PASSPHRASE={cached['passphrase']}")
    print(f"POLY_ADDRESS={cached.get('address', '')}")
    print()


if __name__ == "__main__":
    main()
