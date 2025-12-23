from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from pipeline.tasks import expand_and_rewrite

with DAG("expand_and_rewrite_to_gold", start_date=datetime(2024,1,1), schedule=None, catchup=False) as dag:
    PythonOperator(
        task_id="expand_rewrite",
        python_callable=lambda: expand_and_rewrite("silver/uploads/sample.pdf.json"),
    )
