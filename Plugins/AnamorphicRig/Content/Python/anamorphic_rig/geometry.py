"""벽 형상 계산. 언리얼에 의존하지 않으므로 일반 python 으로도 돌아간다.

좌표계: 원점 = 관람자의 눈(스위트스팟), +X 정면, +Y 오른쪽, +Z 위. 단위 cm.

두 가지 벽 모델이 있고 둘 다 같은 인터페이스를 낸다.

    PanelChain  평평한 패널 N 장. 이음매마다 꺾임각으로 이어 붙인다.
                패널마다 크기/해상도가 달라도 된다. 떨어진 패널도 된다.
                nDisplay Screen 컴포넌트로 그대로 표현된다.

    BentWall    한 장짜리 연속 벽이 코너에서 둥글게(필렛) 꺾인 형상.
                Screen 은 항상 평면이라 워프 메시를 따로 구워야 한다.
                좌우 면의 전개 길이가 달라도 된다.

공통 인터페이스:
    plan_point(u)   전개 좌표 u -> 평면도 (x, y)
    plan_normal(u)  전개 좌표 u -> 관람자를 등지는 면 법선 (x, y)
    developed()     전개 총길이
"""
import math

__all__ = ["PanelChain", "BentWall", "Panel", "Seam", "ang_deg", "grazing_deg", "demo"]


# --- 공통 도우미 ------------------------------------------------------------
def _dir(deg):
    r = math.radians(deg)
    return math.cos(r), math.sin(r)


def ang_deg(pt):
    """평면도 점의 방위각. 0 = 리그 정면(+X), + = 오른쪽."""
    return math.degrees(math.atan2(pt[1], pt[0]))


def grazing_deg(wall, u):
    """u 지점을 스위트스팟에서 봤을 때의 입사각. 90 이 정면, 0 이 완전히 스침."""
    (x, y), (nx, ny) = wall.plan_point(u), wall.plan_normal(u)
    m = math.hypot(x, y)
    if m < 1e-9:
        return 0.0
    return math.degrees(math.asin(min(1.0, abs((x * nx + y * ny) / m))))


def span_deg(wall, samples=256):
    """벽 전체가 차지하는 방위각 구간 (lo, hi)."""
    W = wall.developed()
    a = [ang_deg(wall.plan_point(i * W / samples)) for i in range(samples + 1)]
    return min(a), max(a)


# ===========================================================================
# 패널 N 장
# ===========================================================================
def even(n):
    """화소 수를 짝수로 올린다.

    h.264 는 4:2:0 크로마 서브샘플링이라 가로세로가 홀수면 **인코더가 아예 안 잡힌다.**
    무비 렌더 큐도 ffmpeg 도 같은 제약을 받는다.

        Failed to initialize Movie Pipeline MP4 writer. An encoder that supports
        the render resolution ... was not found.

    벽에서 1 px 차이는 보이지 않는다. 홀수는 영상이 아예 안 만들어진다. 짝수가 낫다.
    """
    n = int(n)
    return max(2, n + (n & 1))


class Panel(object):
    """평평한 화면 한 장.

    w, h        표시 영역 실측 크기 (cm)
    rw, rh      픽셀 해상도. None 이면 PanelChain 의 pitch 로 유도한다
    dz          패널 세로 중심의 높이, 눈 기준 (+ 가 위)
    region      출력 창 안의 (x, y). None 이면 왼쪽부터 자동 나열
    """

    def __init__(self, name, w, h, rw=None, rh=None, dz=0.0, region=None):
        self.name, self.w, self.h = name, float(w), float(h)
        self.rw, self.rh, self.dz, self.region = rw, rh, float(dz), region
        # 배치 결과. PanelChain.place() 가 채운다.
        self.center = self.heading = self.yaw = None

    @property
    def wide(self):
        """화면 왼쪽 -> 오른쪽 방향의 단위 벡터."""
        return _dir(self.heading)

    def edges(self):
        """평면도에서 이 패널의 (왼쪽 끝, 오른쪽 끝)."""
        (cx, cy), (dx, dy) = self.center, self.wide
        return ((cx - dx * self.w / 2.0, cy - dy * self.w / 2.0),
                (cx + dx * self.w / 2.0, cy + dy * self.w / 2.0))

    def span_deg(self):
        a, b = (ang_deg(e) for e in self.edges())
        return (a, b) if a <= b else (b, a)

    def grazing_deg(self):
        """패널 중심을 스위트스팟에서 봤을 때의 입사각. 90 이 정면, 0 이 완전히 스침.

        전개 좌표를 거치지 않으므로 이음매 틈이 있어도 정확하다."""
        (nx, ny), (cx, cy) = _dir(self.yaw), self.center
        m = math.hypot(cx, cy)
        if m < 1e-9:
            return 0.0
        return math.degrees(math.asin(min(1.0, abs((cx * nx + cy * ny) / m))))

    def px_per_cm(self):
        return self.rw / self.w if self.w else 0.0


