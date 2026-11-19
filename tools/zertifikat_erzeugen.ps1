<#
.SYNOPSIS
    Erzeugt EINMALIG das selbst signierte TLS-Zertifikat fuer den HTTPS-Proxy der Web-Version
    und gibt den SHA-256-Fingerabdruck aus.

.DESCRIPTION
    Der Proxy (Caddy, siehe compose.yaml und Caddyfile) liest Zertifikat und privaten
    Schluessel aus secrets\tls\. Das Zertifikat ist 10 Jahre gueltig und gilt fuer localhost,
    127.0.0.1, ::1 und den Rechnernamen (weitere Namen/IP-Adressen ueber -Namen). Es wird
    nur einmal erzeugt und danach nie automatisch erneuert, damit der Fingerabdruck stabil
    bleibt: das Desktop-Programm merkt sich ihn (Zertifikats-Pinning) und vertraut nur
    diesem Zertifikat.

    Ein vorhandenes Zertifikat wird NICHT ueberschrieben (nur der Fingerabdruck wird erneut
    angezeigt). Mit -Erneuern wird bewusst ein neues erzeugt - danach muss der Fingerabdruck
    im Desktop-Programm neu bestaetigt werden.

    Der private Schluessel (secrets\tls\schluessel.pem) gehoert nie ins Repo (secrets\ steht in
    .gitignore) und wird nicht weitergegeben. Weitergegeben wird nur der Fingerabdruck.

    Benoetigt "openssl" (z. B. das von Git fuer Windows mitgelieferte, wird automatisch
    gefunden). Ohne openssl wird ein kurzlebiger Container (podman oder docker) mit dem Image
    alpine/openssl verwendet.

.PARAMETER Namen
    Zusaetzliche DNS-Namen oder IP-Adressen im Zertifikat, z. B. die IP des Rechners im
    Vereinsnetz: -Namen 192.168.1.20,pruefung-pc

.PARAMETER Ausgabe
    Zielordner (Standard: secrets\tls im Projektordner).

.PARAMETER Erneuern
    Ein vorhandenes Zertifikat ersetzen.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools\zertifikat_erzeugen.ps1
#>
param(
    [string[]]$Namen = @(),
    [string]$Ausgabe = (Join-Path (Split-Path -Parent $PSScriptRoot) 'secrets\tls'),
    [switch]$Erneuern
)

$ErrorActionPreference = 'Stop'
$Tage = 3650
$zertifikat = Join-Path $Ausgabe 'zertifikat.pem'
$schluessel = Join-Path $Ausgabe 'schluessel.pem'

function Get-Fingerabdruck([string]$pemPfad) {
    # SHA-256 ueber die DER-Bytes des Zertifikats (der Base64-Teil der PEM-Datei).
    $text = Get-Content -LiteralPath $pemPfad -Raw
    $base64 = ($text -replace '-----BEGIN CERTIFICATE-----', '' -replace '-----END CERTIFICATE-----', '' -replace '\s', '')
    $der = [Convert]::FromBase64String($base64)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { $hash = $sha.ComputeHash($der) } finally { $sha.Dispose() }
    return (($hash | ForEach-Object { $_.ToString('X2') }) -join ':')
}

function Find-Openssl {
    $befehl = Get-Command openssl -ErrorAction SilentlyContinue
    if ($befehl) { return $befehl.Source }
    foreach ($kandidat in @(
        "$env:ProgramFiles\Git\usr\bin\openssl.exe",
        "$env:ProgramFiles\Git\mingw64\bin\openssl.exe",
        "${env:ProgramFiles(x86)}\Git\usr\bin\openssl.exe"
    )) {
        if ($kandidat -and (Test-Path -LiteralPath $kandidat)) { return $kandidat }
    }
    return $null
}

function Zeige-Fingerabdruck([string]$pemPfad) {
    $fp = Get-Fingerabdruck $pemPfad
    Set-Content -LiteralPath (Join-Path $Ausgabe 'fingerabdruck.txt') -Value $fp -Encoding ascii
    Write-Host ''
    Write-Host 'SHA-256-Fingerabdruck des Zertifikats (notieren, im Desktop-Programm abgleichen):'
    Write-Host "  $fp"
    Write-Host ''
    Write-Host "Zertifikat: $pemPfad"
    Write-Host "Auch gespeichert in: $(Join-Path $Ausgabe 'fingerabdruck.txt')"
}

