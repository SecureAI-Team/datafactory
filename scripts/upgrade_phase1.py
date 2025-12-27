#!/usr/bin/env python3
"""
Phase 1 升级脚本
升级意图识别和场景化检索功能

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
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=capture,
        text=True,
    )
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
    
    # 检查 docker compose
    result = run_cmd("docker compose version", check=False, capture=True)
    if result.returncode != 0:
        log("Docker Compose not found", "ERROR")
        sys.exit(1)
    log("Docker Compose OK", "OK")
    
    # 检查 .env 文件
    if not os.path.exists(".env"):
        log(".env file not found", "ERROR")
        log("Please copy .env.example to .env and configure", "INFO")
        sys.exit(1)
    log(".env file OK", "OK")


def check_services_running() -> bool:
    """检查服务是否运行"""
    result = run_cmd(
        "docker compose ps --format json",
        check=False,
        capture=True,
    )
    if result.returncode != 0:
        return False
    
    try:
        # 解析输出
        lines = result.stdout.strip().split('\n')
        running = 0
        for line in lines:
            if line:
                try:
                    container = json.loads(line)
                    if container.get("State") == "running":
                        running += 1
                except json.JSONDecodeError:
                    pass
        return running > 0
    except Exception:
        return False


def backup_current_state():
    """备份当前状态"""
    log("Backing up current state...")
    
    # 创建备份目录
    backup_dir = Path("backups/phase1_upgrade")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # 备份 .env
    if os.path.exists(".env"):
        run_cmd(f"cp .env {backup_dir}/.env.backup")
    
    # 备份 OpenSearch 索引映射
    result = run_cmd(
        'docker compose exec -T api python -c "'
        'from app.clients.opensearch_client import os_client; '
        'from app.config import settings; '
        'import json; '
        'try: '
        '    mapping = os_client.indices.get_mapping(index=settings.os_index); '
        '    print(json.dumps(mapping, indent=2)); '
        'except: '
        '    print(\\\"{}\\\")'
        f'" > {backup_dir}/opensearch_mapping.json',
        check=False,
    )
    
    log(f"Backup saved to {backup_dir}/", "OK")


def rebuild_api_service():
    """重建 API 服务"""
    log("Rebuilding API service with new modules...")
    
    run_cmd("docker compose build --no-cache api")
    log("API service rebuilt", "OK")


def restart_services():
    """重启服务"""
    log("Restarting services...")
    
    run_cmd("docker compose up -d api")
    
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
    log("Verifying upgrade...")
    
    # 测试意图识别
    result = run_cmd(
        '''docker compose exec -T api python -c "
from app.services.intent_recognizer import recognize_intent, IntentType
result = recognize_intent('推荐一个AOI检测方案')
assert result.intent_type == IntentType.SOLUTION_RECOMMENDATION
print(f'Intent: {result.intent_type.value}')
print(f'Scenarios: {result.scenario_ids}')
print(f'Entities: {result.entities}')
print('Intent recognition OK')
"''',
        check=False,
        capture=True,
    )
    
    if result.returncode == 0:
        print(result.stdout)
        log("Intent recognition module OK", "OK")
    else:
        print(result.stderr)
        log("Intent recognition test failed", "WARN")
    
    # 测试场景路由
    result = run_cmd(
        '''docker compose exec -T api python -c "
from app.services.scenario_router import get_scenario_router
from app.services.intent_recognizer import IntentResult, IntentType, SceneClassification
router = get_scenario_router()
intent = IntentResult(
    intent_type=IntentType.PARAMETER_QUERY,
    confidence=0.9,
    scenario_ids=['aoi_inspection'],
)
config = router.route(intent)
print(f'Top K: {config.top_k}')
print(f'Include params: {config.include_params_query}')
print('Scenario router OK')
"''',
        check=False,
        capture=True,
    )
    
    if result.returncode == 0:
        print(result.stdout)
        log("Scenario router module OK", "OK")
    else:
        print(result.stderr)
        log("Scenario router test failed", "WARN")
    
    # 测试澄清引擎
    result = run_cmd(
        '''docker compose exec -T api python -c "
from app.services.clarification import generate_clarification
from app.services.intent_recognizer import IntentResult, IntentType
intent = IntentResult(
    intent_type=IntentType.SOLUTION_RECOMMENDATION,
    confidence=0.6,
    scenario_ids=['aoi_inspection'],
    needs_clarification=True,
)
text = generate_clarification(intent)
if text:
    print('Clarification generated:')
    print(text[:200] + '...')
    print('Clarification engine OK')
else:
    print('No clarification needed')
"''',
        check=False,
        capture=True,
    )
    
    if result.returncode == 0:
        print(result.stdout)
        log("Clarification engine OK", "OK")
    else:
        print(result.stderr)
        log("Clarification engine test failed", "WARN")


def print_summary():
    """打印升级摘要"""
    print("\n" + "=" * 60)
    log("Phase 1 Upgrade Complete!", "OK")
    print("=" * 60)
    print("""
新功能：
1. ✅ 增强的意图识别（规则+LLM混合）
   - 新增 PARAMETER_QUERY（参数查询）意图
   - 新增 CALCULATION（计算选型）意图
   - 新增 CASE_STUDY（案例查询）意图
   - 支持实体抽取（功率、精度、产能等）

2. ✅ 场景化检索路由
   - 根据意图和场景动态调整检索策略
   - 支持参数过滤查询
   - 自动补充通用检索结果

3. ✅ 澄清问卷引擎
   - 动态生成场景相关问题
   - 支持数字选择和自由文本回复
   - 自动解析用户回复

4. ✅ 调试接口
   - GET /v1/debug/index-stats - 索引统计
   - POST /v1/debug/recognize-intent - 意图识别测试
   - POST /v1/debug/search - 场景化检索测试

测试命令：
  # 测试意图识别
  curl -X POST http://localhost:8000/v1/debug/recognize-intent \\
    -H "Content-Type: application/json" \\
    -d '{"query": "AOI设备功率是多少"}'

  # 测试场景化检索
  curl -X POST http://localhost:8000/v1/debug/search \\
    -H "Content-Type: application/json" \\
    -d '{"query": "推荐一个PCB检测方案"}'
""")


def main():
    parser = argparse.ArgumentParser(description="Phase 1 升级脚本")
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="跳过备份步骤",
    )
    parser.add_argument(
        "--skip-rebuild",
        action="store_true",
        help="跳过重建步骤（仅验证）",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="仅验证安装",
    )
    args = parser.parse_args()
    
    print("=" * 60)
    log("AI Data Factory - Phase 1 Upgrade", "INFO")
    log("意图识别增强 & 场景化检索路由", "INFO")
    print("=" * 60 + "\n")
    
    # 检查前置条件
    check_prerequisites()
    
    # 检查服务状态
    services_running = check_services_running()
    
    if args.verify_only:
        if not services_running:
            log("Services not running. Start with: docker compose up -d", "ERROR")
            sys.exit(1)
        verify_upgrade()
        print_summary()
        return
    
    # 备份
    if not args.skip_backup and services_running:
        backup_current_state()
    
    # 重建
    if not args.skip_rebuild:
        rebuild_api_service()
    
    # 重启
    if services_running:
        restart_services()
    else:
        log("Services not running. Start with: docker compose up -d", "WARN")
    
    # 验证
    if services_running or not args.skip_rebuild:
        verify_upgrade()
    
    print_summary()


if __name__ == "__main__":
    main()

