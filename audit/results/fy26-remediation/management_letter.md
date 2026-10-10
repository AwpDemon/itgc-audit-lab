# Management Letter - IT General Controls

**To:** Chief Financial Officer and Audit Committee, Kestrel Valve Co. *(fictional company - portfolio lab)*  
**Period:** 01 October 2025 to 30 September 2026  
**Evidence:** bundle `fy26-remediation` collected 2026-10-10T20:37:33+00:00 (SHA-256 manifest)  
**Date:** 10 October 2026

> This letter is generated from code over evidence pulled from a lab environment. The company, people and tickets are synthetic; the directory, database and repository evidence was collected live from the lab systems. Management responses are placeholders - in a real engagement they are obtained before issue.

## 1. Scope and approach

We tested the design and operating effectiveness of 15 IT general controls over Active Directory, the ERP application and database, and the ERP release pipeline, across three SOX ITGC domains: access to programs and data, program changes, and computer operations. Evidence was obtained directly from the systems with read-only accounts (LDAPS, PostgreSQL `pg_read_all_data`, git) and from management-provided documents. Where populations were machine-readable we tested 100% with data analytics; otherwise we selected random samples sized by control frequency and risk. Deviations found outside a sample were evaluated as well.

## 2. Summary

* **4 of 15** controls operated effectively; **11** were not effective.
* **5** deficiencies are classified as **significant deficiencies**; the rest are control deficiencies.
* **1** are flagged for material-weakness consideration by the engagement team (realised and pervasive; the final assessment needs the financial-statement context).

| # | Control | Finding | Classification |
|---|---|---|---|
| 1 | AC-02 | Terminated users retained access to Active Directory and the ERP | Significant deficiency |
| 2 | AC-03 | Privileged access and segregation-of-duties conflicts are not restricted to authorised personnel | Significant deficiency |
| 3 | CM-01 | Production changes were deployed without a ticket, approval or testing evidence | Significant deficiency |
| 4 | CM-02 | A developer deployed their own changes to production | Significant deficiency |
| 5 | CM-04 | A database schema change was applied directly in production outside the release process | Significant deficiency |
| 6 | AC-01 | New-hire and transfer access is not consistently approved, matched to the request, or cleaned up on transfer | Control deficiency |
| 7 | AC-04 | Quarterly user access reviews were late, not independent, or not followed through | Control deficiency |
| 8 | AC-05 | Domain password and lockout settings are weaker than ISS-04, and some accounts bypass the policy | Control deficiency |
| 9 | AC-07 | Service and generic accounts are not inventoried, owned, or prohibited as required | Control deficiency |
| 10 | OPS-01 | Backup failures were not always followed up | Control deficiency |
| 11 | OPS-02 | No restore test was performed during the year | Control deficiency |

**Aggregated deficiencies (by risk):**

* **R-APD-1** - Unauthorized users obtain access to financially significant systems and data. Controls not effective: AC-01, AC-07. **Significant deficiency.** 2 of 2 controls addressing this risk are not effective (AC-01, AC-07); no control addressing it is effective - risk unmitigated.
* **R-APD-2** - Authorized users obtain access beyond their job responsibilities (incl. SoD conflicts). Controls not effective: AC-01, AC-03, AC-04. **Significant deficiency.** 3 of 3 controls addressing this risk are not effective (AC-01, AC-03, AC-04); no control addressing it is effective - risk unmitigated.
* **R-APD-3** - Former employees or unused accounts retain access that can be misused. Controls not effective: AC-02, AC-04, AC-07. **Significant deficiency.** 3 of 4 controls addressing this risk are not effective (AC-02, AC-04, AC-07); remaining effective: AC-06.
* **R-PC-1** - Unauthorized or untested changes are implemented in production. Controls not effective: CM-01, CM-04. **Significant deficiency.** 2 of 3 controls addressing this risk are not effective (CM-01, CM-04); remaining effective: CM-03.
* **R-PC-2** - Developers make changes to production programs or data without independent review. Controls not effective: AC-03, CM-02, CM-04. **Significant deficiency.** 3 of 3 controls addressing this risk are not effective (AC-03, CM-02, CM-04); no control addressing it is effective - risk unmitigated.
* **R-CO-1** - Financial data cannot be recovered after loss or corruption. Controls not effective: OPS-01, OPS-02. **Significant deficiency.** 2 of 2 controls addressing this risk are not effective (OPS-01, OPS-02); no control addressing it is effective - risk unmitigated.

## 3. Findings

### 1. Terminated users retained access to Active Directory and the ERP