class Seam(object):
    """패널 사이의 이음매.

    turn_deg  앞 패널에서 몇 도 꺾이는가. 부호는 convex 가 정한다
    convex    True 면 코너가 관람자 쪽으로 튀어나온다
    gap       앞 패널 끝과의 틈 (cm)
    joined    False 면 다음 패널이 체인에서 떨어져 나가 좌표를 직접 받는다
    """

    def __init__(self, turn_deg=90.0, convex=True, gap=0.0, joined=True):
        self.turn_deg, self.convex = float(turn_deg), bool(convex)
        self.gap, self.joined = float(gap), bool(joined)

    def delta(self):
        """heading 에 더할 실제 증분. 볼록이면 heading 이 줄어든다."""
        return -self.turn_deg if self.convex else self.turn_deg


class PanelChain(object):
    """평평한 패널 N 장. 이음매마다 꺾임각으로 이어 붙인다.

    panels       Panel 리스트, 관람자 기준 왼쪽부터
    seams        Seam 리스트, len(panels) - 1 개
    eye_dist     눈 -> 기준 이음매까지의 정면 방향 거리 (cm)
    anchor_seam  몇 번째 이음매를 정면에 둘지. 0 = 첫 패널 왼쪽 끝,
                 N = 마지막 패널 오른쪽 끝. None = 전개 한가운데
                 (패널 한 장짜리 평면 벽처럼 정면에 둘 이음매가 없을 때)
    rotate_deg   자동 정렬 뒤 전체를 더 돌리고 싶을 때
    pitch_mm     픽셀 피치. Panel 의 rw/rh 가 없으면 여기서 유도
    free         {패널 인덱스: (x, y, yaw)} 떨어진 패널의 직접 좌표
    """

    def __init__(self, panels, seams, eye_dist, anchor_seam=1,
                 rotate_deg=0.0, pitch_mm=None, free=None):
        self.panels = list(panels)
        self.seams = list(seams) if seams else [Seam() for _ in range(len(panels) - 1)]
        self.eye_dist = float(eye_dist)
        self.anchor_seam = None if anchor_seam is None else int(anchor_seam)
        self.rotate_deg, self.pitch_mm = float(rotate_deg), pitch_mm
        self.free = dict(free or {})
        assert self.panels, "패널이 없다"
        assert len(self.seams) == len(self.panels) - 1, \
            "이음매는 패널보다 하나 적어야 한다 (패널 %d, 이음매 %d)" % (len(self.panels), len(self.seams))
        self.place()

    # --- 배치 --------------------------------------------------------------
    def place(self):
        """패널 중심/방향과 출력 리전을 채운다.

        먼저 임시 좌표계에서 체인을 펴고, 앵커 이음매가 (eye_dist, 0) 에 오도록
        통째로 옮긴 뒤 회전한다. 전체 회전의 기본값은 앵커 이음매의 이등분선이
        눈을 향하는 각도라, 대칭 코너면 저절로 정면 대칭이 된다.
        """
        # 1) 임시 좌표계에서 펴기. 첫 패널은 +Y 로 진행 (heading 90 = 평평한 정면 벽).
        cur, heading, seams_xy, moving = (0.0, 0.0), 90.0, [(0.0, 0.0)], True
        for i, p in enumerate(self.panels):
            if i in self.free:
                fx, fy, fyaw = self.free[i]
                p.heading, p.yaw = fyaw + 90.0, fyaw
                p.center = (fx, fy)
                dx, dy = p.wide
                cur, heading, moving = (fx + dx * p.w / 2.0, fy + dy * p.w / 2.0), p.heading, False
            else:
                if i:
                    s = self.seams[i - 1]
                    heading += s.delta()
                    dx, dy = _dir(heading)
                    cur = (cur[0] + dx * s.gap, cur[1] + dy * s.gap)
                dx, dy = _dir(heading)
                p.heading, p.yaw = heading, heading - 90.0
                p.center = (cur[0] + dx * p.w / 2.0, cur[1] + dy * p.w / 2.0)
                cur = (cur[0] + dx * p.w, cur[1] + dy * p.w)
            if moving:
                seams_xy.append(cur)

        # 2) 앵커 지점을 정면 eye_dist 로. 그 지점의 이등분선이 눈을 향하게 회전.
        #    anchor_seam 이 None 이면 전개 한가운데를 쓴다 (패널 한 장짜리 평면 벽 등,
        #    이음매가 정면에 올 수 없는 경우).
        if self.anchor_seam is None:
            ax, ay = self.plan_point(self.developed() / 2.0)   # 임시 좌표계 기준
        else:
            assert 0 <= self.anchor_seam < len(seams_xy), \
                "anchor_seam=%d 는 범위 밖. 0..%d (또는 None = 전체 중앙)" \
                % (self.anchor_seam, len(seams_xy) - 1)
            ax, ay = seams_xy[self.anchor_seam]
        rot = self.rotate_deg - self._anchor_bisector_deg()
        cr, sr = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        for i, p in enumerate(self.panels):
            if i in self.free:
                continue
            x, y = p.center[0] - ax, p.center[1] - ay
            p.center = (self.eye_dist + x * cr - y * sr, x * sr + y * cr)
            p.heading += rot
            p.yaw = p.heading - 90.0

        # 3) 출력 리전
        px = 0
        for p in self.panels:
            if p.rw is None or p.rh is None:
                assert self.pitch_mm, "%s: rw/rh 도 pitch_mm 도 없다" % p.name
                cm = self.pitch_mm / 10.0
                p.rw, p.rh = even(round(p.w / cm)), even(round(p.h / cm))
            if p.region is None:
                p.region = (px, 0)
            px = p.region[0] + p.rw

    def _anchor_bisector_deg(self):
        """앵커 지점에서 양옆 패널이 이루는 각의 이등분선 방향 (임시 좌표계).

        이 방향이 눈을 향하도록 전체를 돌리므로, 대칭 코너면 저절로 정면 대칭이 된다."""
        if self.anchor_seam is None:
            return self._locate(self.developed() / 2.0)[0].yaw
        k = self.anchor_seam
        chained = [i for i in range(len(self.panels)) if i not in self.free]
        before = [i for i in chained if i < k]
        after = [i for i in chained if i >= k]
        if not before:
            return self.panels[after[0]].heading - 90.0 if after else 0.0
        if not after:
            return self.panels[before[-1]].heading - 90.0
        h0, h1 = self.panels[before[-1]].heading, self.panels[after[0]].heading
        return (h0 + h1) / 2.0 - 90.0

    # --- 공통 인터페이스 ---------------------------------------------------
    def developed(self):
        return sum(p.w for p in self.panels) + sum(s.gap for s in self.seams)

    def _locate(self, u):
        t = 0.0
        for i, p in enumerate(self.panels):
            if i:
                t += self.seams[i - 1].gap
            if u <= t + p.w or i == len(self.panels) - 1:
                return p, max(0.0, min(p.w, u - t))
            t += p.w
        raise AssertionError("unreachable")

    def plan_point(self, u):
        p, s = self._locate(u)
        (dx, dy), (cx, cy) = p.wide, p.center
        return (cx + dx * (s - p.w / 2.0), cy + dy * (s - p.w / 2.0))

    def plan_normal(self, u):
        return _dir(self._locate(u)[0].yaw)

    def window_size(self):
        return (max(p.region[0] + p.rw for p in self.panels),
                max(p.region[1] + p.rh for p in self.panels))

    def column_us(self, arc_seg=24, face_seg=8):
        """메시 열을 뽑을 전개 좌표. 평면 패널이라 경계만 있으면 충분하다.

        인자는 BentWall 과 시그니처를 맞추려고 받기만 한다 (곡률이 없으니 쓸 데가 없다).
        틈이 있으면 그 구간은 두 패널 끝을 잇는 다리 한 장이 된다. 영상 플레이트로 쓸 때
        틈에 해당하는 화소가 사라지지 않고 이어져 보이라고 그렇게 둔다.
        """
        us, t = [0.0], 0.0
        for i, p in enumerate(self.panels):
            if i and self.seams[i - 1].gap > 0.0:
                t += self.seams[i - 1].gap
                us.append(t)
            t += p.w
            us.append(t)
        return us

    # --- 영상 변환이 요구하는 것 -------------------------------------------
    # 전개 영상은 직사각형 한 장이라, 벽이 세로로 하나의 띠여야 한다. 패널마다 높이나
    # 세로 위치가 다르면 전개면이 직사각형이 아니게 되므로 여기서 막는다.
    def _uniform(self, get, what):
        vals = [get(p) for p in self.panels]
        if max(vals) - min(vals) > 1e-6:
            raise ValueError(
                "패널마다 %s 가 다르면 영상 변환을 할 수 없다 (%s).\n"
                "전개 영상은 직사각형 한 장이라 벽이 세로로 하나의 띠여야 한다."
                % (what, ", ".join("%s=%.4g" % (p.name, v) for p, v in zip(self.panels, vals))))
        return vals[0]

    @property
    def height(self):
        return self._uniform(lambda p: p.h, "세로 크기")

    def base_z(self):
        """리그 원점(눈) 기준 벽 하단 높이."""
        return self._uniform(lambda p: p.dz, "세로 중심") - self.height / 2.0

    def geom_key(self):
        """형상을 결정하는 값 전부. 영상 리맵 캐시 키가 이걸 쓴다.
        새 knob 을 추가하면 반드시 여기에도 넣을 것."""
        return (tuple((p.name, p.w, p.h, p.rw, p.rh, p.dz, p.center, p.yaw)
                      for p in self.panels),
                tuple((s.turn_deg, s.convex, s.gap) for s in self.seams),
                self.eye_dist, self.anchor_seam, self.rotate_deg)

    def check(self):
        """형상이 물리적으로 말이 되는지. 문제가 있으면 사람이 읽을 수 있는 목록을 낸다."""
        bad = []
        names = [p.name for p in self.panels]
        if len(set(names)) != len(names):
            bad.append("패널 이름이 중복됨: %s" % names)
        for p in self.panels:
            nx, ny = _dir(p.yaw)
            cx, cy = p.center
            if nx * cx + ny * cy <= 0:
                bad.append("%s: 법선이 관람자를 향한다 (화면이 좌우로 뒤집힌다)" % p.name)
            for e in p.edges():
                if e[0] <= 0:
                    bad.append("%s 의 모서리가 눈 뒤에 있다 (x=%.1f). 관람 거리를 키울 것"
                               % (p.name, e[0]))
                    break
        ww, wh = self.window_size()
        for i, a in enumerate(self.panels):
            ax, ay = a.region
            if ax < 0 or ay < 0:
                bad.append("%s 의 출력 위치가 음수" % a.name)
            for b in self.panels[i + 1:]:
                bx, by = b.region
                if ax < bx + b.rw and bx < ax + a.rw and ay < by + b.rh and by < ay + a.rh:
                    bad.append("%s 와 %s 의 출력 영역이 겹침" % (a.name, b.name))
        return bad


