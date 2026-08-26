"""nDisplay 설정(.ndisplay) 생성과 클러스터 실행 인자. 언리얼 없이도 돌아간다.

BentWall 은 워프 메시 한 장을 Screen 컴포넌트에 실어 보내므로 뷰포트가 하나다.
PanelChain 은 패널마다 Screen 컴포넌트와 뷰포트를 하나씩 만든다.
"""
import json, os

from . import geometry as G

EYE_NAME = "DefaultViewPoint"
SCREEN_ONE = "screen_0"       # BentWall 의 워프 메시를 싣는 컴포넌트


def viewport_name(screen_name):
    """스크린 이름 -> 뷰포트 이름. 두 곳에서 같은 규칙을 써야 하므로 여기 하나만 둔다."""
    return "vp_" + screen_name.split("_", 1)[-1]


def screens_and_viewports(wall, res_w=2560):
    """-> (screens, viewports, window_w, window_h)

    BentWall: 형상이 메시 정점에 이미 들어 있으므로 스크린은 항등 변환이어야 한다.
              size 1x1 이라야 임포트 때 컴포넌트 스케일이 1 로 남는다.
    """
    if isinstance(wall, G.BentWall):
        h = int(round(res_w * wall.height / wall.developed()))
        screens = {SCREEN_ONE: dict(
            parentId="", location=dict(x=0.0, y=0.0, z=0.0),
            rotation=dict(pitch=0.0, yaw=0.0, roll=0.0), size=dict(width=1.0, height=1.0))}
        vps = {viewport_name(SCREEN_ONE): dict(
            camera=EYE_NAME, region=dict(x=0, y=0, w=res_w, h=h),
            projectionPolicy=dict(type="mesh", parameters=dict(mesh_component=SCREEN_ONE)))}
        return screens, vps, res_w, h

    screens, vps = {}, {}
    for p in wall.panels:
        screens[p.name] = dict(
            parentId="", location=dict(x=p.center[0], y=p.center[1], z=p.dz),
            rotation=dict(pitch=0.0, yaw=p.yaw, roll=0.0),
            size=dict(width=p.w, height=p.h))
        vps[viewport_name(p.name)] = dict(
            camera=EYE_NAME,
            region=dict(x=p.region[0], y=p.region[1], w=p.rw, h=p.rh),
            projectionPolicy=dict(type="mesh", parameters=dict(mesh_component=p.name)))
    assert len(vps) == len(wall.panels), \
        "뷰포트 이름이 충돌한다 (패널 이름의 첫 '_' 뒷부분이 겹침)"
    ww, wh = wall.window_size()
    return screens, vps, ww, wh


def build(wall, asset_path, res_w=2560, win_x=0, win_y=0, follow_player=False):
    """-> (설정 dict, 창 가로, 창 세로)"""
    screens, vps, ww, wh = screens_and_viewports(wall, res_w)
    cfg = {"nDisplay": {
        "description": "Anamorphic Rig: %s" % type(wall).__name__,
        "version": "5.00",
        "assetPath": asset_path,
        # 둘 다 켜야 한다. 안 그러면 런타임이 블루프린트에 마지막으로 임포트된 값을 쓰고
        # 이 파일의 형상을 조용히 무시한다.
        # 스크린 *크기* 는 여전히 블루프린트 전용이다 (UpdateComponentTransformsOnly 는
        # 위치/회전만 세팅한다). 크기가 바뀌면 레벨을 다시 빌드해야 한다.
        "misc": {"bFollowLocalPlayerCamera": bool(follow_player), "bExitOnEsc": True,
                 "bOverrideViewportsFromExternalConfig": True,
                 "bOverrideTransformsFromExternalConfig": True},
        "scene": {
            "cameras": {EYE_NAME: dict(     # 런타임에 리그 원점으로 옮겨진다
                parentId="", location=dict(x=0.0, y=0.0, z=0.0),
                rotation=dict(pitch=0.0, yaw=0.0, roll=0.0),
                interpupillaryDistance=6.4, swapEyes=False, stereoOffset="None")},
            "screens": screens},
        "cluster": {
            "primaryNode": {"id": "node_0"},
            "sync": {"renderSyncPolicy": {"type": "none", "parameters": {}},
                     "inputSyncPolicy": {"type": "None", "parameters": {}}},
            "nodes": {"node_0": {
                "host": "127.0.0.1", "sound": True, "fullScreen": False,
                "window": {"x": win_x, "y": win_y, "w": ww, "h": wh},
                "viewports": vps}}},
    }}
    return cfg, ww, wh


