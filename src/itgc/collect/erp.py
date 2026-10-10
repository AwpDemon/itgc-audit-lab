"""Collect ERP application + database evidence with a read-only PostgreSQL login (psycopg 3)."""
from __future__ import annotations

QUERIES = {
    "erp_users.json": """
        select u.username, u.full_name, u.employee_id, u.is_active,
               u.created_at, u.deactivated_at, u.last_login_at,
               coalesce(array_agg(r.role order by r.role) filter (where r.role is not null), '{}') as roles
          from app.users u left join app.user_roles r using (username)
         group by u.username order by u.username""",
    "db_roles.json": """
        select r.rolname as role, r.rolsuper as superuser, r.rolcanlogin as can_login,
               r.rolcreaterole as create_role, r.rolcreatedb as create_db, r.rolbypassrls as bypass_rls,
               shobj_description(r.oid, 'pg_authid') as comment,
               coalesce((select array_agg(g.rolname order by g.rolname) from pg_auth_members m
                          join pg_roles g on g.oid = m.roleid where m.member = r.oid), '{}') as member_of
          from pg_roles r where r.rolname !~ '^pg_' order by r.rolname""",
    "schema_migrations.json": "select version, applied_at, applied_by from public.schema_migrations order by version",
}


def _jsonable(v):
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def collect(dsn: str) -> dict[str, object]:
    import psycopg
    from psycopg.rows import dict_row

    out: dict[str, object] = {}
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        conn.read_only = True
        for name, sql in QUERIES.items():
            rows = conn.execute(sql).fetchall()
            out[name] = [{k: _jsonable(v) for k, v in r.items()} for r in rows]
        out["erp_db_info.json"] = conn.execute(
            "select current_user as audit_login, version() as server_version, now() as collected_at").fetchone()
        out["erp_db_info.json"] = {k: _jsonable(v) for k, v in out["erp_db_info.json"].items()}
    return out
