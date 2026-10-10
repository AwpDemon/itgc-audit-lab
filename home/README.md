# Applying it at home: ITGC thinking for a self-hosted homelab

I run a small self-hosted environment (containers behind an outbound-only tunnel, a single
sign-on proxy, scheduled database dumps and an uptime monitor). After building the lab audit I
pointed the same control objectives at my own setup, **read-only**, with
`src/itgc/home/selfcheck.py`.

**What is deliberately not in this repository:** hostnames, IP addresses, domains, service
URLs, software versions, and any finding about my own network. Real output goes to
`home/private/` (git-ignored), and anything worth fixing went into a private to-do list.
The tests (`tests/test_home_selfcheck.py`) run on fictional `example.test` fixtures.

## Control objectives translated to a homelab

| # | Objective (ITGC domain) | Corporate equivalent | How the check gathers evidence (read-only) |
|---|---|---|---|
| H1 | Internet-facing apps sit behind central SSO (access) | AC-03 / AC-05 | Parse the tunnel's ingress rules; an origin that is the SSO proxy passes, an allow-listed app with its own login is "review", anything else is an exception |
| H2 | Services are not exposed on more interfaces than needed (access) | network segmentation | `docker ps` port bindings: `0.0.0.0` / `::` vs. loopback |
| H3 | Backups run on schedule and success is evidenced (operations) | OPS-01 | Age of the newest backup set + error lines in the backup log tail |
| H4 | Every internet-facing service is monitored (operations) | OPS-03 / OPS-04 | Uptime-monitor database (opened read-only) matched to each published hostname or its origin port |
| H5 | Software is kept current (change) | patch management | Image build dates older than a threshold |
| H6 | Secrets are not stored in plain text in configuration (change / access) | secrets management | Compose files scanned for inline `PASSWORD` / `TOKEN` / `SECRET` values; values are never printed |

## What the exercise taught me (generic)

* **"No inbound ports" is not the same as "no exposure."** An outbound tunnel removes port
  forwarding, but every hostname it publishes is still on the internet. The useful control is
  an *inventory of published hostnames with a stated authentication owner for each*, reviewed
  like a privileged-access list.
* **Machine-to-machine endpoints are the gap SSO does not cover.** Webhooks and APIs cannot sit
  behind an interactive login, so they need their own authentication (tokens, signatures) and
  should be on an explicit allow-list rather than an implicit one.
* **Monitoring the origin is not monitoring the service.** Checks that hit the container directly
  stay green when the public path is broken; at least one check per hostname should go through
  the edge.
* **Stale monitors and stale configuration are change-management findings,** not just noise:
  they show decommissioning does not have a checklist.
* **A backup you have not restored is a hope, not a control** (same lesson as OPS-02 in the lab).
* **One-person environments cannot segregate duties.** The honest compensating control is
  detective: change history in git and a periodic review of what is published.

## Run it on your own setup

```bash
python -m itgc.home.selfcheck \
  --tunnel-config /path/to/tunnel/config.yml --sso-origin 127.0.0.1:9000 \
  --docker-cmd docker --backup-dir /path/to/backups \
  --kuma-db /path/to/kuma.db --compose-root /path/to/stacks
# writes home/private/selfcheck.json (git-ignored)
```
