"""프로젝터 배치 검토. 언리얼에 의존하지 않는다.

LED 는 화소가 벽면에 박혀 있어서 관람자 각도 하나만 보면 된다. 프로젝터는 화소가
프로젝터의 각도 격자에 박혀 있고, 벽에 떨어지는 순간 이미 퍼져 있다. 그것을 관람자가
다시 각도로 압축해서 본다. 왜곡이 두 번 겹치므로 프로젝터 쪽 각도도 따로 봐야 한다.

여기서 답하는 것:
  - 각 대가 담당 구간을 어떤 거리·입사각으로 보는가 (화소가 얼마나 늘어나는가)
  - 필요한 화각은 얼마인가 (렌즈 선정)
  - 겹침이 평면 위에 있는가 (곡률이 점프하는 자리에서 블렌딩하면 안 된다)
  - 두 대의 화소 밀도가 같아지는 곳은 어디인가 (이음매를 둘 자리)

여기서 답하지 않는 것: 실제 워프 맵. 그건 실측 캘리브레이션의 몫이고, 이 계산은
설계 단계에서 배치를 정하는 데 쓴다.
"""
import math

from . import geometry as G


class Projector(object):
    """프로젝터 한 대.

    name     이름
    u0, u1   담당 전개 구간 (cm). 겹침을 포함한, 실제로 빛이 닿는 범위
    back     담당 구간 한가운데의 벽 법선에서 물러난 거리 (cm)
    pos      (x, y) 를 직접 줄 때. back 대신 쓴다
    dz       높이 (리그 원점 = 눈 기준). None 이면 벽 세로 한가운데
    res      (가로, 세로) 화소
    """

    def __init__(self, name, u0, u1, back=3000.0, pos=None, dz=None, res=(3840, 2160)):
        self.name = name
        self.u0, self.u1 = float(u0), float(u1)
        self.back, self.pos, self.dz = float(back), pos, dz
        self.res = (int(res[0]), int(res[1]))
        assert self.u1 > self.u0, "%s 의 담당 구간이 비었다" % name

    def place(self, wall):
        """-> (x, y, z). 리그 원점(눈) 기준."""
        if self.pos is not None:
            x, y = self.pos
        else:
            um = (self.u0 + self.u1) / 2.0
            px, py = wall.plan_point(um)
            nx, ny = wall.plan_normal(um)      # 관람자를 등지는 방향
            x, y = px - nx * self.back, py - ny * self.back
        z = self.dz if self.dz is not None else wall.base_z() + wall.height / 2.0
        return (x, y, z)

    def scan(self, wall, n=400):
        """담당 구간을 훑는다. -> [(u, 거리, 평면입사각, 세로각, 밀도)]

        밀도는 화소 하나가 벽면에서 차지하는 넓이의 역수에 비례한다.
        고정 각도 격자가 벽에 떨어지므로  밀도 ∝ cos(입사각) / 거리^2  이고,
        벽면 법선이 수평이라 세로 성분은 거리에만 들어간다.
        """
        X, Y, Z = self.place(wall)
        zc = wall.base_z() + wall.height / 2.0     # 벽 세로 중앙
        out = []
        for i in range(n + 1):
            u = self.u0 + (self.u1 - self.u0) * i / n
            px, py = wall.plan_point(u)
            nx, ny = wall.plan_normal(u)
            dx, dy, dz = px - X, py - Y, zc - Z
            d = math.sqrt(dx * dx + dy * dy + dz * dz)
            # plan_normal 은 관람자를 등지는 방향이다. 프로젝터도 관람자 쪽에 있으므로
            # 벽을 향하는 광선은 그 법선과 같은 방향을 가리킨다. 양수라야 앞면이다.
            cos = (dx * nx + dy * ny) / d
            inc = math.degrees(math.asin(max(-1.0, min(1.0, cos))))   # 벽면과 이루는 각
            vert = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
            out.append((u, d, inc, vert, (cos / (d * d)) if cos > 0 else 0.0))
        return out

    def fov(self, wall, n=400):
        """-> (수평 화각, 수직 화각) deg. 벽 위아래까지 다 담아야 하는 각."""
        X, Y, Z = self.place(wall)
        zb, zt = wall.base_z(), wall.base_z() + wall.height
        bs, vs = [], []
        for i in range(n + 1):
            u = self.u0 + (self.u1 - self.u0) * i / n
            px, py = wall.plan_point(u)
            dx, dy = px - X, py - Y
            bs.append(math.atan2(dy, dx))
            h = math.hypot(dx, dy)
            vs += [math.atan2(zb - Z, h), math.atan2(zt - Z, h)]
        return (math.degrees(_unwrap_span(bs)), math.degrees(max(vs) - min(vs)))


