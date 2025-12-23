from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from pipeline.tasks import extract_to_silver

with DAG("extract_to_silver", start_date=datetime(2024,1,1), schedule=None, catchup=False) as dag:
    PythonOperator(
        task_id="extract",
        python_callable=lambda: extract_to_silver("uploads/sample.pdf"),
    )
