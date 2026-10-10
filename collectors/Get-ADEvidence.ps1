<#
.SYNOPSIS
  Collect Active Directory user-lifecycle evidence with PowerShell only (no RSAT module needed).

.DESCRIPTION
  Uses System.DirectoryServices.Protocols over LDAP with Negotiate authentication and
  signing + sealing (encrypted), so it works from a non-domain-joined auditor laptop against
  Windows Server AD *and* against the Samba AD DC in this lab. Produces the same schema as the
  Python collector (src/itgc/collect/ad.py) so both can feed the same control tests;
  tests/test_powershell_parity.py compares the two outputs.

  On a domain-joined machine with RSAT you would typically use:
    Get-ADUser -Filter * -Properties lastLogonTimestamp,whenCreated,userAccountControl,memberOf,employeeID
  This script avoids that dependency (RSAT needs AD Web Services, which Samba does not provide).

.EXAMPLE
  .\Get-ADEvidence.ps1 -Server 127.0.0.1 -Port 1389 -BaseDN 'DC=kestrel,DC=lab,DC=test' `
      -User 'svc_audit_ro@kestrel.lab.test' -OutFile .\ad_users_ps.json
#>
[CmdletBinding()]
param(
    [string]$Server = '127.0.0.1',
    [int]$Port = 1389,
    [Parameter(Mandatory)][string]$BaseDN,
    [Parameter(Mandatory)][string]$User,
    [string]$Password = $env:ITGC_LDAP_PASSWORD,
    [string]$OutFile = 'ad_users_ps.json'
)
Add-Type -AssemblyName System.DirectoryServices.Protocols
$ErrorActionPreference = 'Stop'

$flags = @{
    0x0002 = 'ACCOUNTDISABLE'; 0x0010 = 'LOCKOUT'; 0x0020 = 'PASSWD_NOTREQD'; 0x0040 = 'PASSWD_CANT_CHANGE'
    0x0080 = 'ENCRYPTED_TEXT_PWD_ALLOWED'; 0x0200 = 'NORMAL_ACCOUNT'; 0x0800 = 'INTERDOMAIN_TRUST_ACCOUNT'
    0x1000 = 'WORKSTATION_TRUST_ACCOUNT'; 0x2000 = 'SERVER_TRUST_ACCOUNT'; 0x10000 = 'DONT_EXPIRE_PASSWORD'
    0x40000 = 'SMARTCARD_REQUIRED'; 0x80000 = 'TRUSTED_FOR_DELEGATION'; 0x100000 = 'NOT_DELEGATED'
    0x200000 = 'USE_DES_KEY_ONLY'; 0x400000 = 'DONT_REQ_PREAUTH'; 0x800000 = 'PASSWORD_EXPIRED'
    0x1000000 = 'TRUSTED_TO_AUTH_FOR_DELEGATION'
}

function Attr($entry, [string]$name) {
    # attribute names come back in server case (Samba: lower case) - match case-insensitively
    foreach ($k in $entry.Attributes.AttributeNames) { if ($k -ieq $name) { return ,$entry.Attributes[$k] } }
    return $null
}
function First($entry, [string]$name) {
    $a = Attr $entry $name
    if ($a -and $a.Count -gt 0) { return [string]$a[0] }
    return $null
}
function FromFileTime([string]$v) {
    if (-not $v -or $v -eq '0' -or [int64]$v -ge [int64]::MaxValue) { return $null }
    return [DateTime]::FromFileTimeUtc([int64]$v).ToString('yyyy-MM-ddTHH:mm:ss+00:00')
}
function CnOf([string]$dn) { return ($dn -split ',', 2)[0] -replace '^[^=]+=', '' }

$id = New-Object System.DirectoryServices.Protocols.LdapDirectoryIdentifier($Server, $Port)
$cred = New-Object System.Net.NetworkCredential($User, $Password)
$conn = New-Object System.DirectoryServices.Protocols.LdapConnection($id, $cred, [System.DirectoryServices.Protocols.AuthType]::Negotiate)
$conn.SessionOptions.ProtocolVersion = 3
$conn.SessionOptions.Signing = $true
$conn.SessionOptions.Sealing = $true
$conn.SessionOptions.ReferralChasing = [System.DirectoryServices.Protocols.ReferralChasingOptions]::None
$conn.Bind()

$attrs = 'sAMAccountName', 'displayName', 'employeeID', 'department', 'title', 'manager', 'description',
         'userAccountControl', 'whenCreated', 'lastLogonTimestamp', 'pwdLastSet', 'memberOf'
$req = New-Object System.DirectoryServices.Protocols.SearchRequest($BaseDN, '(&(objectCategory=person)(objectClass=user))',
       [System.DirectoryServices.Protocols.SearchScope]::Subtree, [string[]]$attrs)
$page = New-Object System.DirectoryServices.Protocols.PageResultRequestControl(500)
[void]$req.Controls.Add($page)

$users = New-Object System.Collections.Generic.List[object]
do {
    $resp = [System.DirectoryServices.Protocols.SearchResponse]$conn.SendRequest($req)
    foreach ($e in $resp.Entries) {
        $uac = [int](First $e 'userAccountControl')
        $dn = $e.DistinguishedName
        $wc = First $e 'whenCreated'
        $memberOf = @()
        $mo = Attr $e 'memberOf'
        if ($mo) { $memberOf = @($mo.GetValues([string]) | ForEach-Object { CnOf $_ } | Sort-Object) }
        $mgr = First $e 'manager'
        $users.Add([ordered]@{
            sam                  = First $e 'sAMAccountName'
            dn                   = $dn
            ou                   = (($dn -split ',') | Select-Object -Skip 1 | Where-Object { $_ -like 'OU=*' }) -join ','
            display_name         = First $e 'displayName'
            employee_id          = First $e 'employeeID'
            department           = First $e 'department'
            title                = First $e 'title'
            manager              = if ($mgr) { CnOf $mgr } else { $null }
            description          = First $e 'description'
            uac                  = $uac
            uac_flags            = @($flags.Keys | Sort-Object | Where-Object { $uac -band $_ } | ForEach-Object { $flags[$_] })
            enabled              = -not ($uac -band 2)
            when_created         = if ($wc) { [DateTime]::ParseExact($wc.Substring(0, 14), 'yyyyMMddHHmmss', $null).ToString('yyyy-MM-ddTHH:mm:ss+00:00') } else { $null }
            last_logon_timestamp = FromFileTime (First $e 'lastLogonTimestamp')
            member_of            = $memberOf
        })
    }
    $cookie = ($resp.Controls | Where-Object { $_ -is [System.DirectoryServices.Protocols.PageResultResponseControl] }).Cookie
    $page.Cookie = $cookie
} while ($cookie -and $cookie.Length -gt 0)
$conn.Dispose()

$sorted = $users | Sort-Object { ([string]$_['sam']).ToLower() }
$json = ConvertTo-Json -InputObject @($sorted) -Depth 4
[System.IO.File]::WriteAllText((Join-Path (Get-Location) $OutFile), $json, (New-Object System.Text.UTF8Encoding($false)))
Write-Output "collected $($users.Count) user objects -> $OutFile"