# ===========================================================================
# 필렛으로 꺾인 연속 벽
# ===========================================================================
class BentWall(object):
    """면 B - 호 - 면 A. 좌우 면의 전개 길이가 달라도 된다.

    face_b, face_a  각 면의 전개 길이 (cm). 호는 포함하지 않는다
    height          벽 높이 (cm)
    bend_deg        평면도에서 꺾이는 각
    fillet_r        코너 라운드 반지름 (cm)
    convex          True 면 코너가 관람자 쪽으로 볼록
    eye_dist        눈 -> 호 정점, 대칭축 방향 거리 (직선거리가 아님)
    eye_offset_y    스위트스팟이 대칭축에서 벗어난 거리. + 가 오른쪽
    eye_height      바닥에서 눈높이
    base            바닥에서 벽 하단까지
    """

    def __init__(self, face_b, face_a, height, bend_deg, fillet_r, eye_dist, eye_height,
                 convex=True, eye_offset_y=0.0, base=0.0):
        self.face_b, self.face_a, self.height = float(face_b), float(face_a), float(height)
        self.bend_deg, self.fillet_r, self.convex = float(bend_deg), float(fillet_r), bool(convex)
        self.eye_dist, self.eye_offset_y = float(eye_dist), float(eye_offset_y)
        self.eye_height, self.base = float(eye_height), float(base)

    # --- 유도값 ------------------------------------------------------------
    def arc_len(self):
        return math.radians(self.bend_deg) * self.fillet_r

    def arc_mid_u(self):
        """호 한가운데(정점)의 전개 좌표. 좌우 면 길이가 다르면 W/2 가 아니다."""
        return self.face_b + self.arc_len() / 2.0

    def developed(self):
        return self.face_b + self.arc_len() + self.face_a

    def base_z(self):
        """리그 원점(눈) 기준 벽 하단 높이. 양수면 눈보다 위에 매달려 있다."""
        return self.base - self.eye_height

    def _parts(self, u):
        sgn = 1.0 if self.convex else -1.0
        return (sgn, self.eye_dist + sgn * self.fillet_r, u - self.arc_mid_u(),
                self.arc_len() / 2.0, math.radians(self.bend_deg) / 2.0)

    # --- 공통 인터페이스 ---------------------------------------------------
    def plan_point(self, u):
        sgn, cx, d, half_arc, half_ang = self._parts(u)
        R, off = self.fillet_r, self.eye_offset_y
        if abs(d) <= half_arc:
            phi = d / R if R else 0.0
            return (cx - sgn * R * math.cos(phi), R * math.sin(phi) - off)
        s = 1.0 if d > 0 else -1.0
        t = abs(d) - half_arc
        return (cx - sgn * R * math.cos(half_ang) + t * sgn * math.sin(half_ang),
                s * (R * math.sin(half_ang) + t * math.cos(half_ang)) - off)

    def plan_normal(self, u):
        """관람자를 등지는 면 법선. PanelChain 과 부호 규약이 같아야 한다.

        curved.py 원본은 관람자를 향하는 쪽을 돌려줬다. nDisplay Screen 규약
        (로컬 +X = 시선 방향)에 맞추려면 등지는 쪽이라 여기서 뒤집는다.
        """
        sgn, _, d, half_arc, half_ang = self._parts(u)
        phi = (d / self.fillet_r) if (self.fillet_r and abs(d) <= half_arc) \
            else math.copysign(half_ang, d)
        return (math.cos(phi), -sgn * math.sin(phi))

    def column_us(self, arc_seg=24, face_seg=8):
        """워프 메시의 세로 열 위치. 호에만 분할을 몰아준다.

        UV 는 u 로 직접 계산하므로 분할이 균일하지 않아도 등호길이 매개변수화가 유지된다.
        """
        tb, ta = self.face_b, self.face_b + self.arc_len()
        us = [i * tb / face_seg for i in range(face_seg)]
        us += [tb + i * self.arc_len() / arc_seg for i in range(arc_seg)]
        us += [ta + i * self.face_a / face_seg for i in range(face_seg + 1)]
        return us

    def geom_key(self):
        """형상을 결정하는 값 전부. 영상 리맵 캐시 키가 이걸 쓴다.
        형상 knob 을 새로 추가하면 반드시 여기에도 넣을 것."""
        return (self.face_b, self.face_a, self.height, self.bend_deg, self.fillet_r,
                self.convex, self.eye_dist, self.eye_offset_y, self.base_z())

    def check(self):
        bad = []
        if self.face_b <= 0 or self.face_a <= 0:
            bad.append("면 전개 길이는 양수여야 한다")
            return bad
        tangent = self.fillet_r * math.tan(math.radians(self.bend_deg) / 2.0)
        for side, ln in (("B", self.face_b), ("A", self.face_a)):
            if tangent > ln:
                bad.append("필렛 접선길이 %.1f 가 면 %s (%.1f) 보다 크다" % (tangent, side, ln))
        W = self.developed()
        for i in range(65):
            u = i * W / 64.0
            (x, y), (nx, ny) = self.plan_point(u), self.plan_normal(u)
            if x <= 0:
                bad.append("u=%.0f 지점이 눈 뒤에 있다. 관람 거리를 키우거나 곡률을 뒤집을 것" % u)
                break
            if x * nx + y * ny <= 0:
                bad.append("u=%.0f 지점의 법선이 관람자를 향한다 (화면이 좌우로 뒤집힌다)" % u)
                break
        sv = [self.plan_point(i * W / 64.0) for i in range(65)]
        r = [p[1] / p[0] for p in sv]
        if not all(a < b for a, b in zip(r, r[1:])):
            bad.append("가로 매핑이 단조가 아니다 (스위트스팟에서 벽이 접혀 보인다)")
        return bad


