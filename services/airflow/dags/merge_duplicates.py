"""
重复检测与合并 DAG
定期扫描 KU 库，检测重复，生成合并建议，执行已批准的合并
"""
import os
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

import psycopg2
from psycopg2.extras import RealDictCursor

# 导入 pipeline 模块
import sys
sys.path.insert(0, '/opt/pipeline')
from pipeline.dedup_detector import DedupDetector, KUInfo, DuplicateGroup
from pipeline.ku_merger import KUMerger, KUData, MergeResult


# 数据库连接
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        database=os.getenv("POSTGRES_DB", "adf"),
        user=os.getenv("POSTGRES_USER", "adf"),
        password=os.getenv("POSTGRES_PASSWORD", "adfpass"),
    )


def fetch_all_kus(**context) -> List[Dict]:
    """获取所有已发布的 KU"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, title, summary, body_markdown, ku_type, product_id,
                       tags_json, sections_json, version, is_primary,
                       industry_tags, use_case_tags
                FROM knowledge_units
                WHERE status = 'published'
                ORDER BY id
            """)
            rows = cur.fetchall()
            
            # 转换为字典列表
            kus = []
            for row in rows:
                kus.append({
                    "id": str(row["id"]),
                    "title": row["title"],
                    "summary": row["summary"] or "",
                    "body_markdown": row["body_markdown"] or "",
                    "ku_type": row["ku_type"] or "core",
                    "product_id": row["product_id"],
                    "tags": row["tags_json"] if isinstance(row["tags_json"], list) else [],
                    "sections": row["sections_json"] if isinstance(row["sections_json"], list) else [],
                    "version": row["version"] or 1,
                    "is_primary": row["is_primary"] or False,
                    "industry_tags": row["industry_tags"] if isinstance(row["industry_tags"], list) else [],
                    "use_case_tags": row["use_case_tags"] if isinstance(row["use_case_tags"], list) else [],
                })
            
            print(f"获取到 {len(kus)} 个已发布的 KU")
            return kus
    finally:
        conn.close()


def detect_duplicates(**context) -> List[Dict]:
    """检测重复"""
    ti = context["ti"]
    kus_data = ti.xcom_pull(task_ids="fetch_all_kus")
    
    if not kus_data:
        print("没有 KU 数据，跳过检测")
        return []
    
    # 转换为 KUInfo
    ku_infos = [
        KUInfo(
            id=ku["id"],
            title=ku["title"],
            summary=ku["summary"],
            product_id=ku["product_id"],
            ku_type=ku["ku_type"],
        )
        for ku in kus_data
    ]
    
    # 执行检测
    detector = DedupDetector(semantic_threshold=0.85)
    groups = detector.detect_duplicates(ku_infos)
    
    print(f"检测到 {len(groups)} 个重复组")
    
    # 转换为可序列化的字典
    result = []
    for group in groups:
        result.append({
            "group_id": group.group_id,
            "ku_ids": group.ku_ids,
            "similarity_score": group.similarity_score,
            "match_type": group.match_type,
            "merge_recommendation": group.merge_recommendation,
            "details": group.details,
        })
    
    return result


def save_dedup_groups(**context) -> int:
    """保存重复组到数据库"""
    ti = context["ti"]
    groups = ti.xcom_pull(task_ids="detect_duplicates")
    
    if not groups:
        print("没有检测到重复组")
        return 0
    
    conn = get_db_connection()
    saved_count = 0
    
    try:
        with conn.cursor() as cur:
            for group in groups:
                # 检查是否已存在
                cur.execute("""
                    SELECT id FROM dedup_groups
                    WHERE ku_ids::text = %s::text AND status = 'pending'
                """, (json.dumps(sorted(group["ku_ids"])),))
                
                if cur.fetchone():
                    print(f"重复组 {group['group_id']} 已存在，跳过")
                    continue
                
                # 插入新记录
                cur.execute("""
                    INSERT INTO dedup_groups (group_id, ku_ids, similarity_score, status)
                    VALUES (%s, %s, %s, 'pending')
                    ON CONFLICT (group_id) DO NOTHING
                """, (
                    group["group_id"],
                    json.dumps(group["ku_ids"]),
                    group["similarity_score"],
                ))
                saved_count += 1
        
        conn.commit()
        print(f"保存了 {saved_count} 个新的重复组")
        return saved_count
        
    finally:
        conn.close()


