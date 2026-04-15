#!/bin/bash
# Task helper — быстрая работа с дашбордом
# Usage:
#   task.sh create "Title" "Description" [department_id] [priority]
#   task.sh start <task_id>
#   task.sh done <task_id>
#   task.sh step <task_id> <pos> "Title" "Description" [status]
#   task.sh step-done <task_id> <step_id>
#   task.sh list [status]
#   task.sh get <task_id>

API="http://localhost:8080/api"

case "$1" in
  create)
    curl -s -X POST "$API/tasks" \
      -H "Content-Type: application/json" \
      -d "{\"title\":\"$2\",\"description\":\"$3\",\"department_id\":${4:-1},\"status\":\"todo\",\"priority\":\"${5:-normal}\"}"
    ;;
  start)
    curl -s -X PUT "$API/tasks/$2" \
      -H "Content-Type: application/json" \
      -d '{"status":"in_progress"}'
    ;;
  done)
    curl -s -X PUT "$API/tasks/$2" \
      -H "Content-Type: application/json" \
      -d '{"status":"done"}'
    ;;
  review)
    curl -s -X PUT "$API/tasks/$2" \
      -H "Content-Type: application/json" \
      -d '{"status":"review"}'
    ;;
  step)
    curl -s -X POST "$API/tasks/$2/steps" \
      -H "Content-Type: application/json" \
      -d "{\"position\":$3,\"title\":\"$4\",\"description\":\"$5\",\"status\":\"${6:-pending}\"}"
    ;;
  step-done)
    curl -s -X PUT "$API/tasks/$2/steps/$3" \
      -H "Content-Type: application/json" \
      -d '{"status":"done"}'
    ;;
  step-start)
    curl -s -X PUT "$API/tasks/$2/steps/$3" \
      -H "Content-Type: application/json" \
      -d '{"status":"in_progress"}'
    ;;
  list)
    if [ -n "$2" ]; then
      curl -s "$API/tasks" | python3 -c "
import json,sys
for t in json.load(sys.stdin):
    if t['status']=='$2':
        print(f'#{t[\"id\"]} [{t[\"status\"]}] {t[\"priority\"]}: {t[\"title\"]}')"
    else
      curl -s "$API/tasks" | python3 -c "
import json,sys
for t in json.load(sys.stdin):
    s = {'todo':'⏳','in_progress':'🔄','review':'👀','done':'✅'}.get(t['status'],'?')
    print(f'{s} #{t[\"id\"]} [{t[\"status\"]}] {t[\"title\"]}')"
    fi
    ;;
  get)
    curl -s "$API/tasks/$2" | python3 -c "
import json,sys
t=json.load(sys.stdin)
print(f'#{t[\"id\"]} [{t[\"status\"]}] {t[\"title\"]}')
print(f'  {t.get(\"description\",\"\")}')"
    curl -s "$API/tasks/$2/steps" | python3 -c "
import json,sys
for s in json.load(sys.stdin):
    icon = {'pending':'⏳','in_progress':'🔄','done':'✅','skipped':'⏭'}.get(s['status'],'?')
    print(f'  {icon} Step {s[\"position\"]}: {s[\"title\"]}')"
    ;;
  *)
    echo "Usage: task.sh {create|start|done|review|step|step-done|step-start|list|get} [args]"
    ;;
esac
