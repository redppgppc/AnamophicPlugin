"""Flat wall rig: 77m x 21m screen, sweet spot 35m.

Standalone:  python Scripts/flat.py    -> nDisplay/FlatWall.ndisplay + Run_FlatWall.bat
In editor:   Rebuild_FlatWall.bat      -> also places the rig + demo content in FlatWall.umap

Geometry: world origin = viewer's EYE, +X toward the wall, +Y right, +Z up. Units cm.
The wall is a plain rectangle, so an nDisplay Screen component describes it exactly.

For a wall that BENDS in plan view (two faces meeting at an angle with a fillet), see
curved.py. That is a different rig: a Screen component is always flat, so the bent wall
needs a generated warp mesh instead.

Replaces the old round.py / round_video.py / square.py trio. Those differed only by an
"outline mask" that rounded off the four corners of the screen outline. Nobody asked for
it, so it is gone and the three collapsed into this one script.
"""
import json, math, os

# --- knobs (mm on the drawing -> cm here) ----------------------------------
SCREEN_W_CM = 7700.0        # 77000 mm
SCREEN_H_CM = 2100.0        # 21000 mm
EYE_DIST_CM = 3500.0        # 35000 mm sweet spot, eye -> wall
EYE_HEIGHT_CM = 160.0       # eye above the floor; wall bottom edge sits on the floor
SCREEN_DZ_CM = SCREEN_H_CM / 2.0 - EYE_HEIGHT_CM   # wall center relative to eye

RES_W = 2560                                       # test window on one desktop monitor
RES_H = int(round(RES_W * SCREEN_H_CM / SCREEN_W_CM))  # keep 77:21
WIN_X, WIN_Y = 0, 0
FOLLOW_PLAYER = False
HIDE_SCREEN_MESSAGES = True   # 좌상단 빨간 엔진 오버레이(StereoView 등)를 끈다.
                              # 주의: 온스크린 경고를 전부 끈다. "Lighting needs to be
                              # rebuilt" 같은 진짜 경고도 안 보인다. 개발 중엔 False 가 안전.

RIG_ORIGIN = (0.0, 0.0, EYE_HEIGHT_CM)   # eye, when the level has no DCRA yet
VIDEO = "Content/Movies/MediaExample_wall.mp4"
                        # 프로젝트 기준 상대경로. "" = 영상 없음.
                        # 전개 종횡비(77:21) 파일을 쓸 것 (convert_video.py).
PLATE_YAW = 0.0         # flip to 180 if the wall renders black (plate mesh is one-sided)
DEMO = False            # 시차 확인용 큐브 + 뒷벽. 실제 콘텐츠 넣을 땐 False
DEMO_DEPTH_CM = 6000.0
VIDEO_PASSTHROUGH = True   # 영상 1:1 출력. 자동노출과 ACES 톤커브를 꺼서 파일 색이
                           # 그대로 나가게 한다. 3D 콘텐츠를 섞는 맵이면 False.
EXPOSURE_BIAS = 0.0        # 패스스루 노출 보정 EV. 원본 대비 밝기가 어긋나면 조정

UE_EXE = r"D:\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
MAP = "/Game/VprodProject/Maps/FlatWall"   # created by the Rebuild bat if missing
BAT = "Run_FlatWall.bat"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(ROOT, "nDisplay", "FlatWall.ndisplay")
ASSET_DIR, ASSET_NAME = "/Game/FlatWall", "NDC_FlatWall"
EYE_NAME, SCREEN_NAME = "DefaultViewPoint", "screen_0"