def frame_fit(res, h_deg, v_deg):
    """고정 종횡비 프레임이 필요 화각을 담을 때 -> (라디안당 화소, 실제 수평, 실제 수직).

    프로젝터는 직사각형 프레임을 쏜다. 필요한 가로 화각과 세로 화각의 비가 프레임
    종횡비와 다르면, 한 축은 딱 맞고 다른 축은 벽 밖으로 넘쳐 그만큼 화소를 버린다.
    벽에 실제로 쓰이는 화소는 넘치는 쪽 기준으로 정해진다.

    가운데 프로젝터처럼 가까이서 넓은 벽을 올려다보는 경우 세로가 묶이는 축이 되어
    가로를 크게 버린다. 그때는 프로젝터를 90도 돌려 세로로 다는 방법이 있다
    (해상도를 2160 x 3840 으로 넣으면 그 계산이 된다).
    """
    A = float(res[0]) / res[1]
    hh, vh = math.radians(h_deg) / 2.0, math.radians(v_deg) / 2.0
    V = max(vh, math.atan(math.tan(hh) / A))     # 세로가 묶이는 축일 수 있다
    H = math.atan(A * math.tan(V))
    return res[0] / (2.0 * H), math.degrees(2.0 * H), math.degrees(2.0 * V)


class ColumnMap(object):
    """프로젝터 화소열 -> 벽 전개 좌표.

    벽이 수직으로 눌린 면이라, 래스터 한 열을 지나는 광선들은 프로젝터를 지나는
    수직 평면 위에 있고 그 평면은 벽과 수직선 하나에서 만난다. 즉 **열 하나가
    전개 좌표 하나에 대응**한다. 세로는 볼 필요가 없다.

    블렌드 알파도, 워프 맵의 가로 성분도 전부 이 대응에서 나온다.
    """

    def __init__(self, wall, proj, samples=2048):
        self.proj = proj
        X, Y, _ = proj.place(wall)
        W = wall.developed()
        # 담당 구간의 방위각을 표로 만든다. 벽이 프로젝터를 감싸지 않는 한 단조다.
        us = [proj.u0 + (proj.u1 - proj.u0) * i / samples for i in range(samples + 1)]
        bs = []
        for u in us:
            px, py = wall.plan_point(u)
            bs.append(math.atan2(py - Y, px - X))
        ub = [bs[0]]
        for b in bs[1:]:
            d = b - ub[-1]
            while d > math.pi:
                d -= 2 * math.pi
            while d < -math.pi:
                d += 2 * math.pi
            ub.append(ub[-1] + d)
        self.us, self.bs = us, ub
        self.rising = ub[-1] > ub[0]
        h, v = proj.fov(wall)
        _, fh, _ = frame_fit(proj.res, h, v)
        mid = (ub[0] + ub[-1]) / 2.0
        half = math.radians(fh) / 2.0
        self.lo, self.hi = mid - half, mid + half     # 프레임이 실제로 덮는 방위각

    def u_of_column(self, px):
        """화소열 px (0 .. res_x-1) 이 닿는 전개 좌표. 벽 밖이면 None."""
        n = self.proj.res[0]
        b = self.lo + (px + 0.5) / n * (self.hi - self.lo)
        return self.u_of_bearing(b)

    def u_of_bearing(self, b):
        bs, us = self.bs, self.us
        if (b < min(bs[0], bs[-1])) or (b > max(bs[0], bs[-1])):
            return None                                  # 담당 구간 밖 (프레임 낭비분)
        lo, hi = 0, len(bs) - 1
        while hi - lo > 1:                                # 표에서 이분 탐색
            m = (lo + hi) // 2
            if (bs[m] <= b) == self.rising:
                lo = m
            else:
                hi = m
        d = bs[hi] - bs[lo]
        f = 0.0 if abs(d) < 1e-12 else (b - bs[lo]) / d
        return us[lo] + (us[hi] - us[lo]) * f

    def column_us(self):
        """전 열의 전개 좌표. 벽 밖은 None."""
        return [self.u_of_column(i) for i in range(self.proj.res[0])]


