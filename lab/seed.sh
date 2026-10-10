#!/usr/bin/env bash
# Seed the running lab (docker compose up -d first) from the generated spec in lab/.build/.
# Run `python -m itgc scenario` beforehand to (re)generate lab/.build/.
set -euo pipefail
cd "$(dirname "$0")"
until docker compose exec -T dc ldapsearch -x -H ldap://127.0.0.1 -s base -b '' namingContexts >/dev/null 2>&1; do sleep 3; done
docker compose cp .build/ad_spec.json dc:/tmp/ad_spec.json
docker compose cp seed/seed_dc.py dc:/tmp/seed_dc.py
docker compose exec -T dc python3 /tmp/seed_dc.py /tmp/ad_spec.json
docker compose exec -T dc rm -f /tmp/ad_spec.json        # spec contains lab passwords
docker compose cp .build/erp_seed.sql erpdb:/tmp/erp_seed.sql
docker compose exec -T erpdb psql -v ON_ERROR_STOP=1 -U erp_owner -d erp -q -f /tmp/erp_seed.sql
echo "lab seeded"
