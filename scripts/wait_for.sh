#!/bin/sh
set -e
host=${1:-localhost}
port=${2:-80}
echo "waiting for $host:$port"
until nc -z "$host" "$port"; do sleep 2; done