if ((Test-Path -LiteralPath $zertifikat) -and -not $Erneuern) {
    Write-Host 'Es gibt bereits ein Zertifikat - es wird NICHT ueberschrieben (mit -Erneuern ersetzen).'
    Zeige-Fingerabdruck $zertifikat
    exit 0
}

New-Item -ItemType Directory -Force -Path $Ausgabe | Out-Null

# Namen im Zertifikat (subjectAltName)
$san = New-Object System.Collections.Generic.List[string]
foreach ($eintrag in @('localhost', '127.0.0.1', '::1', $env:COMPUTERNAME) + $Namen) {
    if (-not $eintrag) { continue }
    $art = if ($eintrag -match '^[0-9.]+$' -or $eintrag.Contains(':')) { 'IP' } else { 'DNS' }
    $wert = "${art}:$eintrag"
    if (-not $san.Contains($wert)) { $san.Add($wert) }
}
$sanText = $san -join ','

$gemeinsam = @(
    'req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:prime256v1', '-nodes',
    '-days', "$Tage", '-subj', '/CN=localhost',
    '-addext', "subjectAltName=$sanText",
    '-addext', 'basicConstraints=critical,CA:FALSE',
    '-addext', 'keyUsage=critical,digitalSignature',
    '-addext', 'extendedKeyUsage=serverAuth'
)

$openssl = Find-Openssl
if ($openssl) {
    Write-Host "Verwende openssl: $openssl"
    & $openssl @gemeinsam '-keyout' $schluessel '-out' $zertifikat
    if ($LASTEXITCODE -ne 0) { throw "openssl ist mit Fehlercode $LASTEXITCODE beendet worden." }
} else {
    $cli = $null
    foreach ($name in @('podman', 'docker')) {
        if (Get-Command $name -ErrorAction SilentlyContinue) { $cli = $name; break }
    }
    if (-not $cli) {
        throw 'Weder openssl noch podman/docker gefunden. openssl installieren (z. B. Git fuer Windows) und erneut starten.'
    }
    Write-Host "openssl nicht gefunden - verwende einen kurzlebigen Container ($cli, Image alpine/openssl)."
    $ordner = (Resolve-Path -LiteralPath $Ausgabe).Path
    & $cli run --rm -v "${ordner}:/out" docker.io/alpine/openssl:3.5.9@sha256:c92fcbb1da06f6e22bf842833e4713df02a382116d8a40312546b599ec19ca30 @gemeinsam '-keyout' '/out/schluessel.pem' '-out' '/out/zertifikat.pem'
    if ($LASTEXITCODE -ne 0) { throw "Der Container ist mit Fehlercode $LASTEXITCODE beendet worden." }
}

if (-not (Test-Path -LiteralPath $zertifikat) -or -not (Test-Path -LiteralPath $schluessel)) {
    throw 'Zertifikat oder Schluessel wurde nicht erzeugt.'
}

$ablauf = (Get-Date).AddDays($Tage).ToString('dd.MM.yyyy')
Write-Host "Zertifikat erzeugt (gueltig $Tage Tage, bis etwa $ablauf, Namen: $sanText)."
Write-Host "Hinweis: Nach Ablauf warnt der Browser; das Desktop-Programm prueft nur den Fingerabdruck. Vor $ablauf mit -Erneuern ein neues erzeugen (danach Fingerabdruck im Desktop neu bestaetigen)."
Write-Host "Privater Schluessel: $schluessel - nicht weitergeben, nicht ins Repo."
Zeige-Fingerabdruck $zertifikat
Write-Host ''
Write-Host 'Naechste Schritte: podman-compose up -d, dann https://localhost:5443 im Browser oeffnen'
Write-Host '(einmalige Warnung wegen des selbst signierten Zertifikats bestaetigen).'
