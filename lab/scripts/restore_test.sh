#!/usr/bin/env bash
# Re-performance of the backup/restore control: back up the ERP database, restore it into a
# scratch database, and prove the restore is complete and accurate (row counts + content hash
# per table). Prints one JSON document; timings are wall-clock seconds measured here.
set -euo pipefail
DB=${1:-erp}; SCRATCH=${DB}_restore_test; DUMP=/tmp/${DB}.dump
export PGUSER=${PGUSER:-erp_owner}
now() { date +%s.%N; }
t0=$(now); pg_dump -Fc -d "$DB" -f "$DUMP"; t1=$(now)
dropdb --if-exists "$SCRATCH" 2>/dev/null; createdb "$SCRATCH"
pg_restore -d "$SCRATCH" "$DUMP"; t2=$(now)
tables=$(psql -d "$DB" -At -c "select schemaname||'.'||tablename from pg_tables where schemaname in ('app','public') order by 1")
json_tables=""
mismatch=0
for t in $tables; do
  q="select count(*)||':'||coalesce(md5(string_agg(x::text, '|' order by x::text)),'') from $t x"
  a=$(psql -d "$DB" -At -c "$q"); b=$(psql -d "$SCRATCH" -At -c "$q")
  [ "$a" = "$b" ] && ok=true || { ok=false; mismatch=$((mismatch+1)); }
  json_tables="$json_tables{\"table\":\"$t\",\"source_rows\":${a%%:*},\"restored_rows\":${b%%:*},\"source_md5\":\"${a#*:}\",\"restored_md5\":\"${b#*:}\",\"match\":$ok},"
done
t3=$(now)
size=$(stat -c %s "$DUMP")
dropdb "$SCRATCH"; rm -f "$DUMP"
printf '{"database":"%s","backup_seconds":%.2f,"restore_seconds":%.2f,"validation_seconds":%.2f,"total_seconds":%.2f,"dump_bytes":%s,"tables_mismatched":%s,"tables":[%s],"pg_version":"%s","performed_at":"%s"}\n' \
  "$DB" "$(awk "BEGIN{print $t1-$t0}")" "$(awk "BEGIN{print $t2-$t1}")" "$(awk "BEGIN{print $t3-$t2}")" "$(awk "BEGIN{print $t3-$t0}")" \
  "$size" "$mismatch" "${json_tables%,}" "$(psql -d "$DB" -At -c 'show server_version')" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
