"""Anamorphic rig for N panels of arbitrary size (corner chain and/or free placement).

Standalone:  python Scripts/anamorphic.py      -> writes nDisplay/Anamorphic_2Mon.ndisplay
In editor:   Tools > Execute Python Script     -> also imports the config + builds the demo alcove

Geometry: world origin = viewer's EYE, +X forward, +Y right, +Z up. Units cm.
Each panel becomes one nDisplay Screen component plus one viewport. Off-axis
frustums come for free from nDisplay's mesh policy pointed at each Screen.

Panels are described in PANELS below. A panel is either chained (heading + gap,
laid end to end from the previous one) or free (explicit x/y/yaw). See PANELS.
"""
import json, math, os

# ============================================================================
# [1] python 실행만 하면 되는 값  (python Scripts\anamorphic.py -> bat 재실행)
#     measure these, don't trust the spec sheet
# ============================================================================

# --- 패널 목록 --------------------------------------------------------------
# 관람자 기준 왼쪽부터 순서대로 적는다. 개수 제한 없음. 크기는 패널마다 달라도 된다.
#
#   name  nDisplay Screen 컴포넌트 이름. 이 이름이 DCRA 에셋에 구워진다.
#         이름이나 개수를 바꾸면 에셋을 지우고 다시 임포트해야 한다 (build_level 이 잡아 준다).
#   w, h  표시 영역 실측 크기 (cm). 사양서 말고 자로 잰 값.
#   rw, rh  이 패널의 픽셀 해상도.
#   dz    패널 세로 중심의 높이, 눈 기준 (+ 가 위).
#
# 위치는 둘 중 하나로 준다.
#
#   [체인]  heading, gap
#           heading = 평면도에서 이 패널이 **왼쪽 끝에서 오른쪽 끝으로** 뻗는 방향(도).
#                     0 = +X(정면), 90 = +Y(오른쪽), 180 = -X, -90 = -Y(왼쪽).
#           gap     = 앞 패널 끝과의 간격 (cm). 베젤이나 실제 틈. 0 이면 딱 붙는다.
#           앞 패널 끝에서 이어 붙으므로 이음매가 저절로 맞는다.
#
#   [자유]  x, y, yaw
#           x, y = 패널 중심의 평면도 좌표 (cm, 눈이 원점).
#           yaw  = 면 법선의 방위(도). 법선은 관람자를 **등지는** 방향이다
#                  (nDisplay Screen 규약: 로컬 +X = 시선 방향). yaw = heading - 90.
#           자유 패널은 체인을 끊고 새로 시작한다. 뒤따르는 체인 패널은 이 패널 끝에서 이어진다.
#
# 출력 창에서의 위치는 기본이 PANELS 순서대로 왼쪽부터 타일링이다.
# 다르게 붙이려면 rx, ry (창 안 좌상단 픽셀 좌표) 를 직접 준다.
PANELS = [
    dict(name="screen_left",  w=35.4, h=39.8, rw=1280, rh=1440, heading=135.0, gap=0.0, dz=-4.6),
    dict(name="screen_right", w=70.8, h=39.8, rw=2560, rh=1440, heading=45.0,  gap=0.0, dz=-4.6),
]

# 체인을 눈 앞 어디에 걸어 둘지. ANCHOR_SEAM 번째 이음매가 (EYE_DIST_CM, 0) 에 온다.
#   0 = 첫 패널의 왼쪽 끝, 1 = 1번과 2번 사이, ... N = 마지막 패널의 오른쪽 끝.
# 자유 패널은 이미 눈 좌표계이므로 이 이동의 영향을 받지 않는다.
EYE_DIST_CM = 60.0   # 눈 -> 기준 이음매, 정면 방향 거리 (오목 90도는 51 보다 커야 함)
ANCHOR_SEAM = 1

WIN_X, WIN_Y = 0, 0    # 확장 데스크톱에서 창을 놓을 위치
FOLLOW_PLAYER = False  # True: the rig follows the player camera, so WASD/mouse
                       # fly the corner through the scene (content preview).
                       # False: eye nailed to RIG_ORIGIN (installation mode).
HIDE_SCREEN_MESSAGES = True   # 좌상단 빨간 엔진 오버레이(StereoView 등)를 끈다.
                              # 주의: 온스크린 경고를 전부 끈다. "Lighting needs to be
                              # rebuilt" 같은 진짜 경고도 안 보인다. 개발 중엔 False 가 안전.