def _unwrap_span(angles):
    """방위각 목록의 실제 범위. 2pi 를 넘나드는 값을 이어 붙여 잰다."""
    out = [angles[0]]
    for a in angles[1:]:
        d = a - out[-1]
        while d > math.pi:
            d -= 2 * math.pi
        while d < -math.pi:
            d += 2 * math.pi
        out.append(out[-1] + d)
    return max(out) - min(out)


def flat_spans(wall):
    """전개 좌표에서 '평면인 구간' 목록. 겹침을 여기 안에 둬야 한다.

    평면 밖은 곡률이 변하거나(필렛 접점) 법선이 점프하는(패널 이음매) 자리라,
    워프 오차가 가장 커지고 밝기가 끊긴다.
    """
    if isinstance(wall, G.BentWall):
        t1 = wall.face_b
        t2 = t1 + wall.arc_len()
        return [(0.0, t1), (t2, wall.developed())]
    out, t = [], 0.0
    for i, p in enumerate(wall.panels):
        if i:
            t += wall.seams[i - 1].gap
        out.append((t, t + p.w))
        t += p.w
    return out


def in_flat(wall, a, b):
    """구간 [a,b] 가 평면 하나 안에 통째로 들어가는가."""
    return any(s <= a + EPS and b <= e + EPS for s, e in flat_spans(wall))


def density_at(wall, proj, u):
    """한 지점의 밀도만. 교차점 탐색용."""
    X, Y, Z = proj.place(wall)
    zc = wall.base_z() + wall.height / 2.0
    px, py = wall.plan_point(u)
    nx, ny = wall.plan_normal(u)
    dx, dy, dz = px - X, py - Y, zc - Z
    d = math.sqrt(dx * dx + dy * dy + dz * dz)
    cos = (dx * nx + dy * ny) / d      # scan() 과 같은 규약
    return (cos / (d * d)) if cos > 0 else 0.0


def density_crossing(wall, a, b, lo, hi):
    """[lo,hi] 안에서 두 프로젝터의 밀도가 같아지는 u. 없으면 None.

    여기에 겹침 띠 한가운데를 두면 램프가 도는 동안 선명도가 변하지 않는다.
    밀도가 다른 곳에 이음매를 두면 '저 부분만 흐린' 띠가 남는다.
    """
    f = lambda u: density_at(wall, a, u) - density_at(wall, b, u)
    fa, fb = f(lo), f(hi)
    if fa == 0:
        return lo
    if fb == 0:
        return hi
    if fa * fb > 0:
        return None                      # 구간 안에서 안 뒤집힌다
    for _ in range(60):
        m = (lo + hi) / 2.0
        if f(lo) * f(m) <= 0:
            hi = m
        else:
            lo = m
    return (lo + hi) / 2.0


EPS = 0.1      # cm. 값이 m 로 저장됐다 cm 로 돌아오면서 생기는 반올림보다 크고,
               # 어떤 시공 오차보다도 작다. 1 mm 짜리 구멍은 구멍이 아니다.


def coverage(wall, projs):
    """-> (구멍 목록, 겹침 목록). 겹침은 (프로젝터A, 프로젝터B, 시작, 끝)."""
    W = wall.developed()
    ps = sorted(projs, key=lambda p: p.u0)
    gaps, laps = [], []
    reach = 0.0
    for p in ps:
        if p.u0 > reach + EPS:
            gaps.append((reach, p.u0))
        reach = max(reach, p.u1)
    if reach < W - EPS:
        gaps.append((reach, W))
    for i, a in enumerate(ps):
        for b in ps[i + 1:]:
            lo, hi = max(a.u0, b.u0), min(a.u1, b.u1)
            if hi > lo + EPS:
                laps.append((a, b, lo, hi))
    return gaps, laps