# --- 자체 점검 --------------------------------------------------------------
# --- 자체 점검 -------------------------------------------------------------
# 아래 치수는 indoor_1_10 프리셋에서 가져온 **테스트 데이터**다. 야외 77 m 벽의 1/10 이고,
# 각도가 축척에 안 변해서 같은 결론이 나온다. 클래스 기본값으로 두지 않는 이유는,
# 설정을 안 넘겨도 그럴듯한 벽이 나오면 틀린 것을 못 알아채기 때문이다.
DEMO_WALL = dict(face_b=3653.6504591506, face_a=3653.6504591506, height=2100.0,
                 bend_deg=90.0, fillet_r=250.0, eye_dist=3500.0, eye_height=160.0)


def demo_wall(**kw):
    """예시 치수로 만든 BentWall. 바꾸고 싶은 것만 키워드로 준다."""
    d = dict(DEMO_WALL)
    d.update(kw)
    return BentWall(**d)


def demo():
    # 1) 볼록 90도 대칭 코너: 두 모델이 같은 평면도를 내야 한다.
    ch = PanelChain([Panel("L", 70.8, 39.8, 2560, 1440, dz=-4.6),
                     Panel("R", 70.8, 39.8, 2560, 1440, dz=-4.6)],
                    [Seam(90.0, convex=True)], eye_dist=60.0, anchor_seam=1)
    assert not ch.check(), ch.check()
    lo, hi = span_deg(ch)
    assert abs(lo + 24.46) < 0.01 and abs(hi - 24.46) < 0.01, "화각이 기존 리그와 다름: %g..%g" % (lo, hi)
    assert ch.window_size() == (5120, 1440), ch.window_size()
    for p, want in zip(ch.panels, ((85.03, -25.03, 45.0), (85.03, 25.03, -45.0))):
        assert abs(p.center[0] - want[0]) < 0.01 and abs(p.center[1] - want[1]) < 0.01 \
            and abs(p.yaw - want[2]) < 1e-9, "%s: %s %s" % (p.name, p.center, p.yaw)

    # 2) 좌우 크기가 다른 코너
    ch2 = PanelChain([Panel("L", 2000, 1200, 1920, 1152),
                      Panel("R", 3600, 1200, 3456, 1152)],
                     [Seam(90.0, convex=True, gap=30.0)], eye_dist=3500.0, anchor_seam=1)
    assert not ch2.check(), ch2.check()
    assert ch2.window_size() == (5376, 1152), ch2.window_size()
    a, b = ch2.panels[0].span_deg(), ch2.panels[1].span_deg()
    assert abs(a[0] + 16.05) < 0.02 and abs(b[1] - 22.93) < 0.02, (a, b)

    # 3) 피치에서 해상도 유도
    ch3 = PanelChain([Panel("L", 1000, 600), Panel("R", 2000, 600)],
                     [Seam(90.0)], eye_dist=3500.0, pitch_mm=7.8)
    assert (ch3.panels[0].rw, ch3.panels[1].rw) == (1282, 2564), \
        (ch3.panels[0].rw, ch3.panels[1].rw)

    # 4) 평평한 벽 = 패널 한 장
    flat = PanelChain([Panel("W", 7700, 2100, 3840, 1048)], [], eye_dist=3500.0, anchor_seam=None)
    assert not flat.check(), flat.check()
    lo, hi = span_deg(flat)
    assert abs((hi - lo) - 95.45) < 0.05, hi - lo

    # 5) 꺾인 벽: 등호길이 매개변수화와 좌우 비대칭
    for fb, fa in ((3653.6504591506, 3653.6504591506), (2500.0, 4800.0), (5500.0, 1200.0)):
        w = demo_wall(face_b=fb, face_a=fa)
        assert not w.check(), (fb, fa, w.check())
        us = w.column_us()
        poly = sum(math.dist(w.plan_point(us[i]), w.plan_point(us[i + 1]))
                   for i in range(len(us) - 1))
        assert abs(poly - w.developed()) / w.developed() < 1e-3, \
            "표면 길이 %g != 전개 길이 %g" % (poly, w.developed())
        apex = w.plan_point(w.arc_mid_u())
        assert abs(apex[0] - w.eye_dist) < 1e-9 and abs(apex[1] + w.eye_offset_y) < 1e-9, apex
    assert abs(demo_wall().developed() - 7700.0) < 1e-6, demo_wall().developed()

    # 6) 거부되어야 하는 형상
    assert demo_wall(face_b=100.0).check(), "필렛이 면보다 큰데 통과함"
    assert demo_wall(eye_offset_y=-3500.0).check(), "벽이 접히는데 통과함"
    bad = PanelChain([Panel("L", 70.8, 39.8, 100, 100), Panel("R", 70.8, 39.8, 100, 100)],
                     [Seam(90.0, convex=False)], eye_dist=30.0, anchor_seam=1)
    assert bad.check(), "패널이 눈 뒤에 있는데 통과함"

    # 영상 변환 인터페이스: 균일하면 되고, 다르면 막아야 한다.
    uni = PanelChain([Panel("L", 2000, 1200, 1920, 1152), Panel("R", 3600, 1200, 3456, 1152)],
                     [Seam(90.0)], eye_dist=3500.0, anchor_seam=1)
    assert abs(uni.height - 1200) < 1e-9 and abs(uni.base_z() + 600) < 1e-9, \
        (uni.height, uni.base_z())
    assert uni.geom_key() != PanelChain(
        [Panel("L", 2000, 1200, 1920, 1152), Panel("R", 3600, 1200, 3456, 1152)],
        [Seam(60.0)], eye_dist=3500.0, anchor_seam=1).geom_key(), "캐시 키가 꺾임각을 구분 못 함"
    mixed = PanelChain([Panel("L", 2000, 1200, 1920, 1152), Panel("R", 3600, 900, 3456, 864)],
                       [Seam(90.0)], eye_dist=3500.0, anchor_seam=1)
    try:
        mixed.height
        raise AssertionError("높이가 다른데 통과함")
    except ValueError:
        pass

    # 두 모델의 법선 부호 규약이 같아야 한다. 평면도의 주황 화살표가 반대로 나오면
    # 화면이 좌우로 뒤집힌 것으로 오해하게 된다.
    for w in (PanelChain([Panel('L', 2000, 1200, 1920, 1152),
                          Panel('R', 2000, 1200, 1920, 1152)],
                         [Seam(90.0)], eye_dist=3500.0, anchor_seam=1),
              demo_wall(), demo_wall(face_b=2500, face_a=4800), demo_wall(convex=False)):
        W = w.developed()
        for i in range(1, 8):
            u = i * W / 8.0
            (x, y), (nx, ny) = w.plan_point(u), w.plan_normal(u)
            assert x * nx + y * ny > 0, \
                '%s u=%.0f: 법선이 관람자를 향한다 (등져야 함)' % (type(w).__name__, u)

    print("geometry ok")


if __name__ == "__main__":
    demo()
