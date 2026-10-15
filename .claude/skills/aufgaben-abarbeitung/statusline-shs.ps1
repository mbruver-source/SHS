$ErrorActionPreference = 'Stop'
$out = 'Claude'
try {
    $raw = [Console]::In.ReadToEnd()
    $d = $raw | ConvertFrom-Json
    if ($d.model -and $d.model.display_name) { $out = [string]$d.model.display_name }
    $ts = (Get-Date).ToString('s')
    $file = (Join-Path $env:USERPROFILE '.claude\shs-limit.json')
    try {
        if (($d.PSObject.Properties.Name -contains 'rate_limits') -and $null -ne $d.rate_limits) {
            $obj = [ordered]@{ rate_limits = $d.rate_limits; geschrieben = $ts }
        } else {
            $obj = [ordered]@{ rate_limits = $null; geschrieben = $ts; eingabe_schluessel = @($d.PSObject.Properties.Name) }
        }
        $json = $obj | ConvertTo-Json -Depth 10
        [System.IO.File]::WriteAllText($file, $json, (New-Object System.Text.UTF8Encoding($false)))
    } catch { }
    try {
        $rl = $d.rate_limits
        if ($rl) {
            $parts = @()
            if ($rl.five_hour -and $null -ne $rl.five_hour.used_percentage) {
                $parts += ('5h: {0:N0} %' -f [double]$rl.five_hour.used_percentage)
            }
            if ($rl.seven_day -and $null -ne $rl.seven_day.used_percentage) {
                $parts += ('7T: {0:N0} %' -f [double]$rl.seven_day.used_percentage)
            }
            if ($parts.Count -gt 0) { $out = $out + ' | ' + ($parts -join ' | ') }
        }
    } catch { }
} catch { }
Write-Output $out