def _m(cm):
    return "%.2f m" % (cm / 100.0)


def analyze(wall, projs, warn_grazing=20.0, warn_blend_pct=8.0):
    """배치를 사람이 읽을 수 있는 줄로. -> (줄 목록, 경고 목록)."""
    lines, warns = [], []
    if not projs:
        return ["프로젝터가 정의되지 않았습니다"], []
    W = wall.developed()

    lines.append("전개 총길이 %s,  프로젝터 %d 대" % (_m(W), len(projs)))
    fs = flat_spans(wall)
    lines.append("평면 구간  " + ", ".join("%s ~ %s" % (_m(a), _m(b)) for a, b in fs))
    lines.append("")

    peak = 0.0
    for p in sorted(projs, key=lambda q: q.u0):
        s = p.scan(wall)
        X, Y, Z = p.place(wall)
        lit = [v for v in s if v[4] > 0]
        h, v = p.fov(wall)
        lines.append("%s  담당 %s ~ %s (%s)" % (p.name, _m(p.u0), _m(p.u1), _m(p.u1 - p.u0)))
        lines.append("   위치 (%.1f, %.1f, %.1f) m   해상도 %d x %d"
                     % (X / 100.0, Y / 100.0, Z / 100.0, p.res[0], p.res[1]))
        lines.append("   필요 화각  수평 %.1f°  수직 %.1f°" % (h, v))
        if len(lit) < len(s):
            warns.append("%s 의 담당 구간 일부가 벽 뒷면이다 (빛이 닿지 않는다)" % p.name)
        if not lit:
            lines.append("   !! 담당 구간 전체가 벽 뒷면")
            continue
        ds = [q[4] for q in lit]
        incs = [q[2] for q in lit]
        dist = [q[1] for q in lit]
        scale, fh, fv = frame_fit(p.res, h, v)              # 프레임 종횡비까지 반영
        waste = 100.0 * (1.0 - (h * v) / (fh * fv)) if fh * fv else 0.0
        lines.append("   프레임 %.1f° x %.1f° (%d:%d)  화소 낭비 %.0f%%"
                     % (fh, fv, p.res[0], p.res[1], waste))
        if waste > 40.0:
            warns.append("%s 는 프레임의 %.0f%% 가 벽 밖으로 나간다. 필요 화각의 가로세로 비가 "
                         "%d:%d 와 안 맞는다. 뒤로 물리거나 세로로 돌려 다는 것을 검토할 것"
                         % (p.name, waste, p.res[0], p.res[1]))
        lines.append("   거리 %.1f ~ %.1f m   입사각 %.1f ~ %.1f°   밀도차 %.1f 배"
                     % (min(dist) / 100.0, max(dist) / 100.0,
                        min(incs), max(incs), max(ds) / min(ds)))
        worst = min(lit, key=lambda q: q[4])
        best = max(lit, key=lambda q: q[4])
        for tag, q in (("가장 촘촘", best), ("가장 성김", worst)):
            cm_per_px = q[1] / scale / math.sin(math.radians(q[2])) if scale and q[2] > 0.01 else 0
            lines.append("   %s  u=%s  거리 %.1f m  입사각 %.1f°  가로 화소 %.2f cm"
                         % (tag, _m(q[0]), q[1] / 100.0, q[2], cm_per_px))
            peak = max(peak, 1.0 / cm_per_px if cm_per_px else 0.0)
        if min(incs) < warn_grazing:
            warns.append("%s 의 입사각이 %.1f° 까지 떨어진다 (기준 %.0f°). "
                         "그 구간은 화소가 가로로 %.1f 배 늘어난다"
                         % (p.name, min(incs), warn_grazing,
                            1.0 / math.sin(math.radians(max(0.1, min(incs))))))
        lines.append("")

    gaps, laps = coverage(wall, projs)
    for a, b in gaps:
        warns.append("덮이지 않는 구간: %s ~ %s" % (_m(a), _m(b)))

    if not laps:
        warns.append("겹치는 구간이 없다. 블렌딩할 자리가 없으므로 "
                     "이음매에서 밝기·색 차이를 숨길 수 없다")
    lines.append("겹침 %d 곳" % len(laps))
    for a, b, lo, hi in laps:
        wide = hi - lo
        pct = 100.0 * wide / min(a.u1 - a.u0, b.u1 - b.u0)
        flat = in_flat(wall, lo, hi)
        lines.append("   %s + %s   %s ~ %s  (폭 %s, 좁은 쪽의 %.1f%%)  %s"
                     % (a.name, b.name, _m(lo), _m(hi), _m(wide), pct,
                        "평면 위" if flat else "!! 평면 밖"))
        if not flat:
            warns.append("%s + %s 의 겹침이 평면을 벗어난다. 곡률이 변하는 자리에서 "
                         "블렌딩하면 정렬 오차가 증폭된다" % (a.name, b.name))
        if pct < warn_blend_pct:
            warns.append("%s + %s 의 겹침이 %.1f%% 뿐이다 (기준 %.0f%%). "
                         "알파 램프가 돌 폭이 모자라고 시공 오차를 못 흡수한다"
                         % (a.name, b.name, pct, warn_blend_pct))
        x = density_crossing(wall, a, b, lo, hi)
        if x is None:
            xa = density_crossing(wall, a, b, 0.0, W)
            lines.append("      밀도 교차점이 겹침 안에 없음%s"
                         % ("" if xa is None else "  (전개 %s 에 있음)" % _m(xa)))
            warns.append("%s + %s 의 겹침 구간에서 두 대의 화소 밀도가 교차하지 않는다. "
                         "램프가 도는 동안 선명도가 변해 '그 부분만 흐린' 띠가 남는다"
                         % (a.name, b.name))
        else:
            off = 100.0 * abs(x - (lo + hi) / 2.0) / wide
            lines.append("      밀도 교차점 u=%s  (띠 중심에서 %.0f%% 치우침)" % (_m(x), off))

    if peak:
        lines.append("")
        lines.append("벽 이미지 최소 해상도  가로 %d px 이상 "
                     "(가장 촘촘한 프로젝터를 담아내려면)" % int(peak * W + 0.5))
    return lines, warns


