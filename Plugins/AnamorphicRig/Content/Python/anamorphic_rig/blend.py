"""이음매 위치 산출과 알파 블렌드 맵. 언리얼에 의존하지 않는다.

이음매를 어디 둘 것인가에는 조건이 셋 있고, 셋이 항상 같은 자리를 가리키지 않는다.

  1. 평면 위에 있을 것      곡률이 변하는 자리(필렛 접점, 패널 이음매)에서 블렌딩하면
                            워프 오차가 증폭되고 밝기가 끊긴다. 절대 조건이다
  2. 띠 폭을 확보할 것      알파 램프가 돌 물리적 폭 + 시공 오차를 흡수할 여유
  3. 밀도 교차점에 둘 것    두 대의 화소 밀도가 같은 곳이라야 램프가 도는 동안
                            선명도가 변하지 않는다. 다르면 '저 부분만 흐린' 띠가 남는다

suggest_spans 는 1 을 지키면서 2 의 폭을 유지한 채 3 에 최대한 가깝게 민다.
"""
import math
import os

from . import projector as PJ


def _clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def suggest_spans(wall, projs, iters=4):
    """이음매를 밀도 교차점 쪽으로 민다. -> (새 (u0,u1) 목록, 설명 줄).

    겹침 폭은 지금 값을 그대로 유지한다. 폭을 정하는 것은 시공 오차와 알파 램프
    사정이라 계산으로 나오지 않는다. 여기서는 **위치만** 옮긴다.

    담당 구간이 바뀌면 (법선 배치인 경우) 프로젝터 위치도 따라 움직여 밀도가
    달라지므로 몇 번 되풀이한다.
    """
    W = wall.developed()
    ps = sorted(projs, key=lambda p: p.u0)
    spans = [[p.u0, p.u1] for p in ps]
    widths = []
    for i in range(len(ps) - 1):
        widths.append(max(0.0, spans[i][1] - spans[i + 1][0]))
    lines = []

    for it in range(iters):
        live = [PJ.Projector(p.name, spans[i][0], spans[i][1], back=p.back,
                             pos=p.pos, dz=p.dz, res=p.res) for i, p in enumerate(ps)]
        moved = 0.0
        for i in range(len(ps) - 1):
            a, b = live[i], live[i + 1]
            ww = widths[i]
            if ww <= 0:
                continue
            # 두 대의 담당 한가운데 사이에서 밀도 교차점을 찾는다
            lo = (a.u0 + a.u1) / 2.0
            hi = (b.u0 + b.u1) / 2.0
            x = PJ.density_crossing(wall, a, b, lo, hi)
            if x is None:
                if it == 0:
                    lines.append("%s + %s: 두 대의 밀도가 교차하지 않는다. 위치를 못 정한다"
                                 % (a.name, b.name))
                continue
            # 그 교차점을 품는 평면 구간 안으로, 띠가 통째로 들어가게 밀어 넣는다
            flat = _flat_of(wall, x)
            if flat is None:
                flat = _nearest_flat(wall, x)
                lines.append("%s + %s: 밀도 교차점 %.2f m 가 평면 밖이라 가장 가까운 평면으로 옮긴다"
                             % (a.name, b.name, x / 100.0))
            fa, fb = flat
            if fb - fa < ww:
                lines.append("%s + %s: 평면 구간(%.2f m)이 겹침 폭(%.2f m)보다 좁다. "
                             "폭을 줄이거나 배치를 바꿔야 한다"
                             % (a.name, b.name, (fb - fa) / 100.0, ww / 100.0))
                continue
            c = _clamp(x, fa + ww / 2.0, fb - ww / 2.0)
            new_lo, new_hi = c - ww / 2.0, c + ww / 2.0
            moved = max(moved, abs(new_hi - spans[i][1]))
            spans[i][1], spans[i + 1][0] = new_hi, new_lo
        if moved < 0.1:                      # 1 mm 미만이면 수렴한 것으로 본다
            break

    spans[0][0] = 0.0                        # 양 끝은 벽 끝에 고정
    spans[-1][1] = W
    lines.append("%d 회 반복 후 수렴" % (it + 1))
    return [tuple(s) for s in spans], lines


def _flat_of(wall, u):
    for a, b in PJ.flat_spans(wall):
        if a - PJ.EPS <= u <= b + PJ.EPS:
            return (a, b)
    return None


def _nearest_flat(wall, u):
    return min(PJ.flat_spans(wall), key=lambda s: min(abs(u - s[0]), abs(u - s[1])))


# ---------------------------------------------------------------------------
# 알파 블렌드
# ---------------------------------------------------------------------------
def _smooth(t, gamma=1.0):
    """0..1 을 부드럽게. gamma > 1 이면 선명한 쪽이 더 오래 지배한다."""
    t = _clamp(t, 0.0, 1.0)
    s = t * t * (3.0 - 2.0 * t)              # smoothstep
    return s if gamma == 1.0 else s ** gamma


def _feathers(wall, projs):
    """프로젝터마다 (왼쪽 페더 폭, 오른쪽 페더 폭). 이웃이 없으면 0."""
    ps = sorted(projs, key=lambda p: p.u0)
    out = {id(p): [0.0, 0.0] for p in ps}
    for i in range(len(ps) - 1):
        a, b = ps[i], ps[i + 1]
        w = max(0.0, a.u1 - b.u0)
        out[id(a)][1] = w
        out[id(b)][0] = w
    return out


