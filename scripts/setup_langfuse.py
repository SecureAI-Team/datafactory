#!/usr/bin/env python3
"""
Langfuse 项目初始化脚本
创建项目和 API Keys
"""
import os
import requests
import json

# Langfuse 配置
LANGFUSE_URL = os.getenv("LANGFUSE_URL", "http://localhost:3000")
LANGFUSE_EMAIL = os.getenv("LANGFUSE_ADMIN_EMAIL", "admin@adf.local")
LANGFUSE_PASSWORD = os.getenv("LANGFUSE_ADMIN_PASSWORD", "admin123456")

def print_manual_setup():
    """打印手动设置指南"""
    print("""
============================================================
Langfuse 配置指南
============================================================

Langfuse 需要通过 Web UI 进行初始设置。请按以下步骤操作:

1. 访问 Langfuse: http://<ECS_IP>:3000

2. 首次访问时创建管理员账户:
   - Email: admin@adf.local (或你的邮箱)
   - Password: 设置一个强密码

3. 登录后创建项目:
   - 点击 "New Project"
   - Name: AI Data Factory
   - 点击 "Create"

4. 获取 API Keys:
   - 进入项目设置 (Settings)
   - 点击 "API Keys" -> "Create new API key"
   - 复制 Public Key 和 Secret Key

5. 更新 .env 文件:
   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxx
   LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxx
   ```

6. 重启 API 服务:
   ```bash
   docker compose restart api
   ```

7. 验证集成:
   - 在 Open WebUI 中发送一条消息
   - 返回 Langfuse 查看 Traces

============================================================
Langfuse 功能说明
============================================================

- Traces: 查看所有 LLM 调用记录
- Generations: 查看生成的内容
- Scores: 用户反馈评分
- Sessions: 会话追踪
- Prompts: Prompt 版本管理

Dashboard 提供:
- Token 使用统计
- 延迟分析
- 成本估算
- 质量评分趋势

============================================================
""")


def check_langfuse_health():
    """检查 Langfuse 是否运行"""
    try:
        response = requests.get(f"{LANGFUSE_URL}/api/public/health", timeout=5)
        if response.status_code == 200:
            print(f"✓ Langfuse 运行正常: {LANGFUSE_URL}")
            return True
        else:
            print(f"⚠ Langfuse 响应异常: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"✗ 无法连接 Langfuse: {LANGFUSE_URL}")
        print("  请确保 Langfuse 服务已启动: docker compose up -d langfuse")
        return False


def main():
    print("=" * 60)
    print("Langfuse 初始化")
    print("=" * 60)
    
    # 检查服务状态
    check_langfuse_health()
    
    # 打印手动设置指南
    print_manual_setup()
    
    print("""
提示: Langfuse 目前不支持完全自动化的 API 项目创建。
请按照上述指南在 Web UI 中完成配置。

完成后，API 服务会自动将 LLM 调用记录发送到 Langfuse。
""")


if __name__ == "__main__":
    main()

