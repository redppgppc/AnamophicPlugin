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


def scale_regions(vps, ww, wh, k):
    """뷰포트 사각형과 창을 같은 비율로 줄인다. 자리에서 고친다.

    미리보기 전용이다. 배치는 그대로 두고 화소 수만 줄인다. res_w 를 줄이는 것으로는
    안 된다. 다중 패널은 창 크기가 패널 해상도에서 나오므로 res_w 를 무시하기 때문이다.
    """
    if k >= 1.0:
        return ww, wh
    for v in vps.values():
        r = v["region"]
        for key in ("x", "y", "w", "h"):
            r[key] = int(round(r[key] * k))
        r["w"], r["h"] = max(1, r["w"]), max(1, r["h"])
    return max(1, int(round(ww * k))), max(1, int(round(wh * k)))


def screens_and_viewports(wall, res_w, scale=1.0):
    """-> (screens, viewports, window_w, window_h)

    BentWall: 형상이 메시 정점에 이미 들어 있으므로 스크린은 항등 변환이어야 한다.
              size 1x1 이라야 임포트 때 컴포넌트 스케일이 1 로 남는다.
    scale:    미리보기용 축소. 스크린(cm)은 그대로 두고 뷰포트 화소만 줄인다.
    """
    if isinstance(wall, G.BentWall):
        h = int(round(res_w * wall.height / wall.developed()))
        screens = {SCREEN_ONE: dict(
            parentId="", location=dict(x=0.0, y=0.0, z=0.0),
            rotation=dict(pitch=0.0, yaw=0.0, roll=0.0), size=dict(width=1.0, height=1.0))}
        vps = {viewport_name(SCREEN_ONE): dict(
            camera=EYE_NAME, region=dict(x=0, y=0, w=res_w, h=h),
            projectionPolicy=dict(type="mesh", parameters=dict(mesh_component=SCREEN_ONE)))}
        return (screens, vps) + scale_regions(vps, res_w, h, scale)

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
    return (screens, vps) + scale_regions(vps, ww, wh, scale)


def _node(x, y, w, h, vps, sound):
    return {"host": "127.0.0.1", "sound": bool(sound), "fullScreen": False,
            "window": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
            "viewports": vps}


def make_nodes(vps, ww, wh, per_node=0):
    """뷰포트를 노드로 나눈다. -> nodes dict

    per_node <= 0 이면 전부 노드 하나에 담는다. 창 하나에 뷰포트 여러 개가 영역으로
    나열되고, LED 프로세서가 그 한 장을 받아 패널로 쪼갠다.

    쪼개면 노드마다 창이 따로 뜬다. 프로세서가 패널별로 입력을 받을 때 쓴다.
    창 위치는 캔버스에서의 자리를 그대로 물려받는다. 확장 데스크톱에서는 그 좌표가
    곧 어느 모니터로 나갈지를 정한다. 노드 안에서는 뷰포트 좌표를 그 창의 원점 기준으로
    다시 잡는다. 창이 달라지면 원점도 달라지기 때문이다.

    소리는 프라이머리만 낸다. 노드마다 켜면 같은 소리가 겹쳐 나온다.
    """
    order = sorted(vps, key=lambda n: (vps[n]["region"]["x"], vps[n]["region"]["y"]))
    if per_node <= 0 or per_node >= len(order):
        return {"node_0": _node(0, 0, ww, wh, vps, True)}
    nodes = {}
    for i in range(0, len(order), per_node):
        group = order[i:i + per_node]
        rs = [vps[n]["region"] for n in group]
        x0, y0 = min(r["x"] for r in rs), min(r["y"] for r in rs)
        w = max(r["x"] + r["w"] for r in rs) - x0
        h = max(r["y"] + r["h"] for r in rs) - y0
        sub = {}
        for n in group:
            v = dict(vps[n])
            r = dict(v["region"])
            r["x"], r["y"] = r["x"] - x0, r["y"] - y0
            v["region"] = r
            sub[n] = v
        idx = len(nodes)
        nodes["node_%d" % idx] = _node(x0, y0, w, h, sub, idx == 0)
    return nodes


def node_order(nodes):
    """node_0, node_1, ... 순서. 프라이머리가 먼저 떠야 나머지가 붙는다."""
    return sorted(nodes, key=lambda n: int(n.rsplit("_", 1)[-1]))