def weights_at(wall, projs, u, gamma=1.0):
    """전개 좌표 u 에서 각 프로젝터의 알파. 합이 1 이 되도록 정규화한다.

    정규화가 핵심이다. 램프 두 개를 그냥 마주 놓으면 합이 1 이 안 되어 겹침 구간이
    밝거나 어둡게 뜬다.
    """
    fe = _feathers(wall, projs)
    raw = []
    for p in projs:
        if not (p.u0 - PJ.EPS <= u <= p.u1 + PJ.EPS):
            raw.append(0.0)
            continue
        lf, rf = fe[id(p)]
        t = 1.0
        if lf > 0:
            t = min(t, (u - p.u0) / lf)
        if rf > 0:
            t = min(t, (p.u1 - u) / rf)
        raw.append(_smooth(t, gamma))
    s = sum(raw)
    return [r / s for r in raw] if s > 0 else raw


def alpha_columns(wall, projs, proj, gamma=1.0, samples=2048):
    """한 대의 화소열별 알파. -> 길이 res_x 리스트. 벽 밖은 0.

    열 -> 전개 좌표는 ColumnMap 이 준다. 벽이 수직으로 눌린 면이라 알파는 열에만
    의존하고 행에는 의존하지 않는다.
    """
    cm = PJ.ColumnMap(wall, proj, samples)
    idx = projs.index(proj)
    out = []
    for u in cm.column_us():
        out.append(0.0 if u is None else weights_at(wall, projs, u, gamma)[idx])
    return out


def write_maps(wall, projs, out_dir, gamma=1.0, log=print):
    """프로젝터마다 알파 맵을 16비트 PGM 으로 쓴다. -> 만든 파일 경로 목록.

    16비트를 쓰는 이유: 블렌드 램프는 밴딩이 가장 잘 보이는 종류의 그라디언트다.
    8비트로는 겹침 구간에 줄무늬가 생긴다.

    행마다 같은 값이라 파일이 크지만(4K 한 장에 16 MB) 그대로 미디어서버나
    ffmpeg 에 넣을 수 있는 게 낫다.
    """
    from .video import _pgm16
    os.makedirs(out_dir, exist_ok=True)
    made = []
    for p in projs:
        cols = alpha_columns(wall, projs, p, gamma)
        row = [int(_clamp(a, 0.0, 1.0) * 65535 + 0.5) for a in cols]
        path = os.path.join(out_dir, "blend_%s.pgm" % _safe(p.name))
        _pgm16(path, p.res[0], p.res[1], (row for _ in range(p.res[1])))
        made.append(path)
        lit = sum(1 for a in cols if a > 0)
        ramp = sum(1 for a in cols if 0.001 < a < 0.999)
        log("%s: %d x %d, 벽에 닿는 열 %d, 램프 구간 %d 열" % (p.name, p.res[0], p.res[1], lit, ramp))
    return made


def _safe(name):
    return "".join(c if (c.isalnum() or c in "_-") else "_" for c in name).strip("_") or "p"


def check_sum(wall, projs, gamma=1.0, n=400):
    """벽 전 구간에서 알파 합이 1 인지. -> (최소, 최대). 1 에서 벗어나면 이음매가 뜬다."""
    W = wall.developed()
    lo, hi = 9.9, 0.0
    for i in range(n + 1):
        u = W * i / n
        s = sum(w for w in weights_at(wall, projs, u, gamma))
        lo, hi = min(lo, s), max(hi, s)
    return lo, hi


def demo():
    """자체 점검."""
    from . import geometry as G
    S = 0.1
    w = G.BentWall(face_b=3653.65 * S, face_a=3653.65 * S, height=2100.0 * S,
                   bend_deg=90.0, fillet_r=250.0 * S, convex=True,
                   eye_dist=3500.0 * S, eye_height=160.0, base=0.0)
    W = w.developed()
    t1 = w.face_b
    t2 = t1 + w.arc_len()
    projs = [PJ.Projector("L", 0, t1 - 30, back=300),
             PJ.Projector("M", t1 - 60, t2 + 60, back=250, res=(2160, 3840)),
             PJ.Projector("R", t2 + 30, W, back=300)]

    lo, hi = check_sum(w, projs)
    assert abs(lo - 1.0) < 1e-9 and abs(hi - 1.0) < 1e-9, (lo, hi)

    # 겹침 한가운데는 반반이어야 한다
    mid = ((t1 - 60) + (t1 - 30)) / 2.0
    ws = weights_at(w, projs, mid)
    assert abs(ws[0] - ws[1]) < 1e-6, ws
    # 겹침 바깥은 한 대가 전부
    ws = weights_at(w, projs, 100.0)
    assert abs(ws[0] - 1.0) < 1e-9, ws

    # gamma 를 올리면 램프가 한쪽으로 기운다 (합은 그대로 1)
    lo, hi = check_sum(w, projs, gamma=2.5)
    assert abs(lo - 1.0) < 1e-9 and abs(hi - 1.0) < 1e-9, (lo, hi)

    # 이음매 산출이 겹침을 평면 안에 두는지
    bad = [PJ.Projector("L", 0, t1 + 20, back=300),
           PJ.Projector("M", t1 - 20, t2 + 20, back=250, res=(2160, 3840)),
           PJ.Projector("R", t2 - 20, W, back=300)]
    spans, _ = suggest_spans(w, bad)
    for i in range(len(spans) - 1):
        lo_, hi_ = spans[i + 1][0], spans[i][1]
        assert hi_ > lo_, (i, spans)
        assert PJ.in_flat(w, lo_, hi_), ("겹침이 평면 밖", i, lo_, hi_)

    print("blend ok")


if __name__ == "__main__":
    demo()
