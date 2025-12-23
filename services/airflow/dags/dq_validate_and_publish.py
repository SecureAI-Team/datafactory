from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from pipeline.tasks import dq_validate, expand_and_rewrite

with DAG("dq_validate_and_publish", start_date=datetime(2024,1,1), schedule=None, catchup=False) as dag:
    def _validate():
        gid, json_key, md_key, ku_json = expand_and_rewrite("silver/uploads/sample.pdf.json")
        return dq_validate(ku_json)

    PythonOperator(
        task_id="dq_validate",
        python_callable=_validate,
    )