def build(wall, asset_path, res_w, win_x=0, win_y=0,
          follow_player=False, exit_on_esc=True, scale=1.0, per_node=0):
    """-> (설정 dict, 캔버스 가로, 캔버스 세로)

    per_node 로 쪼개면 반환하는 크기는 창 하나가 아니라 전체 캔버스다.
    창 크기는 노드마다 다르므로 nodes[...]["window"] 를 봐야 한다.
    """
    screens, vps, ww, wh = screens_and_viewports(wall, res_w, scale)
    nodes = make_nodes(vps, ww, wh, per_node)
    cfg = {"nDisplay": {
        "description": "Anamorphic Rig: %s" % type(wall).__name__,
        "version": "5.00",
        "assetPath": asset_path,
        # 둘 다 켜야 한다. 안 그러면 런타임이 블루프린트에 마지막으로 임포트된 값을 쓰고
        # 이 파일의 형상을 조용히 무시한다.
        # 스크린 *크기* 는 여전히 블루프린트 전용이다 (UpdateComponentTransformsOnly 는
        # 위치/회전만 세팅한다). 크기가 바뀌면 레벨을 다시 빌드해야 한다.
        "misc": {"bFollowLocalPlayerCamera": bool(follow_player),
                 "bExitOnEsc": bool(exit_on_esc),
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
            # 노드가 여럿이면 소프트웨어 배리어로 프레임을 맞춘다. 안 맞추면 창마다
            # 다른 프레임이 떠서 이음매에서 어긋난다. 현장 하드웨어가 되면 nvidia 로 바꾼다.
            "sync": {"renderSyncPolicy": {
                         "type": "ethernet" if len(nodes) > 1 else "none", "parameters": {}},
                     "inputSyncPolicy": {"type": "None", "parameters": {}}},
            "nodes": nodes},
    }}
    return cfg, ww, wh


def write(cfg, path):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)
    return path


def work_area():
    """주 모니터의 작업 영역 (작업표시줄 제외). -> (가로, 세로) 또는 None.

    ponytail: 주 모니터만 본다. 다른 모니터에 띄우려면 win_x 를 직접 주면 된다.
    """
    try:
        import ctypes
        from ctypes import wintypes
        r = wintypes.RECT()
        SPI_GETWORKAREA = 0x0030
        if not ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(r), 0):
            return None
        return (r.right - r.left, r.bottom - r.top)
    except Exception:
        return None


def monitors():
    """모니터 목록. -> [(x, y, 가로, 세로)] 왼쪽 위부터. 못 구하면 [].

    노드 창을 모니터마다 하나씩 놓을 때 쓴다. 캔버스 좌표대로 이어 붙이면 화소 수가
    모니터 크기와 안 맞아 창 하나가 두 모니터에 걸친다.
    """
    try:
        import ctypes
        from ctypes import wintypes
        got = []
        PROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.POINTER(wintypes.RECT), ctypes.c_longlong)

        def cb(hmon, hdc, lprc, data):
            r = lprc.contents
            got.append((int(r.left), int(r.top),
                        int(r.right - r.left), int(r.bottom - r.top)))
            return 1

        if not ctypes.windll.user32.EnumDisplayMonitors(None, None, PROC(cb), 0):
            return []
        return sorted(got)
    except Exception:
        return []