*Control AC-02 - Timely removal of access for terminated users (leaver) | Access to Programs and Data | Significant deficiency*

**Condition.** We tested 16 item(s) from a population of 16 (100% of population (data analytic)) and noted 2 exception(s):

- `leaver:klee` - failed attribute(s) D; termination_date: 2026-02-19, ad_enabled: False, erp_active: False, ticket: TRM-00004, completed: 2026-02-20T16:00:00, business_days: 1, last_logon: 2026-02-25T21:14:00+00:00
- `leaver:mchen` - failed attribute(s) C; termination_date: 2026-02-19, ad_enabled: False, erp_active: False, ticket: TRM-00005, completed: 2026-03-04T11:00:00, business_days: 9, last_logon: 2026-02-19T16:00:00+00:00

**Criteria.** Access of terminated employees to AD and the ERP is removed within one business day of termination. (ISS-04 logical_access.termination).

**Cause (likely - to be confirmed with management).** Termination tickets are closed on the HR side without confirming the AD account and the separate ERP user were disabled; there is no automated HR-to-AD reconciliation.

**Effect / risk.** Former employees or unused accounts retain access that can be misused. Risk realised in the evidence (failed attribute(s) D). Compensating control(s) AC-04 NOT effective - cannot be relied on.

**Recommendation.** Disable AD and ERP access automatically from the HR termination event (or same-day ticket with verification step); run a weekly HR-terminated vs. enabled-account reconciliation; investigate the post-termination logon for data access and notify the incident process.

**Framework references.** COBIT 2019 DSS05.04, DSS06.03; NIST SP 800-53 Rev. 5 AC-2, AC-2(3), PS-4; SOC 2 TSC CC6.2.

**Management response.** *[To be obtained from the control owner: action, owner, target date.]*

### 2. Privileged access and segregation-of-duties conflicts are not restricted to authorised personnel

*Control AC-03 - Privileged access and segregation of duties | Access to Programs and Data | Significant deficiency*

**Condition.** We tested 48 item(s) from a population of 48 (100% of population (data analytic)) and noted 1 exception(s):

- `Active Directory:svc_backup` - failed attribute(s) A; privileges: ['Backup Operators']

**Criteria.** Administrative access to AD, the ERP and its database is limited to authorized personnel, and no user holds conflicting ERP roles. (ISS-04 logical_access.privileged_access).

**Cause (likely - to be confirmed with management).** Privileged groups are granted for convenience (troubleshooting, backups) and never removed; the authorised list is not reconciled to the systems; the ERP has no preventive SoD rule set.

**Effect / risk.** Authorized users obtain access beyond their job responsibilities (incl. SoD conflicts). Developers make changes to production programs or data without independent review. Risk realised in the evidence (failed attribute(s) A). Pervasive: affects domain-wide settings or tier-0/database administration. Realised AND pervasive: escalate for material-weakness consideration (requires the financial-statement impact assessment, outside ITGC scope).

**Recommendation.** Remove the unauthorised Domain Admin, ERP_ADMIN and database SUPERUSER rights; give service accounts least privilege (Backup Operators / pg_read_all_data); implement a preventive SoD rule set in the ERP role-assignment workflow; reconcile privileged groups to the authorised list monthly.

**Framework references.** COBIT 2019 DSS05.04, DSS06.03, APO13.01; NIST SP 800-53 Rev. 5 AC-5, AC-6, AC-6(5); SOC 2 TSC CC6.1, CC6.3.

**Management response.** *[To be obtained from the control owner: action, owner, target date.]*

### 3. Production changes were deployed without a ticket, approval or testing evidence

*Control CM-01 - Change authorization and testing | Program Changes | Significant deficiency*

**Condition.** We tested 15 item(s) from a population of 32 (Random selection (seed 'FY2026:CM-01'), weekly band, high risk -> n=15) and noted 4 exception(s):

- `rel-2026-01-13` - failed attribute(s) A (found outside the sample); deployed_at: 2026-01-13T19:39:00, deployed_by: bscott, ticket: none
- `rel-2026-03-24` - failed attribute(s) A (found outside the sample); deployed_at: 2026-03-24T19:00:00, deployed_by: bscott, ticket: none
- `rel-2026-04-21` - failed attribute(s) B (found outside the sample); ticket: CHG-00016, type: Normal, approved_at: 2026-04-23T22:05:00, deployed_at: 2026-04-21T19:05:00, approver: dgarcia, developer: dadams, test_evidence: UAT sign-off attached; regression suite passed
- `rel-2026-09-17` - failed attribute(s) C (found outside the sample); ticket: CHG-00030, type: Normal, approved_at: 2026-09-14T17:48:00, deployed_at: 2026-09-17T19:48:00, approver: mwhite, developer: storres, test_evidence: (blank)

