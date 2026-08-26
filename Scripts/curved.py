"""Bent corner wall: two flat faces meeting at BEND_DEG with a fillet arc between them.

Standalone:  python Scripts/curved.py    -> nDisplay/Curved_1Screen.ndisplay + Run_Curved.bat
In editor:   Rebuild_Curved.bat          -> builds the warp mesh asset + the rig into Curved.umap

Plan view (top down). World origin = viewer's EYE, +X toward the wall, +Y right, +Z up, cm.

      face B \                       / face A
              \                     /
               \___             ___/
                   \___  arc __/            CONVEX: the arc apex is the NEAREST point
                       \_____/              to the eye and the faces recede.
                          |
                          |  EYE_DIST_CM  (eye -> arc apex)
                          E

round.py's wall is a plane, so an nDisplay Screen component describes it exactly. This one
is not a plane, and a Screen component is always a flat rectangle. So the geometry is baked
into a generated static mesh and the mesh projection policy is pointed at that instead.

The mesh UV IS the output image. u runs along the DEVELOPED length (arc unrolled), which is
how the LED processor addresses the panels: pixels are evenly spaced along the panel surface,
not along its projection. Parameterizing u by projected X would bunch pixels up in the arc.
"""
import json, math, os

# ============================================================================
# [1] python 실행만 하면 되는 값  (python Scripts\curved.py -> Run_Curved.bat)
#     뷰포트/창/카메라만 바뀌는 값. 런타임이 설정 파일에서 다시 읽는다.
# ============================================================================
RES_W = 2560                # 테스트 창 폭. 높이는 전개 종횡비로 자동 계산
WIN_X, WIN_Y = 0, 0
FOLLOW_PLAYER = False       # True: 리그가 플레이어 카메라를 따라감 (콘텐츠 프리뷰용)
BUFFER_RATIO = 1.0          # 내부 렌더 타깃 배율. 면 바깥쪽이 뿌옇게 보이면 1.3 정도로
HIDE_SCREEN_MESSAGES = True   # 좌상단 빨간 엔진 오버레이(StereoView 등)를 끈다.
                              # 주의: 온스크린 경고를 전부 끈다. "Lighting needs to be
                              # rebuilt" 같은 진짜 경고도 안 보인다. 개발 중엔 False 가 안전.

# ============================================================================
# [2] Rebuild_Curved.bat 까지 돌려야 하는 값  (python -> Rebuild_Curved.bat -> bat)
#     워프 메시 자체에 구워지는 값들. 설정 오버라이드는 위치/회전만 갱신하므로
#     아래를 바꾸면 반드시 메시를 다시 만들어야 한다.
# ============================================================================
FACE_B_CM      = 2653.6504591506  # 왼쪽 면(관람자 기준)의 전개 길이. 호는 포함하지 않는다
FACE_A_CM      = 4653.6504591506  # 오른쪽 면의 전개 길이. 좌우가 달라도 된다
                            # 이 기본값은 전개 총길이가 정확히 7700 이 되는 대칭 값이다.
                            # 도면대로 좌우를 다르게 주면 총길이도 따라 바뀐다
# DEVELOPED_W_CM 은 아래에서 FACE_B + 호 + FACE_A 로 유도된다. 직접 고치지 말 것.
SCREEN_H_CM    = 2100.0     # 벽 높이, 21 m
BEND_DEG       = 45.0       # 평면도에서 두 면이 이루는 꺾임 각
FILLET_R_CM    = 250.0      # 필렛 반지름 (지름 5 m)
CONVEX         = True       # True: 코너가 관람자 쪽으로 볼록. False: 관람자가 코너 안쪽에 섬
EYE_DIST_CM    = 3500.0     # 눈 -> 호 정점, **대칭축 방향** 거리 (직선거리가 아님)
EYE_OFFSET_Y_CM = 0.0       # 스위트스팟이 좌우 대칭축에서 벗어난 거리.
                            # + = 관람자 기준 오른쪽(면 A 쪽), - = 왼쪽(면 B 쪽).
                            # 0 이 아니면 좌우 화각/화소밀도/입사각이 비대칭이 된다