def place_on_monitors(sizes, mons):
    """노드 창 크기 목록 -> 모니터마다 하나씩 놓은 좌표. 못 놓으면 None.

    규칙 하나로 모니터 개수와 무관하게 돈다: **노드 i 를 모니터 i 안에서 안쪽으로 붙인다.**
    맨 왼쪽 모니터는 오른쪽 끝에, 맨 오른쪽 모니터는 왼쪽 끝에, 가운데 모니터는 가운데에.

    벽은 이어진 한 장이다. 창을 모니터 가운데에 놓으면 경계마다 틈이 생겨 벽이 끊겨
    보인다. 안쪽으로 붙이면 경계에서 맞닿아 이어진다. 패널 화소 수가 모니터 해상도와
    같으면 어느 규칙이든 결과가 같다 (남는 자리가 없다).

    세로는 가운데다. 벽은 가로로만 이어지므로 세로에는 맞출 이음매가 없다.

    순서는 둘 다 왼쪽부터다. 패널 순서와 모니터 배치 순서가 다른 현장은 여기서 못 맞춘다.
    그건 도면이 주는 값이라 노드별 좌표를 직접 받아야 한다. 아직 그 UI 는 없다.
    """
    if not mons or len(mons) < len(sizes):
        return None
    n = len(sizes)
    out = []
    for i, ((w, h), (mx, my, mw, mh)) in enumerate(zip(sizes, mons)):
        # 0 = 맨 왼쪽 -> 오른쪽 끝에 붙임, 1 = 맨 오른쪽 -> 왼쪽 끝에 붙임
        f = 0.5 if n == 1 else i / float(n - 1)
        out.append((mx + int(round(max(0, mw - w) * (1.0 - f))),
                    my + max(0, (mh - h) // 2)))
    return out



def screen_bounds():
    """창을 놓을 영역. -> (가로, 세로) 또는 None.

    모니터가 여럿이면 가상 데스크톱 전체를 쓴다. 주 모니터만 보면 두 번째 창을 놓을
    자리가 없다고 판단해 쓸데없이 줄인다. 현장은 출력이 여러 개인 게 정상이다.
    모니터가 하나면 작업 영역(작업표시줄 제외)을 그대로 쓴다.
    """
    wa = work_area()
    try:
        import ctypes
        u = ctypes.windll.user32
        vw, vh = u.GetSystemMetrics(78), u.GetSystemMetrics(79)   # SM_CX/CYVIRTUALSCREEN
        if vw and vh and wa and (vw > wa[0] or vh > wa[1]):
            return (vw, vh)
    except Exception:
        pass
    return wa


def fit_window(ww, wh, area=None, shrink=True):
    """창을 한 화면 안에 넣는다. -> (가로, 세로, x, y, 배율)

    shrink 를 켜면 **모니터 한 대**에 들어가도록 비율을 지켜 줄이고 가운데에 놓는다.
    벽 전체를 한눈에 보려는 미리보기다. 화소가 줄어드니 선명도 판단용은 아니다.

    기준이 주 모니터의 작업 영역인 것이 중요하다. 가상 데스크톱 전체로 재면 "한 화면에
    담는다" 가 "여러 모니터에 걸쳐 담는다" 가 되어 한 화면 모드가 사라진다.

    끄면 원본 해상도 그대로 두고 화면 원점부터 놓는다. 출력이 여러 개인 현장은 이쪽이다.
    화면 밖으로 나가는 부분은 그 자리에 실제 출력이 있다는 전제다.

    화면 크기를 못 구하면 (0, 0) 에 원본 크기로 둔다.
    """
    if area is None:
        area = work_area()
    if not shrink or not area or not ww or not wh:
        return ww, wh, 0, 0, 1.0     # 원점부터. 현장 출력 좌표와 그대로 맞춘다
    sw, sh = area
    k = min(1.0, float(sw) / ww, float(sh) / wh)
    w, h = int(ww * k), int(wh * k)
    return w, h, max(0, (sw - w) // 2), max(0, (sh - h) // 2), k


def launch_args(ue_exe, uproject, map_path, cfg_path, ww, wh,
                win_x=0, win_y=0, hide_screen_messages=True, node="node_0"):
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
            "-game", "-dc_cluster", "-dc_dev_mono", "-dc_node=%s" % node,
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
    cfg, ww, wh = build(w, "/Game/X/Y.Y", 2560)
    n = cfg["nDisplay"]["cluster"]["nodes"]["node_0"]
    assert (ww, wh) == (2560, 698), (ww, wh)
    assert list(n["viewports"]) == ["vp_0"], list(n["viewports"])
    assert cfg["nDisplay"]["scene"]["screens"][SCREEN_ONE]["size"] == {"width": 1.0, "height": 1.0}
    m = cfg["nDisplay"]["misc"]
    assert m["bFollowLocalPlayerCamera"] is False and m["bExitOnEsc"] is True, m
    m = build(w, "/Game/X/Y.Y", 2560, follow_player=True,
              exit_on_esc=False)[0]["nDisplay"]["misc"]
    assert m["bFollowLocalPlayerCamera"] is True and m["bExitOnEsc"] is False, m

    ch = G.PanelChain([G.Panel("screen_left", 70.8, 39.8, 2560, 1440, dz=-4.6),
                       G.Panel("screen_right", 70.8, 39.8, 2560, 1440, dz=-4.6)],
                      [G.Seam(90.0, convex=True)], eye_dist=60.0, anchor_seam=1)
    cfg, ww, wh = build(ch, "/Game/X/Y.Y", 2560)
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

    # 미리보기 축소는 뷰포트 사각형까지 같이 줄어야 한다. 창만 줄이면 오른쪽 패널이
    # 창 밖으로 나가 안 보인다. 다중 패널은 창 크기가 res_w 와 무관하므로 여기서 잡힌다.
    cfg, ww, wh = build(ch, "/Game/X/Y.Y", 2560, scale=0.5)
    assert (ww, wh) == (2560, 720), (ww, wh)
    r = cfg["nDisplay"]["cluster"]["nodes"]["node_0"]["viewports"]
    assert r["vp_left"]["region"] == {"x": 0, "y": 0, "w": 1280, "h": 720}, r["vp_left"]
    assert r["vp_right"]["region"] == {"x": 1280, "y": 0, "w": 1280, "h": 720}, r["vp_right"]
    for name, s in cfg["nDisplay"]["scene"]["screens"].items():
        assert s["size"] == {"width": 70.8, "height": 39.8}, "스크린 실측(cm)은 안 줄어야 한다"

    # 멀티 노드: 뷰포트마다 창이 따로. 창 안에서 좌표는 원점부터 다시 잡힌다.
    cfg, ww, wh = build(ch, "/Game/X/Y.Y", 2560, per_node=1)
    assert (ww, wh) == (5120, 1440), (ww, wh)      # 반환은 전체 캔버스
    nodes = cfg["nDisplay"]["cluster"]["nodes"]
    assert node_order(nodes) == ["node_0", "node_1"], list(nodes)
    assert nodes["node_0"]["window"] == {"x": 0, "y": 0, "w": 2560, "h": 1440}
    assert nodes["node_1"]["window"] == {"x": 2560, "y": 0, "w": 2560, "h": 1440}
    assert list(nodes["node_0"]["viewports"]) == ["vp_left"]
    assert list(nodes["node_1"]["viewports"]) == ["vp_right"]
    for n in nodes.values():
        r = list(n["viewports"].values())[0]["region"]
        assert (r["x"], r["y"]) == (0, 0), "창 원점 기준으로 다시 잡혀야 한다: %s" % r
    assert nodes["node_0"]["sound"] and not nodes["node_1"]["sound"], "소리는 프라이머리만"
    assert cfg["nDisplay"]["cluster"]["sync"]["renderSyncPolicy"]["type"] == "ethernet"
    assert "-dc_node=node_1" in launch_args("u", "p", "/M", "c", 1, 1, node="node_1")

    # 노드 수가 뷰포트 수 이상이면 안 쪼갠다 (지금까지의 동작)
    assert node_order(build(ch, "/Game/X/Y.Y", 2560, per_node=9)[0]
                      ["nDisplay"]["cluster"]["nodes"]) == ["node_0"]

    # 창 배치: 들어가면 가운데, 넘치면 비율을 지켜 줄이고 가운데
    assert fit_window(800, 600, (1920, 1032)) == (800, 600, 560, 216, 1.0)
    w, h, x, y, k = fit_window(2560, 698, (1920, 1032))
    assert (w, h) == (1920, 523) and k == 0.75, (w, h, k)
    assert x == 0 and y == (1032 - 523) // 2, (x, y)
    assert abs(w / float(h) - 2560 / 698.0) < 0.01, "비율이 바뀌었다"
    # 축소를 끄면 원본 크기 그대로, 화면 원점부터. 현장은 출력이 여러 개다
    assert fit_window(3840, 1440, (2560, 1440), shrink=False) == (3840, 1440, 0, 0, 1.0)
    assert isinstance(monitors(), list)      # 못 구해도 빈 목록이지 예외는 아니다

    # 모니터 배치: 노드 i 를 모니터 i 안에 가운데. 개수와 무관하게 같은 규칙이다.
    two = [(0, 0, 2560, 1440), (2560, 0, 2560, 1440)]
    # 왼쪽 모니터는 오른쪽 끝에 붙어야 오른쪽 창과 경계에서 맞닿는다
    assert place_on_monitors([(1280, 1440), (2560, 1440)], two) == [(1280, 0), (2560, 0)]
    assert place_on_monitors([(2560, 1440), (2560, 1440)], two) == [(0, 0), (2560, 0)]
    three = two + [(5120, 0, 1920, 1080)]
    # 3대: 왼쪽 끝은 우측 정렬, 가운데는 가운데, 오른쪽 끝은 좌측 정렬
    assert place_on_monitors([(1920, 1080)] * 3, three) == [(640, 180), (2880, 180), (5120, 0)]
    assert place_on_monitors([(1, 1)] * 3, two) is None, "모니터가 모자라면 못 놓는다"
    assert place_on_monitors([(1, 1)], []) is None
    print("config ok")


if __name__ == "__main__":
    demo()