**Criteria.** Every production change has a change ticket, is tested (UAT), and is approved by the CAB before deployment. (ISS-04 change_management).

**Cause (likely - to be confirmed with management).** The pipeline does not check for an approved change ticket before deploying.

**Effect / risk.** Unauthorized or untested changes are implemented in production. Risk realised in the evidence (failed attribute(s) A, B).

**Recommendation.** Make the production deployment job require an approved change ID (pipeline gate) and attach UAT evidence to the ticket; report deployments without tickets monthly to the CAB.

**Framework references.** COBIT 2019 BAI06.01, BAI07.05; NIST SP 800-53 Rev. 5 CM-3, CM-3(2), CM-4; SOC 2 TSC CC8.1.

**Management response.** *[To be obtained from the control owner: action, owner, target date.]*

### 4. A developer deployed their own changes to production

*Control CM-02 - Segregation of duties - developers cannot deploy to production | Program Changes | Significant deficiency*

**Condition.** We tested 32 item(s) from a population of 32 (100% of population (data analytic)) and noted 3 exception(s):

- `rel-2025-11-25` - failed attribute(s) A, B; deployed_by: ahaddad, commit_authors: ['ahaddad'], deployed_at: 2025-11-25T19:21:00
- `rel-2026-06-16` - failed attribute(s) A, B; deployed_by: ahaddad, commit_authors: ['ahaddad'], deployed_at: 2026-06-16T19:50:00
- `rel-2026-08-18` - failed attribute(s) A, B; deployed_by: ahaddad, commit_authors: ['ahaddad'], deployed_at: 2026-08-18T19:24:00

**Criteria.** Production deployments are performed only by authorized deployers who did not author the change. (ISS-04 change_management.developer_may_not_deploy_own_change).

**Cause (likely - to be confirmed with management).** Pipeline permissions allow any Domain Admin to run the production job; the developer holds Domain Admin rights (see AC-03).

**Effect / risk.** Developers make changes to production programs or data without independent review. Risk realised in the evidence (failed attribute(s) B).

**Recommendation.** Restrict the production pipeline to PRD-Deployers and enforce 'author != deployer' in the pipeline; review the three self-deployed releases for unauthorised content.

**Framework references.** COBIT 2019 BAI06.01, DSS06.03; NIST SP 800-53 Rev. 5 CM-5, AC-5; SOC 2 TSC CC8.1, CC6.3.

**Management response.** *[To be obtained from the control owner: action, owner, target date.]*

### 5. A database schema change was applied directly in production outside the release process

*Control CM-04 - Database changes only through the release process | Program Changes | Significant deficiency*

**Condition.** We tested 11 item(s) from a population of 11 (100% of population (data analytic)) and noted 1 exception(s):

- `V012` - failed attribute(s) A, B; applied_at: 2026-05-14T22:41:07, applied_by: ahaddad

**Criteria.** Every schema change applied to the production ERP database was shipped in an approved release. (ISS-04 change_management.database_changes_via_release_only).

**Cause (likely - to be confirmed with management).** A developer holds database SUPERUSER (see AC-03) and applied a hotfix manually.

**Effect / risk.** Unauthorized or untested changes are implemented in production. Developers make changes to production programs or data without independent review. Risk realised in the evidence (failed attribute(s) A).

**Recommendation.** Remove developer superuser access; alert on schema_migrations rows not written by the pipeline account; retroactively review and approve or reverse the direct change.

**Framework references.** COBIT 2019 BAI06.01, BAI06.03; NIST SP 800-53 Rev. 5 CM-3, CM-5, CM-6; SOC 2 TSC CC8.1.

**Management response.** *[To be obtained from the control owner: action, owner, target date.]*

### 6. New-hire and transfer access is not consistently approved, matched to the request, or cleaned up on transfer

*Control AC-01 - User provisioning and transfers (joiner / mover) | Access to Programs and Data | Control deficiency*

**Condition.** We tested 16 item(s) from a population of 16 (100% of population (population below sampling threshold)) and noted 2 exception(s):

- `hire:mtaylor2` - failed attribute(s) B; hire_date: 2026-03-05, ad_created: 2026-03-03T11:14:00+00:00, ticket: AR-00006, approved_at: 2026-03-06T13:14:00, approver: prossi
- `hire:mbrown` - failed attribute(s) A; hire_date: 2026-07-20, ad_created: 2026-07-15T10:53:00+00:00

