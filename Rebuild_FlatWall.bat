@echo off
rem Rebuilds the flat 77x21m wall rig headlessly into FlatWall.umap (created from the
rem default template if missing). See Scripts\flat.py.
rem Run "python Scripts\flat.py" FIRST if you changed anything - this only builds the level.
rem If the Unreal editor has that level open, the save fails (Error 32) - open another level there first.
set S=%TEMP%\flat_rebuild.py
> "%S%" echo import sys, unreal
>> "%S%" echo sys.path.insert(0, r'%~dp0Scripts')
>> "%S%" echo import flat
>> "%S%" echo les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
>> "%S%" echo if unreal.EditorAssetLibrary.does_asset_exist(flat.MAP): les.load_level(flat.MAP)
>> "%S%" echo else: assert les.new_level_from_template(flat.MAP, '/Engine/Maps/Templates/Template_Default'), 'new level failed'
>> "%S%" echo flat.build_level()
"D:\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "%~dp0Moniter_2.uproject" -ExecutePythonScript="%S%" -unattended -nosplash
if errorlevel 1 (
  echo.
  echo [실패] 빌드가 에러로 끝났습니다. Saved\Logs 의 최신 로그를 확인하세요.
  echo         가장 흔한 원인: 언리얼 에디터가 켜져 있어 .uasset/.umap 이 잠김.
  exit /b 1
)
echo done.