EYE_HEIGHT_CM  = 160.0      # 바닥에서 눈높이
SCREEN_BASE_CM = 500.0        # 바닥에서 벽 하단까지. 건물 외벽에 매달린 벽이면 500 (5 m) 등.
                            # 0 = 벽이 바닥에 붙어 있음

ARC_SEG, FACE_SEG, SEG_V = 24, 8, 4   # 워프 메시 분할. 호만 촘촘하면 된다
FLIP_V = True          # 영상이 위아래로 뒤집히면 False
FLIP_WINDING = False   # 벽이 통째로 검게 나오면 True (백페이스 컬링)
VIDEO = "Content/Movies/TestPattern_wall.mp4"
                       # 프로젝트 기준 상대경로. "" = 영상 없음.
                       # 전개 종횡비(77:21) 파일을 쓸 것 (convert_video.py).
                       # --rounded 판은 쓰지 말 것. 여기엔 Output Remap 마스크가 없어서
                       # 검은 라운드가 그대로 벽 네 모서리를 덮는다 (실측 확인함).
                       # 벽보다 앞에 있는 DEMO 큐브는 영상을 뚫고 나온다. 같이 켜지 말 것.
DEMO = False           # 시차 확인용 큐브 + 바닥. 실제 콘텐츠 넣을 땐 False
DEMO_DEPTH_CM = 6000.0
VIDEO_PASSTHROUGH = True   # 영상 1:1 출력. 자동노출과 ACES 톤커브를 꺼서 파일 색이
                           # 그대로 나가게 한다. 3D 콘텐츠를 섞는 맵이면 False.
EXPOSURE_BIAS = 0.0        # 패스스루 노출 보정 EV. 원본 대비 밝기가 어긋나면 조정

RIG_ORIGIN = (0.0, 0.0, EYE_HEIGHT_CM)   # 레벨에 DCRA 가 아직 없을 때의 눈 위치

UE_EXE = r"D:\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
MAP = "/Game/VprodProject/Maps/Curved"
BAT = "Run_Curved.bat"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(ROOT, "nDisplay", "Curved_1Screen.ndisplay")
ASSET_DIR, ASSET_NAME, MESH_NAME = "/Game/Curved", "NDC_Curved", "SM_WallCurved"
# 워프 메시는 Screen 컴포넌트에 실어 보낸다. UDisplayClusterScreenComponent 는
# UStaticMeshComponent 를 상속하므로 mesh 폴리시가 이름으로 그냥 찾아낸다.
# 새 컴포넌트를 블루프린트에 추가하는 것보다 훨씬 적은 코드로 끝난다.
EYE_NAME, SCREEN_NAME = "DefaultViewPoint", "screen_0"

DEVELOPED_W_CM = None       # arc_len() 이 정의된 뒤 아래에서 채운다
RES_H = None


# --- 평면도 형상 ------------------------------------------------------------
def base_z():
    """리그 원점(눈) 기준 벽 하단 높이. 양수면 눈보다 위에 매달려 있다."""
    return SCREEN_BASE_CM - EYE_HEIGHT_CM


def arc_len():
    return math.radians(BEND_DEG) * FILLET_R_CM


def arc_mid_u():
    """호의 한가운데(정점)에 해당하는 전개 좌표. 좌우 면 길이가 다르면 W/2 가 아니다."""
    return FACE_B_CM + arc_len() / 2.0


DEVELOPED_W_CM = FACE_B_CM + arc_len() + FACE_A_CM
RES_H = int(round(RES_W * SCREEN_H_CM / DEVELOPED_W_CM))


