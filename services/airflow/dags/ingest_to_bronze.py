from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from pipeline.tasks import ingest_to_bronze

with DAG("ingest_to_bronze", start_date=datetime(2024,1,1), schedule=None, catchup=False) as dag:
    PythonOperator(
        task_id="ingest",
        python_callable=lambda: ingest_to_bronze("/tmp/sample.pdf", "uploads/sample.pdf"),
    )
