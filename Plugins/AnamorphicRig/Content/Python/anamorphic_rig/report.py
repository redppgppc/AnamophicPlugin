"""형상 점검 결과를 사람이 읽을 수 있는 줄로 만든다.

언리얼에 의존하지 않는다. 메뉴에서 호출해 출력 로그에 찍고, 나중에 UI 에도 같은 줄을 쓴다.
"""
import math

from . import config as CF
from . import geometry as G
from . import video as V


def _fmt_m(cm):
    return "%.2f m" % (cm / 100.0)


def sizes(wall, res_w):
    """벽 종류와 무관하게 크기와 비율만 뽑는다. -> 줄 목록.

    영상을 만들어 주는 사람이 실제로 묻는 건 "몇 픽셀짜리로 만들면 되냐" 하나다.
    벽 종류가 뭐든 답은 같은 형식이라 여기 한곳에 모은다.
    """
    W = wall.developed()
    out = ["화면 크기  전개 %s (가로) x %s (세로)" % (_fmt_m(W), _fmt_m(wall.height))]
    out.append("           비율 %.3f : 1  (%s)" % (W / wall.height, _ratio_name(W / wall.height)))
    _, _, ww, wh = CF.screens_and_viewports(wall, res_w)
    out.append("출력 해상도  창 %d x %d px  (비율 %.3f : 1)" % (ww, wh, ww / float(wh)))
    plan = V.Plan(wall)
    out.append("영상 파일    %d x %d px  (비율 %.3f : 1)  <- 영상 변환이 만드는 크기"
               % (plan.out_w, plan.out_h, plan.out_w / float(plan.out_h)))
    if abs(ww / float(wh) - W / wall.height) > 0.02:
        out.append("           주의: 창 비율이 벽 비율과 다름. 화소가 정사각형이 아니다")
    return out


def content_spec(wall, warn_band=60.0):
    """영상 만드는 쪽에 그대로 넘길 숫자. -> (줄 목록, 경고 목록).

    아나모픽 변환은 **벽의 기하만** 되돌린다. 영상 안에 이미 찍혀 있는 원근은 못 고친다.
    그래서 3D 툴에서 콘텐츠를 만들 때 쓰는 카메라 화각이 여기 값과 달라지면
    convert() 가 잘라서 맞추고, 잘린 것은 눈에 띄어도 원근이 어긋난 것은 안 띈다.

    화각은 Xv = y/x 가 탄젠트이므로 경계값에 atan 을 씌워 각도로 되돌린다.
    """
    plan = V.Plan(wall)
    x0, x1, z0, z1, _, aspect, band = plan.plane()
    h_fov = math.degrees(math.atan(x1) - math.atan(x0))
    v_fov = math.degrees(math.atan(z1) - math.atan(z0))
    vw, vh = plan.virtual_size()
    msg, warn = band_warning(band, warn_band)
    out = ["콘텐츠 제작 사양  (영상 만드는 쪽에 그대로 전달할 것)",
           "  카메라 수평 화각  %.2f deg" % h_fov,
           "  카메라 수직 화각  %.2f deg" % v_fov,
           "  권장 렌더 크기    %d x %d px  (비율 %.3f : 1)" % (vw, vh, aspect),
           "  " + msg,
           "  주의: 이 화각으로 만들지 않으면 변환에서 잘리고 원근이 어긋난다"]
    return out, ([warn] if warn else [])


def _ratio_name(r):
    """가장 가까운 흔한 비율 이름. 감이 잡히라고 붙인다."""
    known = [(16 / 9.0, "16:9"), (21 / 9.0, "21:9"), (32 / 9.0, "32:9"),
             (4 / 3.0, "4:3"), (2.35, "시네마스코프"), (1.0, "1:1")]
    best, name = min(((abs(r - k) / k, n) for k, n in known))
    return "%s 에 가까움" % name if best < 0.06 else "%.2f : 1" % r