def write(cfg, path):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)
    return path


def launch_args(ue_exe, uproject, map_path, cfg_path, ww, wh,
                win_x=0, win_y=0, hide_screen_messages=True):
    """클러스터 실행 인자.

    창을 실제로 배치하는 것은 WinX/ResX 다. 설정 JSON 의 window 사각형은 창을
    움직이지 못한다 (5.8 의 ResizeWindow 는 死코드).

    작업표시줄은 자동 숨김이어야 한다. 안 그러면 주 모니터 작업 영역이 48px 부족해
    SWindow 가 창을 잘라내고, 요청 크기와 달라진 창을 FSceneViewport::ResizeFrame 이
    다른 모니터 작업 영역 원점으로 재스냅한다.
    """
    args = [ue_exe, uproject, map_path,
            # -dc_dev_mono 는 필수다. 없으면 렌더 디바이스가 아예 생성되지 않고
            # nDisplay 대신 일반 플레이어 카메라가 조용히 보인다.
            "-game", "-dc_cluster", "-dc_dev_mono", "-dc_node=node_0",
            '-dc_cfg=%s' % cfg_path,
            "-windowed", "-forceres",
            "WinX=%d" % win_x, "WinY=%d" % win_y, "ResX=%d" % ww, "ResY=%d" % wh,
            "-nosplash", "-fixedseed", "-NoVerifyGC", "-unattended"]
    if hide_screen_messages:
        args.append('-ExecCmds=DisableAllScreenMessages')
    return args


# --- 자체 점검 --------------------------------------------------------------
def demo():
    w = G.BentWall()
    cfg, ww, wh = build(w, "/Game/X/Y.Y")
    n = cfg["nDisplay"]["cluster"]["nodes"]["node_0"]
    assert (ww, wh) == (2560, 698), (ww, wh)
    assert list(n["viewports"]) == ["vp_0"], list(n["viewports"])
    assert cfg["nDisplay"]["scene"]["screens"][SCREEN_ONE]["size"] == {"width": 1.0, "height": 1.0}

    ch = G.PanelChain([G.Panel("screen_left", 70.8, 39.8, 2560, 1440, dz=-4.6),
                       G.Panel("screen_right", 70.8, 39.8, 2560, 1440, dz=-4.6)],
                      [G.Seam(90.0, convex=True)], eye_dist=60.0, anchor_seam=1)
    cfg, ww, wh = build(ch, "/Game/X/Y.Y")
    n = cfg["nDisplay"]["cluster"]["nodes"]["node_0"]
    assert (ww, wh) == (5120, 1440), (ww, wh)
    assert sorted(n["viewports"]) == ["vp_left", "vp_right"], sorted(n["viewports"])
    assert n["viewports"]["vp_right"]["region"] == {"x": 2560, "y": 0, "w": 2560, "h": 1440}
    for name, s in cfg["nDisplay"]["scene"]["screens"].items():
        assert s["size"] == {"width": 70.8, "height": 39.8}, s
    for v in n["viewports"].values():
        assert v["camera"] in cfg["nDisplay"]["scene"]["cameras"], "뷰포인트 미정의 (z=50 폴백)"
        assert v["projectionPolicy"]["parameters"]["mesh_component"] in \
            cfg["nDisplay"]["scene"]["screens"], "mesh_component 가 어떤 스크린도 안 가리킴"
    args = launch_args("ue.exe", "p.uproject", "/Game/M", "c.ndisplay", ww, wh)
    assert "ResX=%d" % ww in args and "ResY=%d" % wh in args
    print("config ok")


if __name__ == "__main__":
    demo()
