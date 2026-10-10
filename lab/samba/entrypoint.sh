#!/bin/bash
# Provision the domain on first start, then run the DC in the foreground.
set -euo pipefail

REALM="${SAMBA_REALM:?SAMBA_REALM required}"
DOMAIN="${SAMBA_DOMAIN:?SAMBA_DOMAIN required}"
ADMIN_PASS="${SAMBA_ADMIN_PASS:?SAMBA_ADMIN_PASS required}"

if [ ! -f /var/lib/samba/private/sam.ldb ]; then
  echo "[entrypoint] provisioning ${REALM}"
  rm -f /etc/samba/smb.conf
  samba-tool domain provision \
    --realm="${REALM}" --domain="${DOMAIN}" \
    --server-role=dc --dns-backend=SAMBA_INTERNAL \
    --adminpass="${ADMIN_PASS}" --use-rfc2307 \
    --option="dns forwarder = 127.0.0.11" \
    --option="tls enabled = yes"
  cp /var/lib/samba/private/krb5.conf /etc/krb5.conf
fi

exec samba -i --debug-stdout