# ============================================================================
# [2] Rebuild_Level.bat 까지 돌려야 하는 값  (python -> Rebuild_Level.bat -> bat)
#     레벨에 배치되는 액터(스크린 메시 크기, 데모 박스)에 반영되는 값들.
#     PANELS 의 w/h 도 여기에 속한다. 컴포넌트 스케일이 레벨에 구워지기 때문.
# ============================================================================
RIG_ORIGIN = (0.0, 0.0, 1000.0)  # eye position when the level has no DCRA yet.
                                 # If a DCRA already exists, rebuilds keep its
                                 # current (hand-placed) position instead.
DEMO_ALCOVE = False          # False: rig only, no demo walls/cubes (existing ANA_* actors are removed)
ALCOVE_DEPTH_CM = 300.0     # how deep the hole in the wall looks
CUE_SIZE_CM = 8.0           # size of the demo parallax cubes

UE_EXE = r"D:\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
MAP = "/Game/VprodProject/Maps/Main"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(ROOT, "nDisplay", "Anamorphic_2Mon.ndisplay")
ASSET_DIR, ASSET_NAME = "/Game/Anamorphic", "NDC_Anamorphic_2Mon"
# The DCRA's built-in view point sits at z=50, which would put the render eye
# half a metre above the panels. Pin it back to the origin from the config --
# naming the existing component means no re-import is needed (the nDisplay
# factory refuses to overwrite an existing asset, and deleting it fails while
# an editor holds the .uasset).
EYE_NAME = "DefaultViewPoint"


# --- 배치 -------------------------------------------------------------------
def _dir(deg):
    r = math.radians(deg)
    return math.cos(r), math.sin(r)


def place_panels():
    """PANELS -> 해결된 패널 리스트. 각 항목에 loc(x,y,z), yaw, region 이 채워진다.

    체인 패널은 앞 패널 끝에서 이어 붙이고, 자유 패널은 준 좌표를 그대로 쓴다.
    앵커 이동은 선두 체인(첫 자유 패널 이전)에만 적용된다. 자유 패널의 좌표는
    이미 눈 좌표계이고, 그 뒤로 이어지는 체인도 마찬가지이기 때문."""
    assert PANELS, "PANELS 가 비었다"
    cur, seams, moving, out = (0.0, 0.0), [(0.0, 0.0)], True, []
    for p in PANELS:
        free = "x" in p and "y" in p
        assert free or "heading" in p, \
            "%s: heading 도 x/y 도 없다. 체인이면 heading, 자유면 x/y/yaw 를 줄 것" % p["name"]
        if free:
            yaw = p["yaw"]
            dx, dy = _dir(yaw + 90.0)          # 화면 왼쪽 -> 오른쪽 방향
            cx, cy = p["x"], p["y"]
            moving = False                      # 여기서부터는 이미 눈 좌표계
        else:
            dx, dy = _dir(p["heading"])
            yaw = p["heading"] - 90.0
            t = p.get("gap", 0.0) + p["w"] / 2.0
            cx, cy = cur[0] + dx * t, cur[1] + dy * t
        half = p["w"] / 2.0
        cur = (cx + dx * half, cy + dy * half)
        if moving:
            seams.append(cur)
        q = dict(p)
        q.update(loc=(cx, cy, p["dz"]), yaw=yaw, wide=(dx, dy), moving=moving)
        out.append(q)

    assert 0 <= ANCHOR_SEAM < len(seams), \
        "ANCHOR_SEAM=%d 는 범위 밖. 선두 체인의 이음매는 0..%d" % (ANCHOR_SEAM, len(seams) - 1)
    ax, ay = seams[ANCHOR_SEAM]
    ox, oy = EYE_DIST_CM - ax, -ay
    for q in out:
        if q.pop("moving"):
            x, y, z = q["loc"]
            q["loc"] = (x + ox, y + oy, z)

    # 출력 창에서의 자리. 기본은 왼쪽부터 나란히.
    px = 0
    for q in out:
        q["region"] = (q.get("rx", px), q.get("ry", 0), q["rw"], q["rh"])
        px = q["region"][0] + q["rw"]
    return out


def window_size():
    """모든 리전을 담는 창 크기."""
    r = [q["region"] for q in place_panels()]
    return max(x + w for x, _, w, _ in r), max(y + h for _, y, _, h in r)


# --- 설정 / bat -------------------------------------------------------------
def viewport_name(panel_name):
    """패널 이름 -> 뷰포트 이름. 두 곳에서 같은 규칙을 써야 하므로 여기 하나만 둔다."""
    return "vp_" + panel_name.split("_", 1)[-1]