def build_config():
    return {"nDisplay": {
        "description": "Flat 77x21m wall, single viewport",
        "version": "5.00",
        "assetPath": "%s/%s.%s" % (ASSET_DIR, ASSET_NAME, ASSET_NAME),
        "misc": {"bFollowLocalPlayerCamera": FOLLOW_PLAYER, "bExitOnEsc": True,
                 "bOverrideViewportsFromExternalConfig": True,
                 "bOverrideTransformsFromExternalConfig": True},
        "scene": {
            "cameras": {EYE_NAME: {
                "parentId": "", "location": {"x": 0.0, "y": 0.0, "z": 0.0},
                "rotation": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
                "interpupillaryDistance": 6.4, "swapEyes": False, "stereoOffset": "None"}},
            "screens": {SCREEN_NAME: {
                "parentId": "", "location": {"x": EYE_DIST_CM, "y": 0.0, "z": SCREEN_DZ_CM},
                "rotation": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
                "size": {"width": SCREEN_W_CM, "height": SCREEN_H_CM}}}},
        "cluster": {
            "primaryNode": {"id": "node_0"},
            "sync": {"renderSyncPolicy": {"type": "none", "parameters": {}},
                     "inputSyncPolicy": {"type": "None", "parameters": {}}},
            "nodes": {"node_0": {
                "host": "127.0.0.1", "sound": True, "fullScreen": False,
                "window": {"x": WIN_X, "y": WIN_Y, "w": RES_W, "h": RES_H},
                "viewports": {"vp_0": {
                    "camera": EYE_NAME,
                    "region": {"x": 0, "y": 0, "w": RES_W, "h": RES_H},
                    "projectionPolicy": {"type": "mesh",
                                         "parameters": {"mesh_component": SCREEN_NAME}}}}}},
        },
    }}


def build_bat():
    lines = [
        "@echo off",
        "rem Requires: display scaling 100%, taskbar set to auto-hide (see anamorphic.py).",
        '"%s" "%s" %s ^' % (UE_EXE, os.path.join(ROOT, "Moniter_2.uproject"), MAP),
        ' -game -dc_cluster -dc_dev_mono -dc_node=node_0 -dc_cfg="%%~dp0%s" ^'
        % os.path.relpath(CFG_PATH, ROOT),
        " -windowed -forceres WinX=%d WinY=%d ResX=%d ResY=%d ^" % (WIN_X, WIN_Y, RES_W, RES_H),
        " -nosplash -fixedseed -NoVerifyGC -unattended"
        + (' -ExecCmds="DisableAllScreenMessages"' if HIDE_SCREEN_MESSAGES else ""),
    ]
    return "\r\n".join(lines) + "\r\n"


def demo():
    cfg = build_config()["nDisplay"]
    s = cfg["scene"]["screens"][SCREEN_NAME]
    assert s["location"]["z"] - SCREEN_H_CM / 2.0 == -EYE_HEIGHT_CM, "wall bottom is not on the floor"
    assert abs(RES_W / RES_H - SCREEN_W_CM / SCREEN_H_CM) < 0.01, "window aspect != wall aspect"
    vp = cfg["cluster"]["nodes"]["node_0"]["viewports"]["vp_0"]
    assert vp["camera"] in cfg["scene"]["cameras"], "view point not defined (falls back to z=50)"
    assert vp["projectionPolicy"]["parameters"]["mesh_component"] in cfg["scene"]["screens"], \
        "mesh_component resolves to nothing"
    win = cfg["cluster"]["nodes"]["node_0"]["window"]
    bat = build_bat()
    assert "ResX=%d" % win["w"] in bat and "WinX=%d" % win["x"] in bat, "bat/config window mismatch"
    # 파일이 없으면 벽이 그냥 까맣게 나온다. 레벨 빌드 전에 잡는다.
    assert not VIDEO or os.path.isfile(os.path.join(ROOT, VIDEO)), "VIDEO 파일 없음: " + VIDEO
    print("geometry ok: wall %gx%g cm at %g cm, window %dx%d, %s"
          % (SCREEN_W_CM, SCREEN_H_CM, EYE_DIST_CM, RES_W, RES_H,
             ("video " + os.path.basename(VIDEO)) if VIDEO else "no video"))
    print("  수평 화각 %.2f deg" % (2 * math.degrees(math.atan2(SCREEN_W_CM / 2, EYE_DIST_CM))))


