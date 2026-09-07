<#
.SYNOPSIS
    프로젝트를 SVN 업로드 폴더에 동기화한다. 커밋은 하지 않는다.

.DESCRIPTION
    무엇을 보낼지는 git 이 정한다 (git ls-files). .gitignore 에 "배포 대상이 아닌 것" 이
    이미 다 적혀 있어서, 제외 목록을 두 벌 관리하지 않으려는 것이다. 변환 영상·블렌드 맵·
    __pycache__ 처럼 언제든 다시 만드는 것은 그래서 안 간다.

    커밋은 안 한다. 마지막에 명령만 찍어 준다. 공유 서버라 사람이 눌러야 한다.

.PARAMETER Dst
    SVN 작업 사본 안의 대상 폴더.

.PARAMETER Prune
    대상에만 있는 파일을 지우고 svn delete 로 예약한다. 기본은 목록만 보여 준다.

.EXAMPLE
    .\Sync_SVN.ps1
    .\Sync_SVN.ps1 -Prune
#>
param(
    [string]$Dst = "D:\trunk\Anamorphic\AnamorphicPlugin",
    [switch]$Prune
)

$ErrorActionPreference = "Stop"
# git·svn 이 한글 경로를 뱉는다 (Content/새_폴더). 콘솔 인코딩을 안 맞추면
# 깨진 경로로 파일을 찾다가 조용히 빠뜨린다.
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$OutputEncoding = [Text.Encoding]::UTF8

$Src = $PSScriptRoot
if (-not (Test-Path -LiteralPath $Dst -PathType Container)) {
    throw "대상 폴더가 없습니다: $Dst"
}
if (-not (Get-Command svn -ErrorAction SilentlyContinue)) {
    throw "svn 이 PATH 에 없습니다"
}

Write-Host "소스  $Src"
Write-Host "대상  $Dst"
Write-Host ""

# --- 1. 보낼 목록 -----------------------------------------------------------
Push-Location $Src
try {
    $files = @(git -c core.quotepath=false ls-files) | Where-Object { $_ }
} finally {
    Pop-Location
}
if ($files.Count -eq 0) { throw "git ls-files 가 아무것도 못 냈습니다" }
Write-Host ("보낼 파일  {0}개" -f $files.Count)

# --- 2. 복사 ----------------------------------------------------------------
# 크기와 수정 시각이 같으면 건너뛴다. Copy-Item 은 수정 시각을 보존한다.
$copied = 0
foreach ($rel in $files) {
    $s = Join-Path $Src $rel
    if (-not (Test-Path -LiteralPath $s -PathType Leaf)) { continue }   # git 에만 남은 것
    $d = Join-Path $Dst $rel
    $si = Get-Item -LiteralPath $s
    $di = Get-Item -LiteralPath $d -ErrorAction SilentlyContinue
    if ($di -and $di.Length -eq $si.Length -and $di.LastWriteTimeUtc -eq $si.LastWriteTimeUtc) {
        continue
    }
    $dir = Split-Path -Parent $d
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    Copy-Item -LiteralPath $s -Destination $d -Force
    $copied++
}
Write-Host ("복사함     {0}개" -f $copied)

# --- 3. 대상에만 있는 것 ----------------------------------------------------
$want = [System.Collections.Generic.HashSet[string]]::new(
    [string[]]$files, [StringComparer]::OrdinalIgnoreCase)
$cut = $Dst.TrimEnd('\').Length + 1
$extra = @(Get-ChildItem -LiteralPath $Dst -Recurse -File -Force |
    Where-Object { $_.FullName -notlike "*\.svn\*" } |
    ForEach-Object { $_.FullName.Substring($cut).Replace('\', '/') } |
    Where-Object { -not $want.Contains($_) })

if ($extra.Count -gt 0) {
    Write-Host ""
    Write-Host ("대상에만 있음  {0}개" -f $extra.Count) -ForegroundColor Yellow
    $extra | Select-Object -First 15 | ForEach-Object { Write-Host "  $_" }
    if ($extra.Count -gt 15) { Write-Host ("  ... 외 {0}개" -f ($extra.Count - 15)) }
    if (-not $Prune) {
        Write-Host "  -> 지우려면 -Prune 을 붙여 다시 실행" -ForegroundColor Yellow
    }
}

# --- 4. svn 에 알린다 -------------------------------------------------------
Write-Host ""
if ($Prune -and $extra.Count -gt 0) {
    # svn delete --force 는 작업 사본에서 파일까지 지우고 삭제를 예약한다.
    # 버전 관리 밖의 파일에는 실패하므로, 남은 것은 아래에서 직접 지운다.
    for ($i = 0; $i -lt $extra.Count; $i += 50) {
        $batch = $extra[$i..([Math]::Min($i + 49, $extra.Count - 1))] |
                 ForEach-Object { Join-Path $Dst $_ }
        & svn delete --force -- @batch 2>&1 | Out-Null
    }
    $left = @($extra | ForEach-Object { Join-Path $Dst $_ } |
              Where-Object { Test-Path -LiteralPath $_ })
    if ($left.Count -gt 0) { Remove-Item -LiteralPath $left -Force }
    Write-Host ("지움       {0}개" -f $extra.Count)
}

# --force 는 이미 등록된 것을 건너뛰고 새 파일만 등록한다.
& svn add --force -- $Dst | Out-Null

Write-Host ""
Write-Host "--- svn status ---"
& svn status -- $Dst

Write-Host ""
Write-Host "확인한 뒤 직접 커밋할 것:" -ForegroundColor Cyan
Write-Host "  svn commit `"$Dst`" -m `"메시지`"" -ForegroundColor Cyan