def demo():
    """자체 점검. 언리얼 없이 python -c 로 돌린다."""
    w = G.BentWall(face_b=3653.65, face_a=3653.65, height=2100.0, bend_deg=90.0,
                   fillet_r=250.0, convex=True, eye_dist=3500.0, eye_height=160.0, base=0.0)
    W = w.developed()
    t1, t2 = w.face_b, w.face_b + w.arc_len()

    fs = flat_spans(w)
    assert len(fs) == 2 and abs(fs[0][1] - t1) < 1e-6 and abs(fs[1][0] - t2) < 1e-6, fs
    assert in_flat(w, 100.0, 2000.0) and not in_flat(w, t1 - 100.0, t2 + 100.0)

    # 필렛 전담: 이음매가 접점에 얹히고 겹침이 없다 -> 경고가 나와야 한다
    bad = [Projector("L", 0, t1, back=3000), Projector("M", t1, t2, back=3000),
           Projector("R", t2, W, back=3000)]
    _, wb = analyze(w, bad)
    assert any("겹치는 구간이 없다" in x for x in wb), wb

    # 가로지르기: 겹침이 평면 위에 있어야 한다
    good = [Projector("L", 0, t1 - 600, back=3000),
            Projector("M", t1 - 1200, t2 + 1200, back=3000),
            Projector("R", t2 + 600, W, back=3000)]
    lg, wg = analyze(w, good)
    _, laps = coverage(w, good)
    assert len(laps) == 2, laps
    assert all(in_flat(w, lo, hi) for _, _, lo, hi in laps), "겹침이 평면 밖"
    assert not any("평면을 벗어난다" in x for x in wg), wg

    # 구멍 검출
    hole = [Projector("L", 0, t1 - 600, back=3000), Projector("R", t2 + 600, W, back=3000)]
    _, wh = analyze(w, hole)
    assert any("덮이지 않는 구간" in x for x in wh), wh

    print("projector ok")


if __name__ == "__main__":
    demo()
