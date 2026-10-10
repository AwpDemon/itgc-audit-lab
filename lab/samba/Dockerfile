# Samba 4 Active Directory Domain Controller for the ITGC audit lab.
# Built from Debian's packaged Samba so every step is inspectable (no third-party DC image).
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      samba samba-ad-dc samba-ad-provision samba-dsdb-modules samba-vfs-modules \
      winbind krb5-user ldb-tools ldap-utils python3-ldb tdb-tools ca-certificates procps \
 && rm -rf /var/lib/apt/lists/* \
 && rm -f /etc/samba/smb.conf

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# 389 LDAP, 636 LDAPS, 88 Kerberos (only LDAP/LDAPS are published by compose)
EXPOSE 389 636 88
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