def _parts(u):
    """-> (sgn, cx, d, half_arc, half_ang). u 는 전개 좌표, 0 = 관람자 기준 왼쪽 끝."""
    sgn = 1.0 if CONVEX else -1.0
    return (sgn, EYE_DIST_CM + sgn * FILLET_R_CM, u - arc_mid_u(),
            arc_len() / 2.0, math.radians(BEND_DEG) / 2.0)


def plan_point(u):
    """전개 좌표 u -> 평면도 위치 (x, y). 원점은 스위트스팟(눈)이다.
    벽은 물리적으로 고정이므로 스위트스팟이 옆으로 가면 벽 전체가 반대로 밀린 것과 같다."""
    sgn, cx, d, half_arc, half_ang = _parts(u)
    R, off = FILLET_R_CM, EYE_OFFSET_Y_CM
    if abs(d) <= half_arc:
        phi = d / R
        return (cx - sgn * R * math.cos(phi), R * math.sin(phi) - off)
    s = 1.0 if d > 0 else -1.0
    t = abs(d) - half_arc
    return (cx - sgn * R * math.cos(half_ang) + t * sgn * math.sin(half_ang),
            s * (R * math.sin(half_ang) + t * math.cos(half_ang)) - off)


def plan_normal(u):
    """전개 좌표 u -> 관람자를 향하는 면 법선 (x, y), 단위 벡터."""
    sgn, _, d, half_arc, half_ang = _parts(u)
    phi = d / FILLET_R_CM if abs(d) <= half_arc else math.copysign(half_ang, d)
    return (-math.cos(phi), sgn * math.sin(phi))


def column_us():
    """워프 메시의 세로 열 위치. 호에만 분할을 몰아준다. UV 는 u 로 직접 계산하므로
    분할이 균일하지 않아도 등호길이 매개변수화는 그대로 유지된다."""
    tb, ta = FACE_B_CM, FACE_B_CM + arc_len()
    us = [i * tb / FACE_SEG for i in range(FACE_SEG)]
    us += [tb + i * arc_len() / ARC_SEG for i in range(ARC_SEG)]
    us += [ta + i * FACE_A_CM / FACE_SEG for i in range(FACE_SEG + 1)]
    return us


def grazing_deg(u):
    """u 지점을 스위트스팟에서 봤을 때의 입사각. 90 이 정면, 0 이 완전히 스침."""
    (x, y), (nx, ny) = plan_point(u), plan_normal(u)
    m = math.hypot(x, y)
    return math.degrees(math.asin(min(1.0, abs((x * nx + y * ny) / m))))


def geom_key():
    """워프 형상을 결정하는 값 전부. convert_video.py 의 리맵 캐시 키가 이걸 쓴다.
    형상 knob 을 새로 추가하면 반드시 여기에도 넣을 것. 빠뜨리면 낡은 맵이 조용히
    재사용된다."""
    return (FACE_B_CM, FACE_A_CM, SCREEN_H_CM, BEND_DEG, FILLET_R_CM, CONVEX,
            EYE_DIST_CM, EYE_OFFSET_Y_CM, base_z())


def ang_deg(u):
    """u 지점의 방위각. 0 = 리그 정면(+X), + = 오른쪽."""
    x, y = plan_point(u)
    return math.degrees(math.atan2(y, x))


def edge_deg():
    """양 끝의 방위각 (왼쪽 끝, 오른쪽 끝). 대칭이면 부호만 다르다."""
    return ang_deg(0.0), ang_deg(DEVELOPED_W_CM)


def half_fov_deg():
    """전체 수평 화각의 절반. 비대칭일 때도 진짜 절반이지 한쪽 각이 아니다."""
    lo, hi = edge_deg()
    return (hi - lo) / 2.0