def summarize(wall, res_w, warn_grazing=20.0, warn_band=60.0, warn_density=2.0):
    """-> (줄 목록, 경고 목록). 경고가 비어 있으면 형상이 쓸 만하다는 뜻."""
    lines, warns = [], []
    W = wall.developed()
    lo, hi = G.span_deg(wall)
    try:
        lines.extend(sizes(wall, res_w) + [""])
        spec, spec_warns = content_spec(wall, warn_band)
        lines.extend(spec + [""])
        warns.extend(spec_warns)
    except ValueError as e:      # 패널마다 높이가 다르면 전개 직사각형이 안 나온다
        lines.append("화면 크기  전개 %s (세로 크기가 패널마다 달라 비율을 낼 수 없음)" % _fmt_m(W))
        warns.append(str(e).split(chr(10))[0])
    lines.append("전개 총길이 %s,  수평 화각 %.2f deg (%+.2f .. %+.2f)" % (_fmt_m(W), hi - lo, lo, hi))

    bad = wall.check()
    warns.extend(bad)

    if isinstance(wall, G.BentWall):
        tb, ta = wall.face_b, wall.face_b + wall.arc_len()
        lines.append("면B %s + 호 %s + 면A %s   (R=%s, %g deg, %s)"
                     % (_fmt_m(wall.face_b), _fmt_m(wall.arc_len()), _fmt_m(wall.face_a),
                        _fmt_m(wall.fillet_r), wall.bend_deg, "볼록" if wall.convex else "오목"))
        g0, g1 = G.grazing_deg(wall, 1e-6), G.grazing_deg(wall, W - 1e-6)
        lines.append("입사각  왼끝 %.1f -> 정점 %.1f -> 오른끝 %.1f deg"
                     % (g0, G.grazing_deg(wall, wall.arc_mid_u()), g1))
        for side, g in (("왼", g0), ("오른", g1)):
            if g < warn_grazing:
                warns.append("%s쪽 끝 입사각 %.1f deg 가 기준 %.0f deg 미만이다. "
                             "그 끝은 픽셀이 가로로 뭉개진다" % (side, g, warn_grazing))
        arc_deg = G.ang_deg(wall.plan_point(ta)) - G.ang_deg(wall.plan_point(tb))
        b_deg = G.ang_deg(wall.plan_point(tb)) - lo
        a_deg = hi - G.ang_deg(wall.plan_point(ta))
        if arc_deg > 1e-9 and b_deg > 1e-9 and a_deg > 1e-9:
            d_arc = wall.arc_len() / arc_deg
            d_b, d_a = wall.face_b / b_deg, wall.face_a / a_deg
            lines.append("화각 배분  면B %.2f + 호 %.2f + 면A %.2f deg" % (b_deg, arc_deg, a_deg))
            lines.append("화소 밀도  호 %.0f cm/deg, 면B %.0f, 면A %.0f (성긴 쪽이 %.1f 배)"
                         % (d_arc, d_b, d_a, max(d_b, d_a) / d_arc))
        if abs(wall.face_b - wall.face_a) > 1e-9:
            lines.append("좌우 면 길이가 다름. 위 좌우 값이 다른 것이 정상")
        if wall.eye_offset_y:
            lines.append("스위트스팟이 축에서 %s 벗어남" % _fmt_m(wall.eye_offset_y))
        lines.append("벽 하단 %s (눈 기준 %s)" % (_fmt_m(wall.base), _fmt_m(wall.base_z())))
    else:
        ww, wh = wall.window_size()
        lines.append("패널 %d 장,  창 %d x %d px" % (len(wall.panels), ww, wh))
        dens = []
        for p in wall.panels:
            a, b = p.span_deg()
            g, d = p.grazing_deg(), p.px_per_cm()
            dens.append(d)
            lines.append("  %-14s %s x %s  %d x %d px  방위 %+.2f..%+.2f  입사각 %.1f  %.2f px/cm"
                         % (p.name, _fmt_m(p.w), _fmt_m(p.h), p.rw, p.rh, a, b, g, d))
            if g < warn_grazing:
                warns.append("%s 의 입사각 %.1f deg 가 기준 %.0f deg 미만" % (p.name, g, warn_grazing))
        if len(dens) > 1 and min(dens) > 0:
            r = max(dens) / min(dens)
            if r >= warn_density:      # 기준 포함. 정확히 2배도 잡는다
                warns.append("패널 간 화소 밀도가 %.1f 배 차이난다 (%.2f ~ %.2f px/cm). "
                             "의도한 게 아니면 해상도나 피치를 확인할 것"
                             % (r, min(dens), max(dens)))
    return lines, warns


def band_warning(band, warn_band=60.0):
    """--curved 변환의 안전 세로 밴드 경고. band 는 (위, 아래) 비율."""
    pct = (band[1] - band[0]) * 100.0
    msg = "안전 세로 밴드 원본 위에서 %.1f%% ~ %.1f%% (%.1f%% 만 사용 가능)" \
        % (band[0] * 100.0, band[1] * 100.0, pct)
    return msg, (None if pct >= warn_band else
                 "세로 밴드가 %.1f%% 뿐이다. 중요한 내용은 이 구간 안에 넣을 것" % pct)
