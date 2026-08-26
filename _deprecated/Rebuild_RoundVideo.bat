@echo off
rem Rebuilds the RoundVideo map headlessly (round.py rig + video plate; see Scripts\round_video.py).
rem If the Unreal editor has that level open, the save fails (Error 32) - open another level there first.
set S=%TEMP%\rndvideo_rebuild.py
> "%S%" echo import sys, unreal
>> "%S%" echo sys.path.insert(0, r'%~dp0Scripts')
>> "%S%" echo import round_video, round
>> "%S%" echo les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
>> "%S%" echo if unreal.EditorAssetLibrary.does_asset_exist(round.MAP): les.load_level(round.MAP)
>> "%S%" echo else: assert les.new_level_from_template(round.MAP, '/Engine/Maps/Templates/Template_Default'), 'new level failed'
>> "%S%" echo round.build_level()
"D:\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "%~dp0Moniter_2.uproject" -ExecutePythonScript="%S%" -unattended -nosplash
echo done.
