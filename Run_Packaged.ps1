# 패키징된 빌드를 nDisplay 로 실행한다.
#
#   .\Run_Packaged.ps1 NDC_probe_site
#   .\Run_Packaged.ps1 NDC_probe_site_curved_preview
#   .\Run_Packaged.ps1 NDC_probe_site -DryRun           띄우지 않고 명령만 확인
#   .\Run_Packaged.ps1 NDC_probe_site Curved            맵이 Main 이 아닐 때만 둘째 인자
#
# 설정은 nDisplay\<이름>.ndisplay 를 찾는다. 경로를 통째로 줘도 된다.
# 맵은 짧은 이름이면 /Game/Maps/ 를 앞에 붙인다. /Game/ 으로 시작하면 그대로.
# 2026-09-03 에 맵이 /Game/VprodProject/Maps/ 에서 옮겨졌다. 옛 자리에 남은 리다이렉터는
# 쿡에 안 들어가므로 패키지에서는 새 경로를 그대로 줘야 한다.
#
# 설정이 필수인 이유: 같은 DCRA 를 여러 설정이 몬다. 현장 원본이냐 축소 미리보기냐,
# 노드를 몇 개로 쪼개느냐가 전부 .ndisplay 에서 정해진다 (bOverrideViewportsFromExternalConfig).
# 엔진도 -dc_cfg 없이는 클러스터 모드로 뜨지 않고 즉시 종료한다.
#
# 설정과 맵이 서로 맞아야 한다. .ndisplay 의 assetPath 가 가리키는 리그 액터가 그 맵 안에
# 있어야 하고, 없으면 nDisplay 가 화면을 못 잡는다. 프리셋을 바꿨으면 플러그인에서
# '벽 만들기' 로 레벨을 다시 짓고 패키징할 것.
#
# nDisplay 는 -dc_cfg 를 맵보다 먼저, 엔진 초기화 때 읽는다. 게다가 에셋 경로(/Game/...)가
# 아니라 디스크 파일만 받는다. 그래서 맵이 설정을 지목할 수 없고 둘을 따로 준다.
param(
  [Parameter(Mandatory=$true, Position=0)] [string]$Config,
  [Parameter(Position=1)] [string]$Map = "Main",
  [switch]$DryRun
)
$ErrorActionPreference = "Stop"

$exe = Join-Path $PSScriptRoot "Package\Windows\Moniter_2.exe"
if (-not (Test-Path $exe)) { throw "$exe 가 없습니다. 먼저 Package.bat 을 돌리세요." }

if ($Map -notlike "/Game/*") { $Map = "/Game/Maps/$Map" }

if (Test-Path $Config) { $cfg = (Resolve-Path $Config).Path }
else { $cfg = Join-Path $PSScriptRoot "nDisplay\$($Config -replace '\.ndisplay$','').ndisplay" }
if (-not (Test-Path $cfg)) {
  $have = (Get-ChildItem (Join-Path $PSScriptRoot "nDisplay") -Filter *.ndisplay |
           ForEach-Object BaseName) -join ", "
  throw "$cfg 가 없습니다.`n쓸 수 있는 설정: $have"
}

Write-Host "맵:   $Map"
Write-Host "설정: $cfg"

$data    = (Get-Content $cfg -Raw -Encoding UTF8 | ConvertFrom-Json).nDisplay
$cluster = $data.cluster
# 설정이 어느 리그 액터를 찾는지 찍어 둔다. 맵에 그게 없으면 화면이 안 잡힌다.
Write-Host "리그:  $($data.assetPath)"
Write-Host ""

$primary = $cluster.primaryNode.id
# 프라이머리가 먼저 떠야 나머지가 배리어에 붙는다. 순서가 뒤집히면 전부 대기만 한다.
$rest  = @($cluster.nodes.PSObject.Properties.Name | Where-Object { $_ -ne $primary } | Sort-Object)
$names = @($primary) + $rest

foreach ($n in $names) {
  $w = $cluster.nodes.$n.window
  # -dc_dev_mono 가 빠지면 렌더 디바이스가 안 만들어지고 조용히 일반 카메라가 보인다.
  $a = @($Map, "-game", "-dc_cluster", "-dc_dev_mono", "-dc_node=$n", "-dc_cfg=$cfg",
         "-windowed", "-forceres",
         "WinX=$($w.x)", "WinY=$($w.y)", "ResX=$($w.w)", "ResY=$($w.h)",
         "-nosplash", "-fixedseed", "-NoVerifyGC", "-unattended",
         "-ExecCmds=DisableAllScreenMessages")
  "{0,-10} {1}x{2}  창 위치 ({3}, {4})" -f $n, $w.w, $w.h, $w.x, $w.y | Write-Host
  if ($DryRun) { Write-Host "  $exe $($a -join ' ')" }
  else { Start-Process -FilePath $exe -ArgumentList $a }
}

if ($names.Count -gt 1 -and -not $DryRun) {
  Write-Host ""
  Write-Host "노드 $($names.Count) 개. 프레임 동기는 소프트웨어 배리어(ethernet)다."
  Write-Host "창을 하나씩 닫으면 나머지가 동기를 기다리며 멈춘다. 전부 같이 닫을 것."
}
