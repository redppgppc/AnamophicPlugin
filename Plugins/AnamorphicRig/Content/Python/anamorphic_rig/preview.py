"""평면도를 에디터 뷰포트에 디버그 라인으로 그리고, 카메라를 그 위로 옮긴다.

숫자만으로는 배치가 맞는지 확신이 안 선다. 법선이 뒤집혔거나 이음매가 벌어진 건
그림 한 번이면 바로 보인다. 위젯이 필요 없고 파이썬만으로 된다.

주의 두 가지:
  1) DrawDebugLine 은 LifeTime 이 0 보다 커야 **영구 라인 배처**에 들어간다
     (DrawDebugHelpers.cpp 의 GetDebugLineBatcher). 0 이면 에디터 월드에서는
     틱이 안 돌아 사실상 안 보인다.
  2) 그려도 카메라가 딴 데를 보고 있으면 아무것도 안 보인다. 그래서 다 그린 뒤
     전체가 들어오도록 카메라를 위에서 내려다보게 옮긴다.
"""
import math

import unreal

from . import geometry as G

WALL_C = unreal.LinearColor(0.20, 0.85, 0.80, 1.0)     # 벽
SIGHT_C = unreal.LinearColor(0.55, 0.55, 0.60, 1.0)    # 시선
NORMAL_C = unreal.LinearColor(1.00, 0.55, 0.15, 1.0)   # 법선
EYE_C = unreal.LinearColor(1.00, 0.25, 0.25, 1.0)      # 스위트스팟


def _ed():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)


_drawn = [False]     # 평면도가 지금 떠 있는가. 토글에 쓴다.
_saved_cam = []      # 평면도를 그리기 전의 에디터 카메라. 지울 때 되돌린다.


def clear():
    """앞서 그린 평면도를 지우고, 옮겨 뒀던 에디터 카메라를 되돌린다."""
    w = _ed().get_editor_world()
    if w:
        unreal.SystemLibrary.flush_persistent_debug_lines(w)
    _drawn[0] = False
    if _saved_cam:
        loc, rot = _saved_cam.pop()
        _ed().set_level_viewport_camera_info(loc, rot)
        unreal.log("[AnamorphicRig] 에디터 카메라를 원래 위치로 되돌렸습니다")
    _redraw()


def _redraw():
    """뷰포트를 다시 그리게 한다.

    에디터 뷰포트는 실시간 모드가 아니면 무효화될 때만 다시 그린다. 디버그 라인을
    배처에 넣기만 하고 이걸 안 부르면 마우스를 움직이기 전까지 아무것도 안 보인다.
    모달 대화상자 안에서는 틱이 안 돌아 특히 티가 난다.
    """
    unreal.EditorLevelLibrary.editor_invalidate_viewports()


def draw(wall, origin=(0.0, 0.0, 0.0), life=0.0, sight_rays=13, frame=True):
    """리그 원점을 기준으로 평면도를 그린다. origin 은 보통 DCRA 의 월드 위치.

    life 0 = 지울 때까지 남는다 (평면도 보기를 다시 누르거나 clear()).
    frame=True 면 카메라를 위에서 내려다보게 옮긴다.
    """
    world = _ed().get_editor_world()
    if world is None:
        raise RuntimeError("에디터 월드를 못 찾았습니다. 레벨을 하나 열어 주세요")

    # 영구 배처에 들어가려면 LifeTime 이 0 보다 커야 한다. 0 을 주면 아주 길게 잡는다.
    lt = life if life > 0 else 1.0e6
    clear()
    if frame:
        # 카메라를 위에서 내려다보게 옮기기 전에 원래 위치를 기억한다. PlayerStart 가 없으면
        # PIE 가 에디터 카메라 위치에서 시작하므로, 안 되돌리면 하늘에서 시작해 버린다.
        cam = _ed().get_level_viewport_camera_info()
        if cam and len(cam) >= 2:          # 파이썬 바인딩은 (location, rotation) 을 돌려준다
            _saved_cam.append((cam[-2], cam[-1]))

    ox, oy, oz = origin
    W = wall.developed()
    z = oz + (wall.base_z() if isinstance(wall, G.BentWall) else 0.0)
    V = lambda x, y: unreal.Vector(ox + x, oy + y, z)
    line = lambda a, b, c, t: unreal.SystemLibrary.draw_debug_line(world, a, b, c, lt, t)
    text = lambda p, s, c: unreal.SystemLibrary.draw_debug_string(world, p, s, None, c, lt)

    # 벽 크기에 맞춘 굵기. 77 m 벽과 70 cm 모니터를 같은 굵기로 그리면 한쪽은 안 보인다.
    thick = max(1.0, W * 0.004)

    eye = unreal.Vector(ox, oy, z)
    unreal.SystemLibrary.draw_debug_sphere(world, eye, W * 0.012, 12, EYE_C, lt, thick)
    text(eye, "EYE", EYE_C)

    pts = [wall.plan_point(i * W / 256.0) for i in range(257)]
    for a, b in zip(pts, pts[1:]):
        line(V(*a), V(*b), WALL_C, thick * 1.5)

    for i in range(sight_rays):
        p = wall.plan_point(i * W / (sight_rays - 1.0))
        line(eye, V(*p), SIGHT_C, thick * 0.4)
    for u, tag in ((1e-6, "L"), (W / 2.0, "C"), (W - 1e-6, "R")):
        p = wall.plan_point(u)
        text(V(*p), "%s %+.1f deg" % (tag, G.ang_deg(p)), WALL_C)

    # 법선. 관람자를 등지는 방향이라, 화살표가 눈 반대쪽을 가리켜야 정상이다.
    for i in range(sight_rays):
        u = i * W / (sight_rays - 1.0)
        p, nrm = wall.plan_point(u), wall.plan_normal(u)
        t = W * 0.03
        line(V(*p), V(p[0] + nrm[0] * t, p[1] + nrm[1] * t), NORMAL_C, thick)

    if not isinstance(wall, G.BentWall):
        for p in wall.panels:
            for e in p.edges():          # 패널 경계를 세로 눈금으로
                line(V(*e), unreal.Vector(ox + e[0], oy + e[1], z + W * 0.03), WALL_C, thick)
            text(V(*p.center), p.name, WALL_C)

    if frame:
        frame_camera(pts + [(0.0, 0.0)], origin, z)
    _redraw()
    unreal.log("[AnamorphicRig] 평면도를 그렸습니다. 청록=벽, 회색=시선, 주황=법선(눈 반대쪽을 "
               "가리켜야 정상), 빨강=스위트스팟. 지우려면 평면도 보기를 다시 누르세요")
    _drawn[0] = True


def frame_camera(pts, origin, z):
    """평면도 전체가 들어오도록 카메라를 위에서 내려다보게 옮긴다."""
    ox, oy = origin[0], origin[1]
    xs = [ox + p[0] for p in pts]
    ys = [oy + p[1] for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
    # 기본 화각 90도 기준으로 가로/세로가 다 들어오는 높이. 여유 1.4 배.
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    _ed().set_level_viewport_camera_info(
        unreal.Vector(cx, cy, z + span * 1.4),
        unreal.Rotator(roll=0.0, pitch=-90.0, yaw=0.0))


def is_drawn():
    """평면도가 떠 있는가."""
    return _drawn[0]
