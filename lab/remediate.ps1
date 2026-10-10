# PowerShell equivalent of remediate.sh.
Set-Location $PSScriptRoot
docker compose cp scripts/remediate_dc.sh dc:/tmp/remediate_dc.sh 2>&1 | Out-Null
docker compose exec -T dc bash /tmp/remediate_dc.sh 2>&1 | ForEach-Object { "$_" }
docker compose exec -T erpdb psql -v ON_ERROR_STOP=1 -U erp_owner -d erp -f /lab-scripts/remediate_erp.sql 2>&1 | ForEach-Object { "$_" }
