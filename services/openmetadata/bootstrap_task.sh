#!/usr/bin/env bash
curl -X POST http://openmetadata:8585/api/v1/tasks \
 -H "Content-Type: application/json" \
 -d "{\"name\":\"Missing evidence\",\"description\":\"Provide citations for KU 1\",\"type\":\"RequestForEnhancement\"}"
