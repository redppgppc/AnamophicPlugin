@echo off
rem 배포용 실행 파일을 만든다. 결과: Package\Windows\Moniter_2.exe
rem
rem   Package.bat                      Main 맵, Development
rem   Package.bat Main+Curved          맵 여러 개는 + 로
rem   Package.bat Main Shipping        구성까지 지정
rem
rem 에디터를 닫고 돌릴 것. 켜져 있으면 쿡 중 에셋 잠김으로 실패한다.
rem Shipping 은 -ExecCmds 가 막혀 DisableAllScreenMessages 가 안 먹는다. 현장은 Development.
rem 이 파일은 CP949 + CRLF 로 저장한다. UTF-8 이나 LF 면 cmd 파서가 통째로 깨진다.
setlocal
set MAP=%~1
if "%MAP%"=="" set MAP=Main
set CFG=%~2
if "%CFG%"=="" set CFG=Development

rem 쿡 목록은 -MapsToCook 이다. -map 은 '실행할 맵' 이라 쿡 목록을 제대로 못 정한다
rem (ProjectParams.cs 의 MapToRun). 안 주면 프로젝트 기본 맵과 그 참조만 쿡된다.
call "D:\Epic Games\UE_5.8\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun ^
 -project="%~dp0Moniter_2.uproject" -noP4 -platform=Win64 -clientconfig=%CFG% ^
 -MapsToCook=%MAP% ^
 -cook -build -stage -pak -archive -archivedirectory="%~dp0Package" -utf8output
if errorlevel 1 (
  echo.
  echo [실패] 패키징이 에러로 끝났습니다.
  echo         로그: %USERPROFILE%\AppData\Roaming\Unreal Engine\AutomationTool\Logs
  echo         가장 흔한 원인: 언리얼 에디터가 켜져 있어 .uasset/.umap 이 잠김.
  exit /b 1
)

rem 요청한 맵이 실제로 들어갔는지 확인한다. -map 이 조용히 무시된 적이 있어서 넣었다.
echo.
echo 패키지에 들어간 맵:
findstr /i "\.umap" "%~dp0Package\Windows\Manifest_UFSFiles_Win64.txt"
echo.
echo done.  실행: .\Run_Packaged.ps1 맵이름 설정이름
echo         예:   .\Run_Packaged.ps1 Main NDC_probe_site
