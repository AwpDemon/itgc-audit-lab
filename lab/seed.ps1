# Windows/PowerShell equivalent of seed.sh: seed the running lab from lab/.build/.
Set-Location $PSScriptRoot
function Run([string[]]$cmd) {
    & docker @cmd 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw "docker $($cmd -join ' ') failed ($LASTEXITCODE)" }
}
do { Start-Sleep 3; docker compose exec -T dc sh -c "ldapsearch -x -H ldap://127.0.0.1 -s base -b '' namingContexts" 2>&1 | Out-Null } until ($LASTEXITCODE -eq 0)
Run compose, cp, .build/ad_spec.json, dc:/tmp/ad_spec.json
Run compose, cp, seed/seed_dc.py, dc:/tmp/seed_dc.py
Run compose, exec, -T, dc, python3, /tmp/seed_dc.py, /tmp/ad_spec.json
Run compose, exec, -T, dc, rm, -f, /tmp/ad_spec.json
Run compose, cp, .build/erp_seed.sql, erpdb:/tmp/erp_seed.sql
do { Start-Sleep 2; docker compose exec -T erpdb pg_isready -U erp_owner -d erp 2>&1 | Out-Null } until ($LASTEXITCODE -eq 0)
Run compose, exec, -T, erpdb, psql, -v, ON_ERROR_STOP=1, -U, erp_owner, -d, erp, -q, -f, /tmp/erp_seed.sql
Write-Output 'lab seeded'
