"""RoundVideo map: the round.py wall rig + a video on the wall.

    python Scripts/round_video.py   -> nDisplay/RoundVideo_1Screen.ndisplay + Run_RoundVideo.bat
    Rebuild_RoundVideo.bat          -> builds /Game/VprodProject/Maps/RoundVideo (created if missing)

Only the knobs below differ from round.py; geometry, mask and level building are shared.
"""
import os
import round as rig

rig.MAP = "/Game/VprodProject/Maps/RoundVideo"
rig.VIDEO = "Content/Movies/MediaExample_wall.mp4"   # 77:21 file from convert_video.py
rig.ROUNDED = True                                    # False = plain rectangle
rig.CFG_PATH = os.path.join(rig.ROOT, "nDisplay", "RoundVideo_1Screen.ndisplay")
rig.BAT = "Run_RoundVideo.bat"

if __name__ == "__main__":
    rig.main()
