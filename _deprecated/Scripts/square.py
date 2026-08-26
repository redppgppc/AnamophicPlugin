"""Square map: the round.py wall rig with 90-degree (sharp) corners + a video on the wall.

    python Scripts/square.py    -> nDisplay/Square_1Screen.ndisplay + Run_Square.bat
    Rebuild_Square.bat          -> builds /Game/VprodProject/Maps/Square (created if missing)

Same 77x21 m wall and 35 m sweet spot as round.py; the only difference is that no
output-remap mask is applied, so all four corners keep their pixels.
"""
import os
import round as rig

rig.MAP = "/Game/VprodProject/Maps/Square"
rig.VIDEO = "Content/Movies/MediaExample_wall.mp4"   # 77:21 file from convert_video.py; "" = no plate
rig.ROUNDED = False                                   # square corners: no mask
rig.CFG_PATH = os.path.join(rig.ROOT, "nDisplay", "Square_1Screen.ndisplay")
rig.BAT = "Run_Square.bat"

if __name__ == "__main__":
    rig.main()