**Criteria.** Access is granted only after documented approval by the line manager and matches the approved request; prior access is removed on transfer. (ISS-04 logical_access.provisioning / transfers).

**Cause (likely - to be confirmed with management).** Access is fulfilled from verbal/e-mail requests when tickets lag; transfer tickets record removals but no one verifies AD after closure.

**Effect / risk.** Unauthorized users obtain access to financially significant systems and data. Authorized users obtain access beyond their job responsibilities (incl. SoD conflicts). No evidence the risk was realised (exposure only).

**Recommendation.** Block account creation in the provisioning workflow until manager approval is recorded; fulfil from the role baseline in the ticket only; add a post-fulfilment check that compares AD groups with the request and, for transfers, confirms prior-role groups were removed.

**Framework references.** COBIT 2019 DSS05.04, DSS06.03; NIST SP 800-53 Rev. 5 AC-2, PS-5; SOC 2 TSC CC6.2, CC6.3.

**Management response.** *[To be obtained from the control owner: action, owner, target date.]*

### 7. Quarterly user access reviews were late, not independent, or not followed through

*Control AC-04 - Quarterly user access review | Access to Programs and Data | Control deficiency*

**Condition.** We tested 4 item(s) from a population of 8 (Random selection (seed 'FY2026:AC-04:ERP'), quarterly band, high risk -> n=2 per system) and noted 2 exception(s):

- `FY26-Q3-ADPRIV` - failed attribute(s) B (found outside the sample); system: AD privileged groups, quarter_end: 2026-06-30, signed_off: 2026-07-15, days_after_qe: 15, reviewer: dgarcia, removals_requested: 0
- `FY26-Q2-ERP` - failed attribute(s) A (found outside the sample); system: ERP, quarter_end: 2026-03-31, signed_off: 2026-05-11, days_after_qe: 41, reviewer: agonzalez, removals_requested: 0

**Criteria.** Business owners review ERP and privileged AD access quarterly, within 30 days of quarter end; reviewers are independent of the access reviewed; removals are actioned. (ISS-04 logical_access.user_access_review).

**Cause (likely - to be confirmed with management).** Review evidence is tracked by e-mail; removals are ticketed but closure is not verified against the system; reviewer assignment does not exclude reviewers' own accounts.

**Effect / risk.** Authorized users obtain access beyond their job responsibilities (incl. SoD conflicts). Former employees or unused accounts retain access that can be misused. No evidence the risk was realised (exposure only).

**Recommendation.** Track review due dates in the GRC/ITSM tool with escalation at day 20; assign privileged-group reviews to someone who holds no privileged access; require system evidence (screenshot or export) before a removal ticket can be closed.

**Framework references.** COBIT 2019 DSS05.04, MEA02.01; NIST SP 800-53 Rev. 5 AC-2, AC-6(7); SOC 2 TSC CC6.2, CC6.3.

**Management response.** *[To be obtained from the control owner: action, owner, target date.]*

### 8. Domain password and lockout settings are weaker than ISS-04, and some accounts bypass the policy

*Control AC-05 - Password and account-lockout configuration | Access to Programs and Data | Control deficiency*

**Condition.** We tested 77 item(s) from a population of 77 (Test of one (automated setting) + 100% analytic) and noted 1 exception(s):

- `svc_scan` - failed attribute(s) A; kind: service, flags: ['DONT_EXPIRE_PASSWORD', 'NORMAL_ACCOUNT'], issue: DONT_EXPIRE_PASSWORD without approved exception

**Criteria.** Domain password and lockout settings meet ISS-04; no user account bypasses password expiry or the password requirement. (ISS-04 logical_access.password, logical_access.lockout).

**Cause (likely - to be confirmed with management).** The default domain policy was not updated when ISS-04 v3.1 was approved; account flags are set ad hoc by IT to stop help-desk calls.

**Effect / risk.** Weak authentication allows credentials to be guessed or brute-forced. No evidence the risk was realised (exposure only).

**Recommendation.** Set minimum length 12 and lockout threshold 5 in the default domain policy (or move to passphrases + MFA); clear DONT_EXPIRE_PASSWORD on user accounts and PASSWD_NOTREQD everywhere; monitor these flags with a scheduled LDAP query.

**Framework references.** COBIT 2019 DSS05.04; NIST SP 800-53 Rev. 5 IA-5, IA-5(1), AC-7; SOC 2 TSC CC6.1.

**Management response.** *[To be obtained from the control owner: action, owner, target date.]*