def build_config():
    panels = place_panels()
    ww, wh = window_size()
    return {"nDisplay": {
        "description": "Anamorphic rig, %d panel(s)" % len(panels),
        "version": "5.00",
        "assetPath": "%s/%s.%s" % (ASSET_DIR, ASSET_NAME, ASSET_NAME),
        # Both overrides on, or the runtime silently uses whatever was last
        # imported into the blueprint and ignores this file's geometry.
        # Screen *size* is still blueprint-only (UpdateComponentTransformsOnly
        # sets location/rotation only) -- re-import if w/h change.
        "misc": {"bFollowLocalPlayerCamera": FOLLOW_PLAYER, "bExitOnEsc": True,
                 "bOverrideViewportsFromExternalConfig": True,
                 "bOverrideTransformsFromExternalConfig": True},
        "scene": {
            "cameras": {EYE_NAME: {  # moved to the origin at runtime
                "parentId": "", "location": {"x": 0.0, "y": 0.0, "z": 0.0},
                "rotation": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
                "interpupillaryDistance": 6.4, "swapEyes": False, "stereoOffset": "None"}},
            "screens": {
                q["name"]: {"parentId": "", "location": dict(zip("xyz", q["loc"])),
                            "rotation": {"pitch": 0.0, "yaw": q["yaw"], "roll": 0.0},
                            "size": {"width": q["w"], "height": q["h"]}}
                for q in panels}},
        "cluster": {
            "primaryNode": {"id": "node_0"},
            "sync": {"renderSyncPolicy": {"type": "none", "parameters": {}},
                     "inputSyncPolicy": {"type": "None", "parameters": {}}},
            "nodes": {"node_0": {
                "host": "127.0.0.1", "sound": True, "fullScreen": False,
                "window": {"x": WIN_X, "y": WIN_Y, "w": ww, "h": wh},
                "viewports": {
                    viewport_name(q["name"]): {
                        "camera": EYE_NAME,
                        "region": dict(zip(("x", "y", "w", "h"), q["region"])),
                        "projectionPolicy": {"type": "mesh",
                                             "parameters": {"mesh_component": q["name"]}}}
                    for q in panels}}},
        },
    }}


def build_bat():
    """WinX/ResX are what actually place the window; the config rect does not
    move it (nDisplay's ResizeWindow is dead code in 5.8).

    The taskbar must be auto-hidden. Otherwise the primary monitor's work area
    is 48px short, SWindow clamps the new window to that height, and because the
    result no longer matches the requested size FSceneViewport::ResizeFrame
    re-snaps the window to another monitor's work area origin.
    """
    ww, wh = window_size()
    lines = [
        "@echo off",
        "rem Requires: monitors side by side with the left one at (%d,%d),"
        " display scaling 100%%, taskbar set to auto-hide." % (WIN_X, WIN_Y),
        '"%s" "%s" %s ^' % (UE_EXE, os.path.join(ROOT, "Moniter_2.uproject"), MAP),
        # -dc_dev_mono is required: without it nDisplay creates no render device
        # and the window silently shows the ordinary player camera instead.
        ' -game -dc_cluster -dc_dev_mono -dc_node=node_0 -dc_cfg="%%~dp0%s" ^'
        % os.path.relpath(CFG_PATH, ROOT),
        " -windowed -forceres WinX=%d WinY=%d ResX=%d ResY=%d ^" % (WIN_X, WIN_Y, ww, wh),
        " -nosplash -fixedseed -NoVerifyGC -unattended"
        + (' -ExecCmds="DisableAllScreenMessages"' if HIDE_SCREEN_MESSAGES else ""),
    ]
    return "\r\n".join(lines) + "\r\n"


def alcove_bounds():
    """Box that contains the whole view frustum out to the back wall. Sizing it
    at the back-wall plane (not the panel plane) is what keeps the frustum from
    leaking past the walls at larger depths."""
    panels = place_panels()
    corners = []
    for q in panels:
        (cx, cy, cz), (dx, dy) = q["loc"], q["wide"]
        for s in (-1.0, 1.0):
            corners.append((cx + dx * s * q["w"] / 2.0, cy + dy * s * q["w"] / 2.0,
                            cz, q["h"] / 2.0))
    x_near = min(c[0] for c in corners)          # 가장 가까운 패널 모서리
    t = (max(c[0] for c in corners) + ALCOVE_DEPTH_CM) / x_near   # 가장 넓은 광선
    y = max(abs(c[1]) for c in corners) * t
    z = max(abs(c[2]) + c[3] for c in corners) * t
    return x_near, y, z


