| Control | Name | Approach | N | Tested | Exceptions (sample) | Exceptions (final) | Conclusion | Classification |
|---|---|---|---:|---:|---:|---:|---|---|
| AC-01 | User provisioning and transfers (joiner / mover) | analytic | 16 | 16 | 4 | 4 | Not effective | Significant deficiency |
| AC-02 | Timely removal of access for terminated users (leaver) | analytic | 16 | 16 | 4 | 4 | Not effective | Significant deficiency |
| AC-03 | Privileged access and segregation of duties | analytic | 54 | 54 | 5 | 5 | Not effective | Significant deficiency |
| AC-04 | Quarterly user access review | sample | 8 | 4 | 1 | 3 | Not effective | Significant deficiency |
| AC-05 | Password and account-lockout configuration | analytic | 84 | 84 | 7 | 7 | Not effective | Significant deficiency |
| AC-06 | Dormant account management | analytic | 76 | 76 | 6 | 6 | Not effective | Control deficiency |
| AC-07 | Service and generic account management | analytic | 6 | 6 | 3 | 3 | Not effective | Control deficiency |
| CM-01 | Change authorization and testing | sample | 32 | 15 | 0 | 4 | Not effective | Significant deficiency |
| CM-02 | Segregation of duties - developers cannot deploy to production | analytic | 32 | 32 | 3 | 3 | Not effective | Significant deficiency |
| CM-03 | Emergency change approval | sample | 4 | 2 | 0 | 0 | Effective | - |
| CM-04 | Database changes only through the release process | analytic | 11 | 11 | 1 | 1 | Not effective | Significant deficiency |
| OPS-01 | Backup monitoring and failure resolution | analytic | 365 | 9 | 2 | 2 | Not effective | Control deficiency |
| OPS-02 | Periodic restore testing | sample | 0 | 1 | 1 | 1 | Not effective | Control deficiency |
| OPS-03 | Batch job monitoring (ERP to GL interface) | analytic | 261 | 6 | 0 | 0 | Effective | - |
| OPS-04 | Incident management - P1 root-cause analysis | sample | 3 | 2 | 0 | 0 | Effective | - |

Planted issues detected: 39/39 (sample-only approach on sampled controls: 2/8; with full-population analytics: 8/8).

Exceptions not in the answer key:

* AC-05 `frontdesk` - knock-on of a planted issue (same entity planted under another control)
* AC-05 `svc_scan` - knock-on of a planted issue (same entity planted under another control)
* AC-06 `ethomas` - knock-on of a planted issue (same entity planted under another control)
* AC-06 `klee` - knock-on of a planted issue (same entity planted under another control)
