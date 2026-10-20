#!/usr/bin/env bash
# Ralph loop: envuelve un agente CLI en un while con criterio de término.
# Cada iteración parte de CERO contexto; el file system y git son la memoria.
set -u
cd "$(dirname "$0")"
MAX_ITER="${MAX_ITER:-5}"
MODEL="${MODEL:-claude-opus-5}"
unset CLAUDECODE   # permite correrlo desde dentro de una sesión de Claude Code

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || git init -q

for ((i = 1; i <= MAX_ITER; i++)); do
  echo "=== Ralph iteración $i/$MAX_ITER ==="
  out=$(cat spec.md | claude -p --model "$MODEL" --output-format text \
        --permission-mode acceptEdits --allowedTools "Read,Write,Edit,Bash,Glob,Grep")
  echo "$out" | tail -20
  if echo "$out" | grep -q "COMPLETE"; then
    echo "=== COMPLETE en iteración $i ==="
    exit 0
  fi
done
echo "=== Sin COMPLETE tras $MAX_ITER iteraciones ==="
exit 1
