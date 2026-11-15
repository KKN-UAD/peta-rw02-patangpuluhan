# Kirim hasil edit QGIS ke GitHub, tunggu peta online ter-update, lalu download banner PDF.
# Dijalankan lewat kirim_update.bat (klik 2x). Butuh file token.txt di folder yang sama.
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$REPO = "KKN-UAD/peta-rw02-patangpuluhan"
$API = "https://api.github.com/repos/$REPO"
$DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

function Selesai($pesan) { Write-Host ""; Write-Host $pesan; Read-Host "tekan enter buat nutup"; exit }

$tokFile = Join-Path $DIR "token.txt"
if ($env:PETA_TOKEN) { $TOKEN = $env:PETA_TOKEN }
elseif (Test-Path $tokFile) { $TOKEN = (Get-Content $tokFile -Raw).Trim() }
else { Selesai "file token.txt belum ada di folder qgis. minta ke admin repo ya." }
$H = @{ Authorization = "Bearer $TOKEN"; "User-Agent" = "peta-rw02-update"; Accept = "application/vnd.github+json" }

if (Get-Process -Name "qgis*" -ErrorAction SilentlyContinue) { Selesai "qgis masih kebuka. tutup qgis dulu biar editannya kesimpen, terus klik lagi file ini." }
if (Test-Path (Join-Path $DIR "peta_rw02.gpkg-wal")) { Selesai "editan belum kesimpen penuh (ada file peta_rw02.gpkg-wal). buka qgis, save, tutup lagi, terus klik lagi file ini." }

function GitSha([byte[]]$b) {   # sha file versi git, buat cek file berubah atau nggak
    $head = [Text.Encoding]::ASCII.GetBytes("blob $($b.Length)`0")
    $sha = [Security.Cryptography.SHA1]::Create()
    return -join ($sha.ComputeHash($head + $b) | ForEach-Object { $_.ToString("x2") })
}

function Kirim($lokal, $path) {
    $b = [IO.File]::ReadAllBytes($lokal)
    $url = "$API/contents/" + (($path -split "/" | ForEach-Object { [Uri]::EscapeDataString($_) }) -join "/")
    $lama = $null
    try { $lama = (Invoke-RestMethod -Uri $url -Headers $H).sha } catch { }
    if ($lama -eq (GitSha $b)) { return $null }
    $body = @{ message = "Update dari QGIS: $path"; content = [Convert]::ToBase64String($b) }
    if ($lama) { $body.sha = $lama }
    Write-Host "  upload $path"
    $r = Invoke-RestMethod -Method Put -Uri $url -Headers $H -Body ($body | ConvertTo-Json) -ContentType "application/json"
    return $r.commit.sha
}

Write-Host "ngirim editan ke github..."
try {
    $commit = $null
    Get-ChildItem (Join-Path $DIR "foto") -File -ErrorAction SilentlyContinue | ForEach-Object {
        $c = Kirim $_.FullName ("qgis/foto/" + $_.Name); if ($c) { $commit = $c }
    }
    $c = Kirim (Join-Path $DIR "peta_rw02.gpkg") "qgis/peta_rw02.gpkg"; if ($c) { $commit = $c }
} catch { Selesai "gagal upload: $($_.Exception.Message)`ncek internet atau token.txt nya." }

$run = $null
if (-not $commit) {
    Write-Host "gak ada editan baru. ambil banner pdf terbaru aja..."
    $run = (Invoke-RestMethod -Uri "$API/actions/runs?status=success&per_page=20" -Headers $H).workflow_runs | Where-Object { $_.name -eq "Update peta" } | Select-Object -First 1
    if (-not $run) { Selesai "belum ada banner yang jadi di github." }
} else {
Write-Host "kekirim. nunggu github bikin ulang peta (sekitar 3 menit, banner sekitar 5 menit)..."
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 20
    try { $run = (Invoke-RestMethod -Uri "$API/actions/runs?head_sha=$commit" -Headers $H).workflow_runs | Where-Object { $_.name -eq "Update peta" } | Select-Object -First 1 } catch { }
    if ($run) {
        $jobs = (Invoke-RestMethod -Uri $run.jobs_url -Headers $H).jobs
        $dep = $jobs | Where-Object { $_.name -eq "deploy" }
        if ($dep -and $dep.conclusion -eq "success" -and -not $sudahWeb) { $sudahWeb = $true; Write-Host "peta online udah ke-update: https://kkn-uad.github.io/peta-rw02-patangpuluhan/" }
        if ($run.status -eq "completed") { break }
        Write-Host "  masih proses... ($([int](($i + 1) * 20 / 60)) menit)"
    }
}
if (-not $run -or $run.conclusion -ne "success") { Selesai "proses di github gagal atau kelamaan. cek tab Actions di repo, atau kabarin admin." }
}

Write-Host "download banner pdf..."
$art = (Invoke-RestMethod -Uri "$API/actions/runs/$($run.id)/artifacts" -Headers $H).artifacts | Where-Object { $_.name -eq "banner-pdf" } | Select-Object -First 1
if (-not $art -or $art.expired) { Selesai "file banner di github udah kadaluarsa / gak ada. edit dikit terus kirim lagi biar dibikin ulang." }
$out = Join-Path (Split-Path -Parent $DIR) "banner"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$zip = Join-Path $env:TEMP "banner-pdf.zip"
Invoke-WebRequest -Uri $art.archive_download_url -Headers $H -OutFile $zip -UseBasicParsing
Expand-Archive -Path $zip -DestinationPath $out -Force
Remove-Item $zip
Start-Process $out
Selesai "beres! banner pdf ada di folder banner, peta online juga udah ke-update."
