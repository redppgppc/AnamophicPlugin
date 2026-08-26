@echo off
rem Requires: display scaling 100%, taskbar set to auto-hide (see anamorphic.py).
"D:\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" "D:\Temp\Moniter_2\Moniter_2.uproject" /Game/VprodProject/Maps/Curved ^
 -game -dc_cluster -dc_dev_mono -dc_node=node_0 -dc_cfg="%~dp0nDisplay\Curved_1Screen.ndisplay" ^
 -windowed -forceres WinX=0 WinY=0 ResX=2560 ResY=758 ^
 -nosplash -fixedseed -NoVerifyGC -unattended -ExecCmds="DisableAllScreenMessages"