# --- one runnable check ----------------------------------------------------
def demo():
    panels = place_panels()
    names = [q["name"] for q in panels]
    assert len(set(names)) == len(names), "패널 이름이 중복됨: %s" % names

    for q in panels:
        (cx, cy, cz), yaw, (dx, dy) = q["loc"], q["yaw"], q["wide"]
        r = math.radians(yaw)
        n = (math.cos(r), math.sin(r))                  # 로컬 +X = 법선(시선 방향)
        assert abs(math.hypot(*n) - 1.0) < 1e-9
        # 법선이 관람자를 등져야 한다. 반대면 화면이 좌우로 뒤집혀 나온다.
        assert n[0] * cx + n[1] * cy > 0, \
            "%s: 법선이 관람자를 향한다. heading(자유 배치면 yaw)에 180 을 더할 것" % q["name"]
        # wide 는 yaw 에서 유도되므로 둘이 어긋나면 배치 계산이 틀린 것이다.
        assert abs(dx - (-math.sin(r))) < 1e-9 and abs(dy - math.cos(r)) < 1e-9, \
            "%s: heading 과 yaw 가 불일치" % q["name"]
        for s in (-1.0, 1.0):
            ex = cx + dx * s * q["w"] / 2.0
            assert ex > 0.0, \
                "%s 의 모서리가 눈 뒤에 있다 (x=%.1f). EYE_DIST_CM 을 키울 것" % (q["name"], ex)

    # 출력 리전이 겹치거나 창 밖으로 나가면 안 된다.
    ww, wh = window_size()
    for i, a in enumerate(panels):
        ax, ay, aw, ah = a["region"]
        assert ax >= 0 and ay >= 0 and ax + aw <= ww and ay + ah <= wh, \
            "%s 의 리전이 창 %dx%d 를 벗어남: %s" % (a["name"], ww, wh, a["region"])
        for b in panels[i + 1:]:
            bx, by, bw, bh = b["region"]
            if ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah:
                raise AssertionError("%s 와 %s 의 출력 리전이 겹침" % (a["name"], b["name"]))

    cfg = build_config()["nDisplay"]
    cams = cfg["scene"]["cameras"]
    vps = cfg["cluster"]["nodes"]["node_0"]["viewports"]
    assert len(vps) == len(panels), "뷰포트 이름이 충돌함 (패널 이름의 첫 '_' 뒷부분이 겹침)"
    for vp_name, v in vps.items():
        assert v["camera"] in cams, vp_name + ": view point not defined (falls back to z=50)"
        assert v["projectionPolicy"]["parameters"]["mesh_component"] in cfg["scene"]["screens"], \
            vp_name + ": mesh_component 가 어떤 스크린도 가리키지 않음"
    assert all(c["location"] == {"x": 0.0, "y": 0.0, "z": 0.0} for c in cams.values()), \
        "eye must sit at the rig origin"
    win = cfg["cluster"]["nodes"]["node_0"]["window"]
    bat = build_bat()
    assert "ResX=%d" % win["w"] in bat and "WinX=%d" % win["x"] in bat, "bat/config window mismatch"

    print("geometry ok: 패널 %d 장, 창 %dx%d" % (len(panels), ww, wh))
    for q in panels:
        (cx, cy, cz), (dx, dy) = q["loc"], q["wide"]
        a = [math.degrees(math.atan2(cy + dy * s * q["w"] / 2.0,
                                     cx + dx * s * q["w"] / 2.0)) for s in (-1.0, 1.0)]
        print("  %-14s %gx%g cm  %dx%d px  중심(%.1f, %.1f, %.1f) yaw %+.1f  방위 %+.2f..%+.2f deg"
              % (q["name"], q["w"], q["h"], q["rw"], q["rh"], cx, cy, cz, q["yaw"], a[0], a[1]))
    lo = min(math.degrees(math.atan2(q["loc"][1] + q["wide"][1] * s * q["w"] / 2.0,
                                     q["loc"][0] + q["wide"][0] * s * q["w"] / 2.0))
             for q in panels for s in (-1.0, 1.0))
    hi = max(math.degrees(math.atan2(q["loc"][1] + q["wide"][1] * s * q["w"] / 2.0,
                                     q["loc"][0] + q["wide"][0] * s * q["w"] / 2.0))
             for q in panels for s in (-1.0, 1.0))
    print("  전체 수평 화각 %.2f deg (%+.2f .. %+.2f)" % (hi - lo, lo, hi))


