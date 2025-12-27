#!/usr/bin/env python3
"""
Phase 2 升级脚本
升级上下文管理、计算引擎、反馈优化功能

支持：
- 现有部署升级
- 新部署初始化
"""
import os
import sys
import json
import argparse
import subprocess
from pathlib import Path


def log(msg: str, level: str = "INFO"):
    """打印日志"""
    icons = {"INFO": "ℹ️", "OK": "✅", "WARN": "⚠️", "ERROR": "❌", "STEP": "🔧"}
    print(f"{icons.get(level, '•')} {msg}")


def run_cmd(cmd: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """执行命令"""
    log(f"Running: {cmd}", "STEP")
    result = subprocess.run(cmd, shell=True, capture_output=capture, text=True)
    if check and result.returncode != 0:
        log(f"Command failed: {cmd}", "ERROR")
        if capture:
            print(result.stderr)
        sys.exit(1)
    return result


def check_prerequisites():
    """检查前置条件"""
    log("Checking prerequisites...")
    
    # 检查 Docker
    result = run_cmd("docker --version", check=False, capture=True)
    if result.returncode != 0:
        log("Docker not found", "ERROR")
        sys.exit(1)
    log("Docker OK", "OK")
    
    # 检查 .env 文件
    if not os.path.exists(".env"):
        log(".env file not found", "ERROR")
        sys.exit(1)
    log(".env file OK", "OK")


def run_migrations():
    """运行数据库迁移"""
    log("Running database migrations...")
    
    result = run_cmd(
        "docker compose run --rm api alembic upgrade head",
        check=False,
        capture=True,
    )
    
    if result.returncode == 0:
        log("Database migrations completed", "OK")
    else:
        log(f"Migration warning: {result.stderr[:200]}", "WARN")


def rebuild_api_service():
    """重建 API 服务"""
    log("Rebuilding API service with Phase 2 modules...")
    
    run_cmd("docker compose build --no-cache api")
    log("API service rebuilt", "OK")


def restart_services():
    """重启服务"""
    log("Restarting services...")
    
    run_cmd("docker compose up -d api redis")
    
    # 等待服务就绪
    log("Waiting for API service to be ready...")
    import time
    for i in range(30):
        result = run_cmd(
            "docker compose exec -T api curl -s http://localhost:8000/health",
            check=False,
            capture=True,
        )
        if result.returncode == 0:
            log("API service is ready", "OK")
            return
        time.sleep(2)
    
    log("API service did not become ready in time", "WARN")


def verify_upgrade():
    """验证升级"""
    log("Verifying Phase 2 upgrade...")
    
    # 测试上下文管理
    result = run_cmd(
        '''docker compose exec -T api python -c "
from app.services.context_manager import get_or_create_context, save_context
ctx = get_or_create_context('test-conv-123')
ctx.add_turn('user', 'test query')
ctx.set_preference('budget_range', 'medium')
save_context(ctx)
ctx2 = get_or_create_context('test-conv-123')
assert len(ctx2.turns) == 1
assert ctx2.get_preference('budget_range') == 'medium'
print('Context manager OK')
"''',
        check=False,
        capture=True,
    )
    
    if result.returncode == 0:
        print(result.stdout)
        log("Context manager OK", "OK")
    else:
        print(result.stderr)
        log("Context manager test failed", "WARN")
    
    # 测试计算引擎
    result = run_cmd(
        '''docker compose exec -T api python -c "
from app.services.calculation_engine import try_calculate
result = try_calculate(
    query='产能5000片/小时需要几台设备',
    entities={'产能': {'value': 5000, 'unit': 'pcs/h'}},
)
assert result is not None
assert result.success
print(f'Calculation result: {result.result_value} {result.result_unit}')
print(f'Reasoning: {result.reasoning}')
print('Calculation engine OK')
"''',
        check=False,
        capture=True,
    )
    
    if result.returncode == 0:
        print(result.stdout)
        log("Calculation engine OK", "OK")
    else:
        print(result.stderr)
        log("Calculation engine test failed", "WARN")
    
    # 测试反馈优化器
    result = run_cmd(
        '''docker compose exec -T api python -c "
from app.services.feedback_optimizer import get_feedback_optimizer, FeedbackType
optimizer = get_feedback_optimizer()

# Test feedback detection
detection = optimizer.detect_natural_feedback('非常有帮助，谢谢')
assert detection is not None
assert detection[0] == FeedbackType.NATURAL_POSITIVE
print(f'Detected feedback: {detection}')

# Test recording
record = optimizer.record_feedback(
    conversation_id='test-123',
    feedback_type=FeedbackType.EXPLICIT_POSITIVE,
    query='test query',
    response='test response',
    rating=5,
    intent_type='technical_qa',
)
print(f'Recorded feedback: {record.feedback_id}')
print('Feedback optimizer OK')
"''',
        check=False,
        capture=True,
    )
    
    if result.returncode == 0:
        print(result.stdout)
        log("Feedback optimizer OK", "OK")
    else:
        print(result.stderr)
        log("Feedback optimizer test failed", "WARN")


def print_summary():
    """打印升级摘要"""
    print("\n" + "=" * 60)
    log("Phase 2 Upgrade Complete!", "OK")
    print("=" * 60)
    print("""
新功能：

1. ✅ 对话上下文管理
   - 实体跟踪：自动提取和追踪对话中的参数
   - 偏好记忆：记住用户偏好（预算、技术水平等）
   - 历史压缩：长对话自动摘要压缩
   - 上下文注入：将历史上下文融入 Prompt

2. ✅ 计算引擎
   - 设备数量估算：根据产能需求计算设备数量
   - 精度校验：判断设备是否能检测特定缺陷
   - 成本计算：单件检测成本估算
   - ROI 计算：投资回报周期估算
   - 产能匹配：判断设备产能是否满足需求

3. ✅ 反馈优化
   - 自然语言反馈检测：识别"有帮助"/"不满意"等表达
   - 反馈统计：按意图、场景汇总反馈数据
   - Prompt 增强：基于正面反馈案例增强 Prompt
   - 问题分析：识别常见问题模式

4. ✅ 新增调试接口
   - POST /v1/debug/calculate     - 测试计算引擎
   - GET  /v1/debug/context/{id}  - 查看对话上下文
   - GET  /v1/debug/feedback-stats - 反馈统计
   - POST /v1/debug/record-feedback - 手动记录反馈

测试命令：

  # 测试计算引擎
  curl -X POST http://localhost:8000/v1/debug/calculate \\
    -H "Content-Type: application/json" \\
    -d '{"query": "产能5000片/小时需要几台AOI设备"}'

  # 查看反馈统计
  curl http://localhost:8000/v1/debug/feedback-stats

  # 在 Open WebUI 中测试多轮对话
  # 1. 问：推荐一个AOI检测方案
  # 2. 补充：预算50万，检测PCB焊点
  # 3. 追问：需要几台设备才能满足每小时5000片的产能
""")


def main():
    parser = argparse.ArgumentParser(description="Phase 2 升级脚本")
    parser.add_argument("--skip-rebuild", action="store_true", help="跳过重建步骤")
    parser.add_argument("--skip-migrations", action="store_true", help="跳过数据库迁移")
    parser.add_argument("--verify-only", action="store_true", help="仅验证安装")
    args = parser.parse_args()
    
    print("=" * 60)
    log("AI Data Factory - Phase 2 Upgrade", "INFO")
    log("上下文管理 + 计算引擎 + 反馈优化", "INFO")
    print("=" * 60 + "\n")
    
    check_prerequisites()
    
    if args.verify_only:
        verify_upgrade()
        print_summary()
        return
    
    # 数据库迁移
    if not args.skip_migrations:
        run_migrations()
    
    # 重建
    if not args.skip_rebuild:
        rebuild_api_service()
    
    # 重启
    restart_services()
    
    # 验证
    verify_upgrade()
    
    print_summary()


if __name__ == "__main__":
    main()

