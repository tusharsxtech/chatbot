#!/bin/sh
set -e

MODEL="${OLLAMA_MODEL:-qwen2.5:1.5b}"

ollama serve &
SERVER_PID=$!

until ollama list >/dev/null 2>&1; do
  sleep 1
done

if ! ollama list | grep -q "^${MODEL}"; then
  ollama pull "${MODEL}"
fi

wait "${SERVER_PID}"