def spawn_passthrough_volume(actors, prefix):
    """영상 전용 맵용 포스트프로세스 볼륨.

    기본 파이프라인은 자동노출 + ACES 톤커브를 거치므로 영상이 1:1 로 안 나간다.
    실측: 순색 컬러바의 0 이어야 할 채널이 최대 +136 까지 떠서 탈색된다.
    3D 씬을 예쁘게 보이려는 기능이라 영상 전용 맵에서는 방해만 된다.
    """
    import unreal
    v = actors.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0))
    v.set_actor_label(prefix + "passthrough")
    v.set_editor_property("unbound", True)          # 레벨 전체에 적용
    v.set_editor_property("priority", 1000.0)       # 다른 볼륨보다 우선
    # 구조체는 값으로 복사되어 오므로 고친 뒤 되돌려 넣어야 한다.
    s = v.get_editor_property("settings")
    for k, val in (("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL),
                   ("auto_exposure_apply_physical_camera_exposure", False),
                   ("auto_exposure_bias", EXPOSURE_BIAS),
                   ("tone_curve_amount", 0.0),
                   ("expand_gamut", 0.0),
                   ("blue_correction", 0.0)):
        s.set_editor_property("override_" + k, True)
        s.set_editor_property(k, val)
    v.set_editor_property("settings", s)
    return v


def build_level():
    import unreal
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    keep_transform = None
    for a in actors.get_all_level_actors():
        if isinstance(a, unreal.DisplayClusterRootActor):
            keep_transform = (a.get_actor_location(), a.get_actor_rotation())
            actors.destroy_actor(a)
        elif a.get_actor_label().startswith("FLAT_"):
            actors.destroy_actor(a)

    asset = "%s/%s" % (ASSET_DIR, ASSET_NAME)
    if not unreal.EditorAssetLibrary.does_asset_exist(asset):
        task = unreal.AssetImportTask()
        task.filename, task.destination_path, task.destination_name = CFG_PATH, ASSET_DIR, ASSET_NAME
        task.automated = task.replace_existing = task.save = True
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    O = unreal.Vector(*RIG_ORIGIN)
    cube = unreal.load_object(None, "/Engine/BasicShapes/Cube.Cube")
    grid = unreal.load_object(None, "/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial")

    def spawn(name, loc, size, hidden=False):
        act = actors.spawn_actor_from_object(cube, unreal.Vector(*loc) + O)
        act.set_actor_label("FLAT_" + name)
        act.set_actor_scale3d(unreal.Vector(*[v / 100.0 for v in size]))
        act.static_mesh_component.set_material(0, grid)
        # The frame sits ON the screen plane, so it would render over the wall content.
        act.set_actor_hidden_in_game(hidden)
        return act

    # Reference frame of the physical wall: 4 edge bars, so the outline is visible
    # in the editor. Hidden in game.
    t, X, W, H = 20.0, EYE_DIST_CM, SCREEN_W_CM / 2, SCREEN_H_CM / 2
    spawn("top",    (X, 0, SCREEN_DZ_CM + H), (t, 2 * W, t), hidden=True)
    spawn("bottom", (X, 0, SCREEN_DZ_CM - H), (t, 2 * W, t), hidden=True)
    spawn("left",   (X, -W, SCREEN_DZ_CM),    (t, t, 2 * H), hidden=True)
    spawn("right",  (X,  W, SCREEN_DZ_CM),    (t, t, 2 * H), hidden=True)

    if DEMO:
        x1 = EYE_DIST_CM + DEMO_DEPTH_CM
        k = x1 / EYE_DIST_CM   # widest ray, out to the back wall
        y, z = (W + 200) * k, (H + 200) * k
        spawn("back",  (x1, 0, SCREEN_DZ_CM), (t, 2 * y, 2 * z))
        spawn("floor", ((EYE_DIST_CM + x1) / 2, 0, -EYE_HEIGHT_CM - t / 2), (DEMO_DEPTH_CM, 2 * y, t))
        for i, (dx, dy, dz, s) in enumerate(((800, -2000, 0, 300), (1500, 0, 600, 400),
                                             (2500, 2200, -100, 500), (4500, -1000, 300, 800))):
            spawn("cue%d" % i, (EYE_DIST_CM + dx, dy, dz), (s, s, s))

    if VIDEO:
        # MediaPlate auto-plays on BeginPlay; sits exactly on the screen plane, fills it.
        # The wall is flat, so a flat plate maps 1:1. (A bent wall does not - see curved.py.)
        plate = actors.spawn_actor_from_class(
            unreal.MediaPlate, unreal.Vector(EYE_DIST_CM, 0, SCREEN_DZ_CM) + O,
            unreal.Rotator(roll=0.0, pitch=0.0, yaw=PLATE_YAW))
        plate.set_actor_label("FLAT_video")
        comp = plate.get_editor_property("media_plate_component")
        res = unreal.MediaPlateResource()
        res.set_editor_property("type", unreal.MediaPlateResourceType.EXTERNAL)
        res.set_editor_property("external_media_path", os.path.join(ROOT, VIDEO))
        comp.set_editor_property("media_plate_resource", res)
        # 켜져 있으면 영상 종횡비에 맞춰 메시 스케일을 덮어쓴다.
        comp.set_is_aspect_ratio_auto(False)
        comp.set_editor_property("loop", True)
        # SM_MediaPlateScreen is a 100x100 plane in local Y/Z.
        plate.get_editor_property("static_mesh_component").set_relative_scale3d(
            unreal.Vector(1.0, SCREEN_W_CM / 100.0, SCREEN_H_CM / 100.0))

    if VIDEO_PASSTHROUGH:
        spawn_passthrough_volume(actors, "FLAT_")

    cls = unreal.load_object(None, "%s/%s.%s_C" % (ASSET_DIR, ASSET_NAME, ASSET_NAME))
    dcra = (actors.spawn_actor_from_class(cls, *keep_transform) if keep_transform
            else actors.spawn_actor_from_class(cls, O))
    dcra.set_actor_label(ASSET_NAME)
    for c in dcra.get_components_by_class(unreal.DisplayClusterCameraComponent):
        if c.get_name() == EYE_NAME:
            c.set_relative_location(unreal.Vector(0, 0, 0), False, False)
    for c in dcra.get_components_by_class(unreal.DisplayClusterScreenComponent):
        if c.get_name() == SCREEN_NAME:
            c.set_relative_location_and_rotation(unreal.Vector(EYE_DIST_CM, 0, SCREEN_DZ_CM),
                                                 unreal.Rotator(0, 0, 0), False, False)
            c.set_relative_scale3d(unreal.Vector(1.0, SCREEN_W_CM, SCREEN_H_CM))
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        # Error Code 32 in the log = another editor has FlatWall.umap open. Open a
        # different level there (or run this script from that editor's Python console).
        raise RuntimeError("FlatWall.umap save FAILED - level not updated (is it open in another editor?)")
    unreal.log("flat rig ready: DCRA at %s = viewer's eye (%s), wall at %g cm"
               % (dcra.get_actor_location(), "kept from level" if keep_transform else "RIG_ORIGIN", EYE_DIST_CM))


def main():
    demo()
    os.makedirs(os.path.dirname(CFG_PATH), exist_ok=True)
    with open(CFG_PATH, "w") as f:
        json.dump(build_config(), f, indent=2)
    with open(os.path.join(ROOT, BAT), "w", newline="") as f:
        f.write(build_bat())
    print("wrote " + CFG_PATH + "\nwrote " + BAT)
    try:
        import unreal  # noqa: F401
    except ImportError:
        pass
    else:
        build_level()


if __name__ == "__main__":
    main()