def execute_approved_merges(**context) -> int:
    """执行已批准的合并"""
    conn = get_db_connection()
    merged_count = 0
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 获取已批准待执行的合并
            cur.execute("""
                SELECT id, group_id, ku_ids
                FROM dedup_groups
                WHERE status = 'approved'
                ORDER BY created_at
                LIMIT 10
            """)
            approved_groups = cur.fetchall()
            
            if not approved_groups:
                print("没有待执行的合并")
                return 0
            
            merger = KUMerger(use_llm=False)  # 不使用 LLM 以提高速度
            
            for group in approved_groups:
                try:
                    # 获取要合并的 KU 详情
                    ku_ids = group["ku_ids"]
                    placeholders = ",".join(["%s"] * len(ku_ids))
                    cur.execute(f"""
                        SELECT id, title, summary, body_markdown, ku_type, product_id,
                               tags_json, sections_json, version,
                               industry_tags, use_case_tags
                        FROM knowledge_units
                        WHERE id IN ({placeholders})
                    """, ku_ids)
                    ku_rows = cur.fetchall()
                    
                    if len(ku_rows) < 2:
                        print(f"组 {group['group_id']} 的 KU 数量不足，跳过")
                        continue
                    
                    # 转换为 KUData
                    kus = []
                    for row in ku_rows:
                        kus.append(KUData(
                            id=str(row["id"]),
                            title=row["title"],
                            summary=row["summary"] or "",
                            body_markdown=row["body_markdown"] or "",
                            ku_type=row["ku_type"] or "core",
                            product_id=row["product_id"],
                            tags=row["tags_json"] if isinstance(row["tags_json"], list) else [],
                            sections=row["sections_json"] if isinstance(row["sections_json"], list) else [],
                            version=row["version"] or 1,
                            industry_tags=row["industry_tags"] if isinstance(row["industry_tags"], list) else [],
                            use_case_tags=row["use_case_tags"] if isinstance(row["use_case_tags"], list) else [],
                        ))
                    
                    # 执行合并
                    result = merger.merge_kus(kus, strategy="comprehensive")
                    
                    if not result.success:
                        print(f"组 {group['group_id']} 合并失败: {result.error}")
                        continue
                    
                    # 创建新的合并后 KU
                    merged_ku = result.merged_ku
                    cur.execute("""
                        INSERT INTO knowledge_units (
                            title, summary, body_markdown, ku_type, product_id,
                            tags_json, sections_json, version, is_primary,
                            merge_source_ids, industry_tags, use_case_tags,
                            status, created_by
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, true, %s, %s, %s, 'published', 'system_merge'
                        ) RETURNING id
                    """, (
                        merged_ku.title,
                        merged_ku.summary,
                        merged_ku.body_markdown,
                        merged_ku.ku_type,
                        merged_ku.product_id,
                        json.dumps(merged_ku.tags),
                        json.dumps(merged_ku.sections),
                        merged_ku.version,
                        json.dumps(result.source_ku_ids),
                        json.dumps(merged_ku.industry_tags),
                        json.dumps(merged_ku.use_case_tags),
                    ))
                    new_ku_id = cur.fetchone()[0]
                    
                    # 标记源 KU 为已合并
                    cur.execute(f"""
                        UPDATE knowledge_units
                        SET status = 'merged', parent_ku_id = %s
                        WHERE id IN ({placeholders})
                    """, [str(new_ku_id)] + ku_ids)
                    
                    # 创建关联关系
                    for source_id in ku_ids:
                        cur.execute("""
                            INSERT INTO ku_relations (source_ku_id, target_ku_id, relation_type, metadata)
                            VALUES (%s, %s, 'merged_from', %s)
                        """, (
                            str(new_ku_id),
                            str(source_id),
                            json.dumps(result.merge_report),
                        ))
                    
                    # 更新重复组状态
                    cur.execute("""
                        UPDATE dedup_groups
                        SET status = 'merged', merge_result_ku_id = %s
                        WHERE id = %s
                    """, (new_ku_id, group["id"]))
                    
                    merged_count += 1
                    print(f"成功合并组 {group['group_id']} -> 新 KU {new_ku_id}")
                    
                except Exception as e:
                    print(f"处理组 {group['group_id']} 时出错: {e}")
                    continue
        
        conn.commit()
        print(f"完成 {merged_count} 个合并")
        return merged_count
        
    finally:
        conn.close()


def generate_report(**context) -> Dict:
    """生成重复检测报告"""
    ti = context["ti"]
    groups = ti.xcom_pull(task_ids="detect_duplicates") or []
    saved_count = ti.xcom_pull(task_ids="save_dedup_groups") or 0
    merged_count = ti.xcom_pull(task_ids="execute_approved_merges") or 0
    
    report = {
        "run_date": datetime.now().isoformat(),
        "detected_groups": len(groups),
        "new_groups_saved": saved_count,
        "merges_executed": merged_count,
        "recommendations": {
            "merge": len([g for g in groups if g.get("merge_recommendation") == "merge"]),
            "review": len([g for g in groups if g.get("merge_recommendation") == "review"]),
            "keep_all": len([g for g in groups if g.get("merge_recommendation") == "keep_all"]),
        }
    }
    
    print(f"重复检测报告: {json.dumps(report, indent=2)}")
    return report


# DAG 定义
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    "merge_duplicates",
    default_args=default_args,
    description="检测和合并重复的 KU",
    schedule_interval="0 2 * * *",  # 每天凌晨2点执行
    start_date=days_ago(1),
    catchup=False,
    tags=["dedup", "merge", "maintenance"],
) as dag:
    
    fetch_task = PythonOperator(
        task_id="fetch_all_kus",
        python_callable=fetch_all_kus,
        provide_context=True,
    )
    
    detect_task = PythonOperator(
        task_id="detect_duplicates",
        python_callable=detect_duplicates,
        provide_context=True,
    )
    
    save_task = PythonOperator(
        task_id="save_dedup_groups",
        python_callable=save_dedup_groups,
        provide_context=True,
    )
    
    merge_task = PythonOperator(
        task_id="execute_approved_merges",
        python_callable=execute_approved_merges,
        provide_context=True,
    )
    
    report_task = PythonOperator(
        task_id="generate_report",
        python_callable=generate_report,
        provide_context=True,
    )
    
    fetch_task >> detect_task >> save_task >> merge_task >> report_task

