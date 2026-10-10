#!/usr/bin/env bash
# Apply management's remediation to the running lab, then re-collect with --label fy26-remediation.
set -euo pipefail
cd "$(dirname "$0")"
docker compose cp scripts/remediate_dc.sh dc:/tmp/remediate_dc.sh
docker compose exec -T dc bash /tmp/remediate_dc.sh
docker compose exec -T erpdb psql -v ON_ERROR_STOP=1 -U erp_owner -d erp -f /lab-scripts/remediate_erp.sql