# --- 설정 / bat -------------------------------------------------------------
def build_config():
    return {"nDisplay": {
        "description": "Bent %g deg corner wall, r%g fillet, single viewport" % (BEND_DEG, FILLET_R_CM),
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
            # 형상은 메시 정점에 이미 들어 있으므로 스크린은 항등 변환이어야 한다.
            # size 1x1 이라야 임포트 때 컴포넌트 스케일이 1 로 남는다.
            "screens": {SCREEN_NAME: {
                "parentId": "", "location": {"x": 0.0, "y": 0.0, "z": 0.0},
                "rotation": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
                "size": {"width": 1.0, "height": 1.0}}}},
        "cluster": {
            "primaryNode": {"id": "node_0"},
            "sync": {"renderSyncPolicy": {"type": "none", "parameters": {}},
                     "inputSyncPolicy": {"type": "None", "parameters": {}}},
            "nodes": {"node_0": {
                "host": "127.0.0.1", "sound": True, "fullScreen": False,
                "window": {"x": WIN_X, "y": WIN_Y, "w": RES_W, "h": RES_H},
                "viewports": {"vp_0": {
                    "camera": EYE_NAME,
                    "bufferRatio": BUFFER_RATIO,
                    "region": {"x": 0, "y": 0, "w": RES_W, "h": RES_H},
                    "projectionPolicy": {"type": "mesh", "parameters": {
                        "mesh_component": SCREEN_NAME, "base_uv_index": "0"}}}}}},
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


# --- 자체 점검 --------------------------------------------------------------
def demo():
    W, us = DEVELOPED_W_CM, column_us()
    assert FACE_B_CM > 0 and FACE_A_CM > 0, "면 전개 길이는 양수여야 함"
    assert abs(FACE_B_CM + arc_len() + FACE_A_CM - W) < 1e-9, "전개 길이가 맞지 않음"
    tangent = FILLET_R_CM * math.tan(math.radians(BEND_DEG) / 2.0)
    for side, ln in (("B", FACE_B_CM), ("A", FACE_A_CM)):
        assert tangent <= ln, \
            "필렛 접선길이 %.1f 가 면 %s (%.1f) 보다 큼" % (tangent, side, ln)

    apex = plan_point(arc_mid_u())
    assert abs(apex[0] - EYE_DIST_CM) < 1e-9 and abs(apex[1] + EYE_OFFSET_Y_CM) < 1e-9, \
        "호 정점이 EYE_DIST / EYE_OFFSET_Y 와 맞지 않음"

    # 두 면의 방향이 실제로 BEND_DEG 를 이루는지
    a, b = plan_point(W), plan_point(W - 1.0)
    c, d = plan_point(0.0), plan_point(1.0)
    va = math.atan2(a[1] - b[1], a[0] - b[0])
    vb = math.atan2(c[1] - d[1], c[0] - d[0])
    between = math.degrees(abs(va - vb))
    assert abs(min(between, 360 - between) - (180.0 - BEND_DEG)) < 1e-6, \
        "꺾임 각이 BEND_DEG 와 다름: %g" % between

    # UV 가 등호길이 매개변수화인지: 3D 폴리라인 길이 = 전개 길이
    poly = sum(math.dist(plan_point(us[i]), plan_point(us[i + 1])) for i in range(len(us) - 1))
    assert abs(poly - W) / W < 1e-3, "표면 길이 %g != 전개 길이 %g (UV 가 어긋남)" % (poly, W)
    assert us[0] == 0.0 and abs(us[-1] - W) < 1e-9 and all(
        us[i] < us[i + 1] for i in range(len(us) - 1)), "u 가 단조증가 0..W 가 아님"

    # 스위트스팟에서 벽 전체가 보이는지 (법선이 시선을 마주보고, 눈 뒤로 넘어가지 않음)
    for u in us:
        (x, y), (nx, ny) = plan_point(u), plan_normal(u)
        assert x > 0.0, "u=%g 지점이 눈 뒤에 있음 (EYE_DIST 를 키우거나 반대 곡률)" % u
        assert x * nx + y * ny < 0.0, "u=%g 지점의 법선이 관람자를 등짐" % u
        assert abs(math.hypot(nx, ny) - 1.0) < 1e-9

    assert abs(RES_W / RES_H - W / SCREEN_H_CM) < 0.01, "창 종횡비 != 전개 종횡비"
    # 파일이 없으면 벽이 그냥 까맣게 나온다. 레벨 빌드 전에 잡는다.
    assert not VIDEO or os.path.isfile(os.path.join(ROOT, VIDEO)), "VIDEO 파일 없음: " + VIDEO
    cfg = build_config()["nDisplay"]
    vp = cfg["cluster"]["nodes"]["node_0"]["viewports"]["vp_0"]
    assert vp["camera"] in cfg["scene"]["cameras"], "뷰포인트 미정의 (z=50 으로 폴백됨)"
    assert vp["projectionPolicy"]["parameters"]["mesh_component"] in cfg["scene"]["screens"], \
        "mesh_component 가 어떤 컴포넌트도 가리키지 않음"
    win = cfg["cluster"]["nodes"]["node_0"]["window"]
    bat = build_bat()
    assert "ResX=%d" % win["w"] in bat and "WinX=%d" % win["x"] in bat, "bat 와 설정의 창이 불일치"

    # 참고 수치. assert 가 아니라 눈으로 확인하는 값들.
    tb, ta = FACE_B_CM, FACE_B_CM + arc_len()
    lo, hi = edge_deg()
    arc_deg = ang_deg(ta) - ang_deg(tb)
    face_b_deg, face_a_deg = ang_deg(tb) - lo, hi - ang_deg(ta)
    face_deg = min(face_b_deg, face_a_deg)   # 성긴 쪽이 화질을 결정한다
    print("geometry ok")
    print("  전개 %g cm = 면 %.1f + 호 %.1f + 면 %.1f  (R=%g, %g deg, %s)"
          % (W, FACE_B_CM, arc_len(), FACE_A_CM, FILLET_R_CM, BEND_DEG,
             "볼록" if CONVEX else "오목"))
    print("  호 정점 (%.1f, %.1f), 접점 (%.1f, %.1f)/(%.1f, %.1f), 양 끝 (%.1f, %.1f)/(%.1f, %.1f)"
          % (plan_point(arc_mid_u()) + plan_point(tb) + plan_point(ta)
             + plan_point(0.0) + plan_point(W)))
    print("  수평 화각 %.2f deg = 면B %.2f + 호 %.2f + 면A %.2f  (끝 방위 %+.2f .. %+.2f)"
          % (hi - lo, face_b_deg, arc_deg, face_a_deg, lo, hi))
    print("  입사각: 왼끝 %.1f -> 접점 %.1f -> 정점 %.1f -> 접점 %.1f -> 오른끝 %.1f deg"
          % (grazing_deg(1e-6), grazing_deg(tb), grazing_deg(arc_mid_u()),
             grazing_deg(ta), grazing_deg(W - 1e-6)))
    if EYE_OFFSET_Y_CM:
        print("  ** 스위트스팟이 축에서 %+g cm 벗어남. 위 좌우 값이 다른 것이 정상 **"
              % EYE_OFFSET_Y_CM)
    dens_arc = arc_len() / arc_deg
    dens_b, dens_a = FACE_B_CM / face_b_deg, FACE_A_CM / face_a_deg
    print("  화소 밀도: 호 %.0f cm/deg, 면B %.0f, 면A %.0f (성긴 쪽이 %.1f 배)"
          % (dens_arc, dens_b, dens_a, max(dens_b, dens_a) / dens_arc))
    if abs(FACE_B_CM - FACE_A_CM) > 1e-9:
        print("  ** 좌우 면 길이가 다름 (B %.1f / A %.1f). 위 좌우 값이 다른 것이 정상 **"
              % (FACE_B_CM, FACE_A_CM))
    print("  창 %dx%d, 워프 메시 %d x %d 정점" % (RES_W, RES_H, len(us), SEG_V + 1))


# --- 레벨 빌드 --------------------------------------------------------------
def build_mesh_asset():
    """전개 길이로 UV 를 매긴 워프 메시를 만든다. 리그 로컬 좌표 그대로 굽는다."""
    import unreal
    md = unreal.StaticMesh.create_static_mesh_description()
    pg = md.create_polygon_group()
    us = column_us()
    cols = []
    for u in us:
        x, y = plan_point(u)
        col = []
        for j in range(SEG_V + 1):
            f = j / float(SEG_V)
            v = md.create_vertex()
            md.set_vertex_position(v, unreal.Vector(x, y, base_z() + SCREEN_H_CM * f))
            inst = md.create_vertex_instance(v)
            md.set_vertex_instance_uv(
                inst, unreal.Vector2D(u / DEVELOPED_W_CM, (1.0 - f) if FLIP_V else f), 0)
            col.append(inst)
        cols.append(col)

    for i in range(len(us) - 1):
        for j in range(SEG_V):
            a, b, c, d = cols[i][j], cols[i + 1][j], cols[i + 1][j + 1], cols[i][j + 1]
            if FLIP_WINDING:
                b, d = d, b
            md.create_triangle(pg, [a, b, c])
            md.create_triangle(pg, [a, c, d])

    path = "%s/%s" % (ASSET_DIR, MESH_NAME)
    mesh = (unreal.load_object(None, "%s.%s" % (path, MESH_NAME))
            if unreal.EditorAssetLibrary.does_asset_exist(path)
            else unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                MESH_NAME, ASSET_DIR, unreal.StaticMesh, None))
    mesh.build_from_static_mesh_descriptions([md], False, True)
    # nDisplay 는 워프 지오메트리를 CPU 에서 읽는다. 에디터에서는 그냥 되지만 패키징하면
    # GPU 로만 올라가서 워프가 죽는다 (DisplayClusterRender_MeshComponent.cpp:69).
    mesh.set_editor_property("allow_cpu_access", True)
    # 벽은 충돌체가 아니다. 꺼야 GetPhysicsTriMeshData 경고가 사라진다.
    mesh.get_editor_property("body_setup").set_editor_property(
        "collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh)
    unreal.log("warp mesh built: %s (%d columns)" % (path, len(us)))
    return mesh


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
        elif a.get_actor_label().startswith("CRV_"):
            actors.destroy_actor(a)

    mesh = build_mesh_asset()

    asset = "%s/%s" % (ASSET_DIR, ASSET_NAME)
    if not unreal.EditorAssetLibrary.does_asset_exist(asset):
        task = unreal.AssetImportTask()
        task.filename, task.destination_path, task.destination_name = CFG_PATH, ASSET_DIR, ASSET_NAME
        task.automated = task.replace_existing = task.save = True
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    O = unreal.Vector(*RIG_ORIGIN)
    if DEMO:
        cube = unreal.load_object(None, "/Engine/BasicShapes/Cube.Cube")
        grid = unreal.load_object(None, "/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial")
        far = plan_point(DEVELOPED_W_CM)[0] + DEMO_DEPTH_CM
        # ponytail: 바닥 + 뒷벽 + 큐브 몇 개. 실제 콘텐츠는 나중에 손으로.
        for name, loc, size in (
                ("back",  (far, 0, base_z() + SCREEN_H_CM / 2),
                 (20.0, 3 * DEVELOPED_W_CM, 4 * SCREEN_H_CM)),
                ("floor", (far / 2, 0, -EYE_HEIGHT_CM - 10.0),
                 (far, 3 * DEVELOPED_W_CM, 20.0))):
            act = actors.spawn_actor_from_object(cube, unreal.Vector(*loc) + O)
            act.set_actor_label("CRV_" + name)
            act.set_actor_scale3d(unreal.Vector(*[v / 100.0 for v in size]))
            act.static_mesh_component.set_material(0, grid)
        for i, (dx, dy, dz, s) in enumerate(((1200, -1500, 0, 300), (2200, 900, 500, 400),
                                             (3500, -2500, -100, 600), (5000, 2000, 300, 800))):
            act = actors.spawn_actor_from_object(cube, unreal.Vector(EYE_DIST_CM + dx, dy, dz) + O)
            act.set_actor_label("CRV_cue%d" % i)
            act.set_actor_scale3d(unreal.Vector(s / 100.0, s / 100.0, s / 100.0))
            act.static_mesh_component.set_material(0, grid)

    if VIDEO_PASSTHROUGH:
        spawn_passthrough_volume(actors, "CRV_")

    cls = unreal.load_object(None, "%s/%s.%s_C" % (ASSET_DIR, ASSET_NAME, ASSET_NAME))
    dcra = (actors.spawn_actor_from_class(cls, *keep_transform) if keep_transform
            else actors.spawn_actor_from_class(cls, O))
    dcra.set_actor_label(ASSET_NAME)

    for c in dcra.get_components_by_class(unreal.DisplayClusterCameraComponent):
        if c.get_name() == EYE_NAME:
            c.set_relative_location(unreal.Vector(0, 0, 0), False, False)
    hit = False
    for c in dcra.get_components_by_class(unreal.DisplayClusterScreenComponent):
        if c.get_name() == SCREEN_NAME:
            # 형상이 메시에 구워져 있으므로 컴포넌트는 항등 변환이어야 한다.
            c.set_static_mesh(mesh)
            c.set_relative_location_and_rotation(unreal.Vector(0, 0, 0),
                                                 unreal.Rotator(0, 0, 0), False, False)
            c.set_relative_scale3d(unreal.Vector(1.0, 1.0, 1.0))
            hit = True
    if not hit:
        raise RuntimeError("컴포넌트 '%s' 가 DCRA 에 없음. %s 에셋을 지우고 다시 실행할 것"
                           % (SCREEN_NAME, asset))

    if VIDEO:
        # round.py 처럼 평면 플레이트를 쓰면 꺾인 벽에서 최대 6 m 어긋난다. 시선이 벽에
        # 닿는 지점과 플레이트에 닿는 지점이 다르기 때문. 워프 메시를 그대로 한 벌 더
        # 놓으면 UV 가 같으므로 자동으로 1:1 이 된다.
        # DCRA 와 같은 변환에 놓아야 한다. 메시 정점이 리그 로컬 좌표이기 때문.
        plate = actors.spawn_actor_from_class(
            unreal.MediaPlate, dcra.get_actor_location(), dcra.get_actor_rotation())
        plate.set_actor_label("CRV_video")
        comp = plate.get_editor_property("media_plate_component")
        res = unreal.MediaPlateResource()
        res.set_editor_property("type", unreal.MediaPlateResourceType.EXTERNAL)
        res.set_editor_property("external_media_path", os.path.join(ROOT, VIDEO))
        comp.set_editor_property("media_plate_resource", res)
        # 켜져 있으면 영상 종횡비에 맞춰 메시 스케일을 덮어쓴다. 우리 메시는 이미 실측 cm 다.
        comp.set_is_aspect_ratio_auto(False)
        comp.set_editor_property("loop", True)
        # 메시는 생성자에서만 세팅되고 머티리얼은 컴포넌트 오버라이드(슬롯 0)라 그대로 남는다.
        smc = plate.get_editor_property("static_mesh_component")
        smc.set_static_mesh(mesh)
        smc.set_relative_scale3d(unreal.Vector(1.0, 1.0, 1.0))

    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        # 로그에 Error Code 32 = 다른 에디터가 Curved.umap 을 열고 있음.
        raise RuntimeError("Curved.umap 저장 실패 (다른 에디터에서 열려 있는지 확인)")
    unreal.log("curved rig ready: DCRA at %s = viewer's eye (%s)"
               % (dcra.get_actor_location(), "kept from level" if keep_transform else "RIG_ORIGIN"))


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
