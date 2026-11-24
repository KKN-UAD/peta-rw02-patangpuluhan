# Kirim hasil edit QGIS ke GitHub, tunggu peta online ter-update, lalu download banner PDF.
# Dijalankan lewat kirim_update.bat (klik 2x). Butuh file token.txt di folder yang sama.
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$REPO = "KKN-UAD/peta-rw02-patangpuluhan"
# --- pengaturan per RW (folder di repo, nama file data, nama banner di github, alamat peta online) ---
$SUB = ""                     # RW 02 di folder utama repo
$GPKG = "peta_rw02.gpkg"
$ARTIFACT = "banner-pdf"
$WEB = "https://kkn-uad.github.io/peta-rw02-patangpuluhan/"
$API = "https://api.github.com/repos/$REPO"
$DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

function Selesai($pesan) { Write-Host ""; Write-Host $pesan; Read-Host "tekan enter buat nutup"; exit }

$tokFile = Join-Path $DIR "token.txt"
if ($env:PETA_TOKEN) { $TOKEN = $env:PETA_TOKEN }
elseif (Test-Path $tokFile) { $TOKEN = (Get-Content $tokFile -Raw).Trim() }
else { Selesai "file token.txt belum ada di folder qgis. minta ke admin repo ya." }
$H = @{ Authorization = "Bearer $TOKEN"; "User-Agent" = "peta-rw02-update"; Accept = "application/vnd.github+json" }

if (Get-Process -Name "qgis*" -ErrorAction SilentlyContinue) { Selesai "qgis masih kebuka. tutup qgis dulu biar editannya kesimpen, terus klik lagi file ini." }
if (Test-Path (Join-Path $DIR "$GPKG-wal")) { Selesai "editan belum kesimpen penuh (ada file peta_rw02.gpkg-wal). buka qgis, save, tutup lagi, terus klik lagi file ini." }

# cek koneksi + token dulu (coba 3x)
$cek = $null
for ($i = 1; $i -le 3; $i++) {
    try { Invoke-RestMethod -Uri $API -Headers $H | Out-Null; $cek = "ok"; break }
    catch {
        $kode = $null; if ($_.Exception.Response) { $kode = [int]$_.Exception.Response.StatusCode }
        if ($kode -in 401, 403, 404) { $cek = "token"; break }
        $cek = "internet"; Write-Host "  gak bisa nyambung ke github, nyoba lagi ($i/3)..."; Start-Sleep -Seconds 5
    }
}
if ($cek -eq "internet") { Selesai "gak bisa nyambung ke github.`ncoba buka github.com di browser. kalau gak kebuka berarti internetnya mati atau wifinya ngeblok github, ganti wifi / pakai hotspot hp terus klik lagi file ini." }
if ($cek -eq "token") { Selesai "token.txt nya ditolak github (mungkin udah kadaluarsa). kabarin admin buat minta token baru." }

function GitSha([byte[]]$b) {   # sha file versi git, buat cek file berubah atau nggak
    $head = [Text.Encoding]::ASCII.GetBytes("blob $($b.Length)`0")
    $sha = [Security.Cryptography.SHA1]::Create()
    return -join ($sha.ComputeHash($head + $b) | ForEach-Object { $_.ToString("x2") })
}

function PesanGithub($err) {   # ambil pesan error asli dari github
    try {
        $sr = New-Object IO.StreamReader($err.Exception.Response.GetResponseStream())
        return ($sr.ReadToEnd() | ConvertFrom-Json).message
    } catch { return $err.Exception.Message }
}

function ShaLama($url) {
    try { return (Invoke-RestMethod -Uri ($url + "?ref=main&t=" + [DateTime]::Now.Ticks) -Headers $H).sha }
    catch { if (-not $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 404) { throw }; return $null }   # 404 = file baru
}

function Kirim($lokal, $path) {
    $b = [IO.File]::ReadAllBytes($lokal)
    if ($b.Length -gt 40MB) { throw "file $path kegedean (lebih dari 40 MB), kecilin dulu fotonya" }
    $url = "$API/contents/" + (($path -split "/" | ForEach-Object { [Uri]::EscapeDataString($_) }) -join "/")
    $baru = GitSha $b
    for ($coba = 1; $coba -le 2; $coba++) {
        $lama = ShaLama $url
        if ($lama -eq $baru) { return $null }
        $body = @{ message = "Update dari QGIS: $path"; content = [Convert]::ToBase64String($b); branch = "main" }
        if ($lama) { $body.sha = $lama }
        Write-Host "  upload $path"
        try {
            $r = Invoke-RestMethod -Method Put -Uri $url -Headers $H -Body ($body | ConvertTo-Json) -ContentType "application/json; charset=utf-8"
            return $r.commit.sha
        } catch {
            $kode = 0; if ($_.Exception.Response) { $kode = [int]$_.Exception.Response.StatusCode }
            $msg = PesanGithub $_
            if ($coba -lt 2 -and $kode -in 409, 422) { Write-Host "  ditolak (${kode}: $msg), nyoba lagi..."; Start-Sleep -Seconds 3; continue }
            throw "github nolak $path (${kode}): $msg"
        }
    }
}

Write-Host "ngirim editan ke github..."
try {
    $commit = $null
    Get-ChildItem (Join-Path $DIR "foto") -File -ErrorAction SilentlyContinue | ForEach-Object {
        $c = Kirim $_.FullName ($SUB + "qgis/foto/" + $_.Name); if ($c) { $commit = $c }
    }
    $c = Kirim (Join-Path $DIR $GPKG) ($SUB + "qgis/" + $GPKG); if ($c) { $commit = $c }
} catch { Selesai "gagal upload: $($_.Exception.Message)`nfotoin/screenshot layar ini terus kirim ke admin ya." }

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
        if ($dep -and $dep.conclusion -eq "success" -and -not $sudahWeb) { $sudahWeb = $true; Write-Host "peta online udah ke-update: $WEB" }
        if ($run.status -eq "completed") { break }
        Write-Host "  masih proses... ($([int](($i + 1) * 20 / 60)) menit)"
    }
}
if (-not $run -or $run.conclusion -ne "success") { Selesai "proses di github gagal atau kelamaan. cek tab Actions di repo, atau kabarin admin." }
}

Write-Host "download banner pdf..."
$art = (Invoke-RestMethod -Uri "$API/actions/runs/$($run.id)/artifacts" -Headers $H).artifacts | Where-Object { $_.name -eq $ARTIFACT } | Select-Object -First 1
if (-not $art -or $art.expired) { Selesai "file banner di github udah kadaluarsa / gak ada. edit dikit terus kirim lagi biar dibikin ulang." }
$out = Join-Path $DIR "banner"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$zip = Join-Path $env:TEMP "banner-pdf.zip"
Invoke-WebRequest -Uri $art.archive_download_url -Headers $H -OutFile $zip -UseBasicParsing
Expand-Archive -Path $zip -DestinationPath $out -Force
Remove-Item $zip
Start-Process $out
Selesai "beres! banner pdf ada di folder banner, peta online juga udah ke-update."
