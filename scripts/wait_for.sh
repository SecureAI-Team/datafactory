#!/usr/bin/env bash
set -e
host=$1; port=$2
echo "waiting for $host:$port"
until nc -z $host $port; do sleep 2; done
