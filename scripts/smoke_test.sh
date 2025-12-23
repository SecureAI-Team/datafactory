#!/usr/bin/env bash
set -e
python scripts/create_buckets.py
python scripts/create_opensearch_index.py
python scripts/seed_data.py
echo "Smoke placeholder: run pipelines and gateway manually in this stub."
