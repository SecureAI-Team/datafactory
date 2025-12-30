#!/usr/bin/env python3
"""
创建默认管理员用户

用法:
    python scripts/create_admin_user.py
    
或在 Docker 中运行:
    docker compose exec api python /work/scripts/create_admin_user.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'api'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Try to use passlib, fallback to bcrypt directly
try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)
except Exception:
    # Fallback: use bcrypt directly
    import bcrypt
    
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# Default users to create
DEFAULT_USERS = [
    {
        "username": "admin",
        "email": "admin@example.com",
        "password": "admin123",
        "display_name": "系统管理员",
        "role": "admin",
        "department": "IT",
    },
    {
        "username": "dataops",
        "email": "dataops@example.com",
        "password": "dataops123",
        "display_name": "数据运维",
        "role": "data_ops",
        "department": "数据团队",
    },
    {
        "username": "sales",
        "email": "sales@example.com",
        "password": "sales123",
        "display_name": "销售用户",
        "role": "bd_sales",
        "department": "销售部",
    },
]


def get_database_url():
    """构建数据库连接 URL"""
    user = os.getenv("POSTGRES_USER", "adf")
    password = os.getenv("POSTGRES_PASSWORD", "adfpass")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "adf")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def create_users():
    """创建默认用户"""
    database_url = get_database_url()
    print(f"连接数据库: {database_url.replace(os.getenv('POSTGRES_PASSWORD', 'adfpass'), '***')}")
    
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        for user_data in DEFAULT_USERS:
            # 检查用户是否已存在
            result = session.execute(
                text("SELECT id, password_hash FROM users WHERE username = :username"),
                {"username": user_data["username"]}
            ).fetchone()
            
            # 生成密码哈希
            password_hash = hash_password(user_data["password"])
            
            if result:
                user_id, existing_hash = result
                # 检查密码哈希是否有效（以 $2b$ 开头且长度足够）
                if existing_hash and existing_hash.startswith('$2b$') and len(existing_hash) >= 59:
                    print(f"  ⏭️  用户 '{user_data['username']}' 已存在（密码有效），跳过")
                else:
                    # 更新无效的密码哈希
                    session.execute(
                        text("UPDATE users SET password_hash = :password_hash WHERE id = :user_id"),
                        {"password_hash": password_hash, "user_id": user_id}
                    )
                    print(f"  🔄 更新用户 '{user_data['username']}' 的密码哈希")
                continue
            
            # 插入用户
            session.execute(
                text("""
                    INSERT INTO users (username, email, password_hash, display_name, role, department, is_active)
                    VALUES (:username, :email, :password_hash, :display_name, :role, :department, true)
                """),
                {
                    "username": user_data["username"],
                    "email": user_data["email"],
                    "password_hash": password_hash,
                    "display_name": user_data["display_name"],
                    "role": user_data["role"],
                    "department": user_data["department"],
                }
            )
            
            print(f"  ✅ 创建用户: {user_data['username']} ({user_data['role']})")
        
        session.commit()
        print("\n✅ 用户创建完成!")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ 创建用户失败: {e}")
        raise
    finally:
        session.close()


def print_credentials():
    """打印默认凭据"""
    print("\n" + "=" * 50)
    print("📋 默认登录凭据")
    print("=" * 50)
    print()
    print("┌──────────────┬───────────────┬─────────────┐")
    print("│ 用户名       │ 密码          │ 角色        │")
    print("├──────────────┼───────────────┼─────────────┤")
    for user in DEFAULT_USERS:
        print(f"│ {user['username']:<12} │ {user['password']:<13} │ {user['role']:<11} │")
    print("└──────────────┴───────────────┴─────────────┘")
    print()
    print("⚠️  请在生产环境中修改这些默认密码!")
    print()


if __name__ == "__main__":
    print("=" * 50)
    print("🔧 创建默认用户")
    print("=" * 50)
    print()
    
    try:
        create_users()
        print_credentials()
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)