### 9. Service and generic accounts are not inventoried, owned, or prohibited as required

*Control AC-07 - Service and generic account management | Access to Programs and Data | Control deficiency*

**Condition.** We tested 4 item(s) from a population of 4 (100% of population (data analytic)) and noted 1 exception(s):

- `svc_scan` - failed attribute(s) A; description: Network scanner/copier SMTP relay

**Criteria.** Every service account is inventoried with an active owner; generic (shared) user accounts are not used. (ISS-04 logical_access.service_accounts / generic_accounts).

**Cause (likely - to be confirmed with management).** Service accounts are created by project teams without registering them; owners are not updated when people leave; a shared reception login was never replaced.

**Effect / risk.** Unauthorized users obtain access to financially significant systems and data. Former employees or unused accounts retain access that can be misused. No evidence the risk was realised (exposure only).

**Recommendation.** Register every service account with a current owner and review annually; move to group-managed service accounts where possible; replace the shared login with named accounts (or a kiosk mode without ERP access).

**Framework references.** COBIT 2019 DSS05.04; NIST SP 800-53 Rev. 5 AC-2, IA-2, IA-4; SOC 2 TSC CC6.1, CC6.2.

**Management response.** *[To be obtained from the control owner: action, owner, target date.]*

### 10. Backup failures were not always followed up

*Control OPS-01 - Backup monitoring and failure resolution | Computer Operations | Control deficiency*

**Condition.** We tested 9 item(s) from a population of 365 (100% of failed runs identified by analytic over the full job log) and noted 2 exception(s):

- `2026-01-28` - failed attribute(s) A; status: Failed, ticket: none, start: 2026-01-28T01:09:00
- `2026-06-26` - failed attribute(s) A; status: Failed, ticket: none, start: 2026-06-26T01:01:00

**Criteria.** Daily ERP database backups complete; failures are ticketed within one business day and resolved. (ISS-04 operations.backup).

**Cause (likely - to be confirmed with management).** Failure e-mails go to a shared mailbox without ticket automation.

**Effect / risk.** Financial data cannot be recovered after loss or corruption. No evidence the risk was realised (exposure only).

**Recommendation.** Create incidents automatically from backup-job failures; report consecutive failures to the IT Manager the same day.

**Framework references.** COBIT 2019 DSS04.07, DSS01.01; NIST SP 800-53 Rev. 5 CP-9; SOC 2 TSC A1.2, CC7.4.

**Management response.** *[To be obtained from the control owner: action, owner, target date.]*

### 11. No restore test was performed during the year

*Control OPS-02 - Periodic restore testing | Computer Operations | Control deficiency*

**Condition.** We tested 1 item(s) from a population of 0 (Annual control: 1 occurrence expected) and noted 1 exception(s):

- `management restore test (FY2026)` - failed attribute(s) A; tests_in_period: 0, most_recent_test: 2024-11-14

**Criteria.** Backups are restored at least annually to prove they are usable. (ISS-04 operations.restore_test).

**Cause (likely - to be confirmed with management).** Restore testing is not scheduled or owned.

**Effect / risk.** Financial data cannot be recovered after loss or corruption. No evidence the risk was realised (exposure only).

**Recommendation.** Schedule an annual (preferably quarterly) restore test with documented validation (row counts / checksums) and measured restore time against the RTO.

**Framework references.** COBIT 2019 DSS04.04, DSS04.07; NIST SP 800-53 Rev. 5 CP-9(1), CP-10; SOC 2 TSC A1.3.

**Management response.** *[To be obtained from the control owner: action, owner, target date.]*

## 4. Controls operating effectively

* AC-06 - Dormant account management
* CM-03 - Emergency change approval
* OPS-03 - Batch job monitoring (ERP to GL interface)
* OPS-04 - Incident management - P1 root-cause analysis

## 5. Other observations

* OPS-01: Observation: 2 consecutive failed nights 2025-11-16 to 2025-11-17 - recovery point exposure of 3 days.
* OPS-01: Observation: 3 consecutive failed nights 2026-06-03 to 2026-06-05 - recovery point exposure of 4 days.
* OPS-02: Auditor re-performance proves the backup mechanism works today; it does NOT cure the control failure (management did not perform the control during the period).
* AC-05: Scope limitation: No PSOs returned: none exist OR the read-only audit account lacks rights to read them (default AD ACLs restrict PSOs to Domain Admins). Request a DA-run export if relevant.

---
*Prepared by Ali Askari as a portfolio lab engagement. Not an audit opinion.*
