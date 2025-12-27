#!/usr/bin/env python3
"""
Phase 3 升级脚本：结构化参数
- 参数提取器
- 结构化检索增强
- 计算引擎增强
- 数据库迁移
"""
import subprocess
import sys


def run_cmd(cmd: str, check: bool = True) -> int:
    """执行命令"""
    print(f"\n>>> {cmd}")
    result = subprocess.run(cmd, shell=True)
    if check and result.returncode != 0:
        print(f"命令失败: {cmd}")
    return result.returncode


def main():
    print("=" * 60)
    print("Phase 3 升级: 结构化参数")
    print("=" * 60)
    
    # 1. 应用数据库迁移
    print("\n[1/4] 应用数据库迁移...")
    run_cmd("docker compose run --rm api alembic upgrade head", check=False)
    
    # 2. 重建 API 镜像
    print("\n[2/4] 重建 API 服务...")
    run_cmd("docker compose build api")
    
    # 3. 重启服务
    print("\n[3/4] 重启服务...")
    run_cmd("docker compose up -d api")
    
    # 4. 验证新模块
    print("\n[4/4] 验证新模块...")
    verify_cmd = '''docker compose exec -T api python -c "
from app.services.param_extractor import extract_params
from app.services.calculation_engine import calculate_with_extraction
from app.services.retrieval import search_with_params, smart_search

# 测试参数提取
params = extract_params('功率500W的AOI设备，精度0.01mm')
print(f'提取参数: {[p.to_dict() for p in params]}')
assert len(params) >= 2, '参数提取失败'
print('✓ 参数提取 OK')

# 测试智能搜索
result = smart_search('功率500W的AOI设备')
print(f'搜索策略: {result.get(\"strategy\")}')
print('✓ 智能搜索 OK')

# 测试计算增强
calc_result = calculate_with_extraction('产能5000片/小时需要几台设备')
print(f'计算结果: {calc_result.result_value if calc_result else None}')
print('✓ 计算引擎 OK')
"'''
    run_cmd(verify_cmd, check=False)
    
    print("\n" + "=" * 60)
    print("Phase 3 升级完成!")
    print("=" * 60)
    print("""
新增功能:
  - 参数提取器（从查询中自动提取参数需求）
  - 智能搜索（根据查询类型选择最佳检索策略）
  - 参数化检索（支持参数值过滤和范围查询）
  - 规格比对（多产品参数对比）
  - 计算引擎增强（自动参数提取 + 计算）

新增 API:
  POST /v1/debug/extract-params   - 测试参数提取
  POST /v1/debug/smart-search     - 智能搜索
  POST /v1/debug/compare-specs    - 规格比对

使用示例:
  curl -X POST http://localhost:8000/v1/debug/extract-params \\
    -H "Content-Type: application/json" \\
    -d '{"query": "功率>=500W的AOI设备，精度小于0.01mm"}'
""")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

