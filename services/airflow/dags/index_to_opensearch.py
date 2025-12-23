from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from pipeline.tasks import index_to_opensearch, expand_and_rewrite

with DAG("index_to_opensearch", start_date=datetime(2024,1,1), schedule=None, catchup=False) as dag:
    def _index():
        gid, json_key, md_key, ku_json = expand_and_rewrite("silver/uploads/sample.pdf.json")
        return index_to_opensearch(ku_json, gid)

    PythonOperator(
        task_id="index",
        python_callable=_index,
    )
