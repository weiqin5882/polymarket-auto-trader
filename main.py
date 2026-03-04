#!/usr/bin/env python3
"""
Polymarket Auto Trader - 主入口
"""

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from trading.core import ProfitSystem
from trading.executor import AutomatedTradingSystem


def load_config(config_path: str = "config/system.json") -> dict:
    """加载配置"""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ 配置文件不存在: {config_path}")
        print("请复制 config/system.json.example 为 config/system.json 并填写配置")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Polymarket Auto Trader')
    parser.add_argument('--config', '-c', default='config/system.json', help='配置文件路径')
    parser.add_argument('--dry-run', action='store_true', help='模拟模式（不实际交易）')
    parser.add_argument('--live', action='store_true', help='实盘交易模式')
    parser.add_argument('--strategy', '-s', help='只运行指定策略')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🚀 Polymarket Auto Trader")
    print("=" * 60)
    
    # 加载配置
    config = load_config(args.config)
    
    # 设置模式
    if args.dry_run:
        print("\n📍 模式: 模拟交易（dry-run）")
        os.environ['TRADING_MODE'] = 'dry-run'
    elif args.live:
        print("\n⚠️  模式: 实盘交易（LIVE）")
        confirm = input("确认开始实盘交易？这将使用真实资金！[yes/no]: ")
        if confirm.lower() != 'yes':
            print("已取消")
            return
        os.environ['TRADING_MODE'] = 'live'
    else:
        print("\n📍 模式: 模拟交易（默认）")
        os.environ['TRADING_MODE'] = 'dry-run'
    
    # 创建并启动系统
    system = AutomatedTradingSystem(config)
    
    try:
        asyncio.run(system.start())
    except KeyboardInterrupt:
        print("\n\n👋 用户中断，正在安全停止...")
        asyncio.run(system.stop())
    except Exception as e:
        print(f"\n❌ 系统错误: {e}")
        raise


if __name__ == "__main__":
    main()