def apply_regions(dcra, panels):
    """DCRA 인스턴스의 뷰포트 Region 과 창 크기를 PANELS 에 맞춘다."""
    import unreal
    cfg = dcra.get_editor_property("current_config_data")
    if cfg is None:
        raise RuntimeError("DCRA 에 current_config_data 가 없다. 에셋 임포트가 실패했는지 확인할 것")
    nodes = cfg.get_editor_property("cluster").get_editor_property("nodes")
    assert len(nodes) == 1, "노드가 %d 개다. 멀티 노드는 아직 지원하지 않는다" % len(nodes)
    node = list(nodes.values())[0]

    want = {viewport_name(q["name"]): q for q in panels}
    have = dict(node.get_editor_property("viewports"))
    missing, extra = [n for n in want if n not in have], [n for n in have if n not in want]
    if missing or extra:
        raise RuntimeError(
            "DCRA 에셋의 뷰포트가 PANELS 와 다름.\n"
            "  에셋에 있는 것: %s\n  PANELS 가 원하는 것: %s\n"
            "  없는 것: %s / 남는 것: %s\n"
            "해결: 콘텐츠 브라우저에서 %s/%s 에셋을 지우고 이 배치 파일을 다시 실행할 것."
            % (sorted(have), sorted(want), missing, extra, ASSET_DIR, ASSET_NAME))

    def rect(x, y, w, h):
        r = unreal.DisplayClusterConfigurationRectangle()
        for k, v in (("x", x), ("y", y), ("w", w), ("h", h)):
            r.set_editor_property(k, int(v))
        return r

    ww, wh = window_size()
    node.set_editor_property("window_rect", rect(WIN_X, WIN_Y, ww, wh))
    for name, q in want.items():
        have[name].set_editor_property("region", rect(*q["region"]))
    unreal.log("viewport regions applied: %s, window %dx%d"
               % (", ".join("%s=%dx%d" % (n, q["rw"], q["rh"]) for n, q in sorted(want.items())),
                  ww, wh))


