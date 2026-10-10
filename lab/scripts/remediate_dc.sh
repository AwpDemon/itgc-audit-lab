#!/usr/bin/env bash
# Management's remediation of the configuration/access findings (run inside the DC container).
# Historical process failures (missing tickets, late reviews, self-deployments) cannot be fixed
# retroactively - the re-test shows which findings remediation can and cannot close.
set -euo pipefail
st() { samba-tool "$@" >/dev/null; echo "ok: samba-tool $*"; }
H=/var/lib/samba/private/sam.ldb
uac() {  # uac <sam> <value>
  dn=$(ldbsearch -H $H "(sAMAccountName=$1)" dn | sed -n 's/^dn: //p')
  printf 'dn: %s\nchangetype: modify\nreplace: userAccountControl\nuserAccountControl: %s\n' "$dn" "$2" | ldbmodify -H $H >/dev/null
  echo "ok: userAccountControl $1=$2"
}
# AC-05 domain policy to ISS-04
st domain passwordsettings set --min-pwd-length=12 --account-lockout-threshold=5
# AC-02 / AC-06 / AC-07: disable leavers still enabled, dormant accounts, generic and orphaned accounts
for u in klee ethomas gmensah rnovak lbaker svc_legacyftp frontdesk; do st user disable "$u"; done
# AC-03: remove unauthorised Domain Admins
st group removemembers "Domain Admins" ahaddad,svc_backup
# AC-01 / AC-04: remove excess and review-flagged access
st group removemembers APP-ERP-GL-Poster bnguyen
st group removemembers APP-ERP-GL-Approver cadams
st group removemembers APP-ERP-AP-Approver amartinez
# AC-05: clear DONT_EXPIRE_PASSWORD / PASSWD_NOTREQD on user accounts (512 = NORMAL_ACCOUNT)
for u in pjohnson jallen mmoore; do uac "$u" 512; done
