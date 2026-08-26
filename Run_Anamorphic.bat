@echo off
rem Requires: monitors side by side with the left one at (0,0), display scaling 100%, taskbar set to auto-hide.
"D:\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" "D:\Temp\Moniter_2\Moniter_2.uproject" /Game/VprodProject/Maps/Main ^
 -game -dc_cluster -dc_dev_mono -dc_node=node_0 -dc_cfg="%~dp0nDisplay\Anamorphic_2Mon.ndisplay" ^
 -windowed -forceres WinX=0 WinY=0 ResX=3840 ResY=1440 ^
 -nosplash -fixedseed -NoVerifyGC -unattended -ExecCmds="DisableAllScreenMessages"