def build_level():
    import unreal
    # Drop the old actors before the asset, or the import refuses to overwrite
    # an asset that is still referenced ("이 파일이 이미 있습니다").
    # A hand-placed DCRA position wins over RIG_ORIGIN so rebuilds don't undo it.
    panels = place_panels()
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    keep_transform = None
    for a in actors.get_all_level_actors():
        if isinstance(a, unreal.DisplayClusterRootActor):
            keep_transform = (a.get_actor_location(), a.get_actor_rotation())
            actors.destroy_actor(a)
        elif a.get_actor_label().startswith("ANA_"):
            actors.destroy_actor(a)

    asset = "%s/%s" % (ASSET_DIR, ASSET_NAME)
    if not unreal.EditorAssetLibrary.does_asset_exist(asset):
        task = unreal.AssetImportTask()
        task.filename, task.destination_path, task.destination_name = CFG_PATH, ASSET_DIR, ASSET_NAME
        task.automated = task.replace_existing = task.save = True
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    O = unreal.Vector(*RIG_ORIGIN)
    if DEMO_ALCOVE:
        cube = unreal.load_object(None, "/Engine/BasicShapes/Cube.Cube")
        grid = unreal.load_object(None, "/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial")
        x0, y, z = alcove_bounds()
        x1 = max(q["loc"][0] for q in panels) + ALCOVE_DEPTH_CM
        cx, depth, t = (x0 + x1) / 2, x1 - x0, 10.0
        # ponytail: 4 scaled cubes, no interior dressing. Put real content in later by hand.
        # No ceiling: the template's sun/skylight is the interior lighting. A closed
        # box is pitch black inside and auto-exposure turns the output to mush.
        walls = [("back",  (x1, 0, 0),   (t, 2 * y, 2 * z)),
                 ("left",  (cx, -y, 0),  (depth, t, 2 * z)),
                 ("right", (cx,  y, 0),  (depth, t, 2 * z)),
                 ("floor", (cx, 0, -z),  (depth, 2 * y, t))]
        for name, loc, size in walls:
            act = actors.spawn_actor_from_object(cube, unreal.Vector(*loc) + O)
            act.set_actor_label("ANA_" + name)
            act.set_actor_scale3d(unreal.Vector(*[s / 100.0 for s in size]))
            act.static_mesh_component.set_material(0, grid)

        # A few cubes at staggered depths as parallax cues.
        for i, (dx, dy, dz) in enumerate(((120, -25, -10), (200, 20, 5), (280, 0, -20))):
            act = actors.spawn_actor_from_object(cube, unreal.Vector(EYE_DIST_CM + dx, dy, dz) + O)
            act.set_actor_label("ANA_cue%d" % i)
            s = CUE_SIZE_CM / 100.0
            act.set_actor_scale3d(unreal.Vector(s, s, s))

    cls = unreal.load_object(None, "%s/%s.%s_C" % (ASSET_DIR, ASSET_NAME, ASSET_NAME))
    if keep_transform:
        dcra = actors.spawn_actor_from_class(cls, keep_transform[0], keep_transform[1])
        unreal.log("DCRA respawned at its previous position %s (RIG_ORIGIN ignored)" % keep_transform[0])
    else:
        dcra = actors.spawn_actor_from_class(cls, O)
    dcra.set_actor_label(ASSET_NAME)

    # The runtime pulls location/rotation from the config, but the frustum comes
    # from the actual screen mesh, whose scale is baked into the blueprint. Set
    # both on the instance so the knobs above are the single source of truth.
    for c in dcra.get_components_by_class(unreal.DisplayClusterCameraComponent):
        if c.get_name() == EYE_NAME:
            c.set_relative_location(unreal.Vector(0, 0, 0), False, False)

    # 컴포넌트는 에셋 임포트 때 구워진다. PANELS 의 이름/개수를 바꿨으면 에셋을 새로
    # 만들어야 한다. nDisplay 임포트 팩토리가 기존 에셋을 덮어쓰지 못하기 때문.
    have = {c.get_name(): c
            for c in dcra.get_components_by_class(unreal.DisplayClusterScreenComponent)}
    want = [q["name"] for q in panels]
    missing, extra = [n for n in want if n not in have], [n for n in have if n not in want]
    if missing or extra:
        raise RuntimeError(
            "DCRA 에셋의 스크린 컴포넌트가 PANELS 와 다름.\n"
            "  에셋에 있는 것: %s\n  PANELS 가 원하는 것: %s\n"
            "  없는 것: %s / 남는 것: %s\n"
            "해결: 콘텐츠 브라우저에서 %s 에셋을 지우고 이 배치 파일을 다시 실행할 것. "
            "(nDisplay 임포트는 기존 에셋을 덮어쓰지 못한다)"
            % (sorted(have), want, missing, extra, asset))
    for q in panels:
        c = have[q["name"]]
        c.set_relative_location_and_rotation(
            unreal.Vector(*q["loc"]), unreal.Rotator(roll=0.0, pitch=0.0, yaw=q["yaw"]), False, False)
        c.set_relative_scale3d(unreal.Vector(1.0, q["w"], q["h"]))

    # 뷰포트 Region 은 인스턴스 설정에 있다. 무비 렌더 큐는 .ndisplay 파일을 읽지 않고
    # 이 값을 그대로 출력 해상도로 쓴다 (DisplayClusterMovieGraphRenderCameraSource_Math.cpp
    # 의 GetCameraOverscannedResolution -> RenderTargetRect.Size()). 여기서 갱신해 두지
    # 않으면 rw/rh 를 바꿔도 렌더 결과는 에셋을 임포트하던 시점의 크기로 계속 나온다.
    apply_regions(dcra, panels)

    # Save, or the level keeps referencing a stale actor.
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    # 실제 위치를 찍는다. RIG_ORIGIN 을 찍으면 손으로 옮겨 둔 리그일 때 거짓말이 된다.
    unreal.log("anamorphic rig ready: %d panel(s), DCRA at %s = viewer's eye (%s)"
               % (len(panels), dcra.get_actor_location(),
                  "kept from level" if keep_transform else "RIG_ORIGIN"))


if __name__ == "__main__":
    demo()
    os.makedirs(os.path.dirname(CFG_PATH), exist_ok=True)
    with open(CFG_PATH, "w") as f:
        json.dump(build_config(), f, indent=2)
    bat = os.path.join(ROOT, "Run_Anamorphic.bat")
    with open(bat, "w", newline="") as f:
        f.write(build_bat())
    print("wrote " + CFG_PATH + "\nwrote " + bat)
    try:
        import unreal  # noqa: F401
    except ImportError:
        pass
    else:
        build_level()
