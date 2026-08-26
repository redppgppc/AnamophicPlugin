@echo off
rem Rebuilds the rig in the level headlessly (screen size, RIG_ORIGIN, demo alcove).
rem Only needed when MON_W/H_CM or RIG_ORIGIN change - everything else is config-only.
rem If the Unreal editor is open with this level, reload the level in it afterwards.
set S=%TEMP%\ana_rebuild.py
> "%S%" echo import sys, unreal
>> "%S%" echo unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/VprodProject/Maps/Main')
>> "%S%" echo sys.path.insert(0, r'%~dp0Scripts')
>> "%S%" echo import anamorphic
>> "%S%" echo anamorphic.build_level()
"D:\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "%~dp0Moniter_2.uproject" -ExecutePythonScript="%S%" -unattended -nosplash
if errorlevel 1 (
  echo.
  echo [실패] 빌드가 에러로 끝났습니다. Saved\Logs 의 최신 로그를 확인하세요.
  echo         가장 흔한 원인: 언리얼 에디터가 켜져 있어 .uasset/.umap 이 잠김.
  exit /b 1
)
echo done.
