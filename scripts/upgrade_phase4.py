#!/usr/bin/env python3
"""
Phase 4 升级脚本：优化闭环
- 场景切换检测
- 反馈分析报表
- 自动Prompt优化
- 质量监控仪表盘
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
    print("Phase 4 升级: 优化闭环")
    print("=" * 60)
    
    # 1. 重建 API 镜像
    print("\n[1/3] 重建 API 服务...")
    run_cmd("docker compose build api")
    
    # 2. 重启服务
    print("\n[2/3] 重启服务...")
    run_cmd("docker compose up -d api")
    
    # 3. 验证新模块
    print("\n[3/3] 验证新模块...")
    verify_cmd = '''docker compose exec -T api python -c "
from app.services.scenario_switch_detector import detect_scenario_switch
from app.services.feedback_analyzer import analyze_feedback
from app.services.prompt_optimizer import get_optimization_suggestions
from app.services.quality_monitor import get_health_status

# 测试场景切换检测
result = detect_scenario_switch('换个话题，问一下成本问题', ['AOI设备功率多少？'])
print(f'场景切换检测: {result.switch_type.value}')
assert result.switch_type.value != 'none', '场景切换检测失败'
print('✓ 场景切换检测 OK')

# 测试反馈分析
report = analyze_feedback(days=1)
print(f'反馈分析: 健康评分 {report.health_score:.0f}')
print('✓ 反馈分析 OK')

# 测试Prompt优化
suggestions = get_optimization_suggestions()
print(f'优化建议数: {len(suggestions)}')
print('✓ Prompt优化器 OK')

# 测试质量监控
health = get_health_status()
print(f'健康状态: {\"健康\" if health.healthy else \"降级\"}, 评分 {health.score:.0f}')
print('✓ 质量监控 OK')
"'''
    run_cmd(verify_cmd, check=False)
    
    print("\n" + "=" * 60)
    print("Phase 4 升级完成!")
    print("=" * 60)
    print("""
新增功能:
  - 场景切换检测（识别话题转换、追问、澄清）
  - 反馈分析报表（按意图/场景统计，识别问题模式）
  - 自动Prompt优化（基于反馈生成Few-shot和改进建议）
  - 质量监控仪表盘（核心指标跟踪、告警）

新增 API:
  POST /v1/debug/detect-switch          - 场景切换检测
  GET  /v1/debug/feedback-report        - 反馈分析报告
  GET  /v1/debug/feedback-trend         - 反馈趋势
  GET  /v1/debug/optimization-suggestions - 优化建议
  GET  /v1/debug/health                 - 健康状态
  GET  /v1/debug/dashboard              - 监控仪表盘

使用示例:
  # 场景切换检测
  curl -X POST http://localhost:8000/v1/debug/detect-switch \\
    -H "Content-Type: application/json" \\
    -d '{"query": "换个话题，问一下成本", "previous_queries": ["AOI功率多少"]}'

  # 反馈分析报告
  curl http://localhost:8000/v1/debug/feedback-report?days=7

  # 健康状态
  curl http://localhost:8000/v1/debug/health
""")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

