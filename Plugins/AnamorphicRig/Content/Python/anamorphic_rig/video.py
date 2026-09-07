"""영상 변환. ffmpeg 만 쓰므로 언리얼 없이도 돌아간다.

세 가지 산출물이 있고 서로 대체할 수 없다.

  wall     전개 직사각형에 맞춘 것. 벽지처럼 붙는다. 꺾인 벽에서는 코너에서 그림이 접힌다.
           관람 시점이 정해지지 않은 평범한 LED 벽이 원하는 것.

  curved   아나모픽 사전 왜곡. 스위트스팟에 선 사람에게 평평하게 보이도록 미리 찌그러뜨린다.
           코엑스 파도 효과. 스위트스팟에서만 정확하고, 다른 위치에서는 wall 보다 더 이상하다.

  preview  curved 의 역방향. 벽 없이 착시가 맞는지 눈으로 확인하는 검증용.
           벽에 넣는 파일이 아니다.

형상은 geometry 객체에서 그대로 읽으므로 벽 설정이 바뀌면 변환도 따라 바뀐다.
"""
import hashlib, math, os, shutil, subprocess, tempfile
from array import array

CURVED_SS = 2      # remap 은 최근접 샘플링뿐이라, 크게 뜬 뒤 줄여서 계단을 없앤다
SAMPLES = 4096     # 투영 경계를 재는 표본 수
OUTSIDE = 65535    # remap 이 fill 색으로 칠하도록 넣는 범위 밖 값


class Plan(object):
    """벽 하나에 대한 변환 계획. 출력 크기와 투영 경계를 한 번만 재서 들고 있는다."""

    def __init__(self, wall, out_w, virt_w=0):
        self.wall, self.out_w, self.virt_w = wall, int(out_w), int(virt_w)
        h = int(round(self.out_w * wall.height / wall.developed()))
        self.out_h = h - h % 2                          # yuv420 은 짝수 높이가 필요
        assert self.out_h > 0, "출력 높이가 0 이다. 벽 크기를 확인할 것"
        self._plane = None

    # --- 투영 경계 ---------------------------------------------------------
    def plane(self):
        """벽을 스위트스팟에서 봤을 때의 투영 경계.

        -> (x0, x1, z0, z1, mag, aspect, band)
        관람 거리는 정규화에서 상쇄되므로 1 로 두고 계산한다. 즉 화면 좌표는
        Xv = y/x, Zv = z/x 로 끝난다.
        band 는 벽 어느 지점에서도 잘리지 않는 세로 구간 (원본 위에서부터의 비율).
        """
        if self._plane:
            return self._plane
        w = self.wall
        W, H = w.developed(), w.height
        zt, zb = w.base_z() + H, w.base_z()
        pts = [w.plan_point(i * W / SAMPLES) for i in range(SAMPLES + 1)]
        xv = [y / x for x, y in pts]
        x0, x1 = min(xv), max(xv)
        z0 = min(zb / x for x, _ in pts)
        z1 = max(zt / x for x, _ in pts)
        d = W / SAMPLES

        def s(u):
            x, y = w.plan_point(u)
            return (y / x - x0) / (x1 - x0)

        mag = max((2 * d / W) / (s(W - d) - s(W - 3 * d)),
                  (2 * d / W) / (s(3 * d) - s(d)))
        band = ((z1 - min(zt / x for x, _ in pts)) / (z1 - z0),
                (z1 - max(zb / x for x, _ in pts)) / (z1 - z0))
        self._plane = (x0, x1, z0, z1, mag, (x1 - x0) / (z1 - z0), band)
        return self._plane

    def virtual_size(self):
        """가상 평면 래스터 크기. 벽 양 끝이 1:1 이 되도록 잡는다."""
        _, _, _, _, mag, aspect, _ = self.plane()
        vw = self.virt_w or round(self.out_w * mag / 2) * 2
        return vw, round(vw / aspect / 2) * 2

    def _key(self, *extra):
        return hashlib.md5(repr(self.wall.geom_key() + (self.out_w, self.out_h) + extra)
                           .encode()).hexdigest()[:12]

    # --- 리맵 맵 -----------------------------------------------------------
    def warp_maps(self):
        """벽 픽셀 -> 가상 평면 픽셀 좌표 맵 두 장. TEMP 에 캐시하고 경로를 돌려준다.

        Xv 는 열에만, Zv 는 z * (1/x) 의 외적 구조라 열별 1/x 를 미리 잡아 두면
        행마다 곱셈 한 번으로 끝난다. numpy 없이도 견딜 만하다.
        """
        w = self.wall
        W, H = w.developed(), w.height
        zt = w.base_z() + H
        x0, x1, z0, z1, _, _, _ = self.plane()
        vw, vh = self.virtual_size()
        mw, mh = self.out_w * CURVED_SS, self.out_h * CURVED_SS

        key = self._key(mw, mh, vw, vh, "warp")
        xm = os.path.join(tempfile.gettempdir(), "arwarp_%s_x.pgm" % key)
        ym = os.path.join(tempfile.gettempdir(), "arwarp_%s_y.pgm" % key)
        if os.path.exists(xm) and os.path.exists(ym):
            return xm, ym, vw, vh

        cols = [w.plan_point((px + 0.5) / mw * W) for px in range(mw)]
        kx, kz = (vw - 1) / (x1 - x0), (vh - 1) / (z1 - z0)
        cx = lambda v: 0 if v < 0 else (vw - 1 if v > vw - 1 else v)
        cz = lambda v: 0 if v < 0 else (vh - 1 if v > vh - 1 else v)
        _pgm16(xm, mw, mh, [[cx(int((y / x - x0) * kx + 0.5)) for x, y in cols]] * mh)
        invx = [1.0 / x for x, _ in cols]

        def yrow(py):
            zk = (zt - (py + 0.5) / mh * H) * kz
            b = z1 * kz + 0.5
            return [cz(int(b - zk * ix)) for ix in invx]

        _pgm16(ym, mw, mh, (yrow(py) for py in range(mh)))
        return xm, ym, vw, vh

    def eye_maps(self, pw, ph):
        """warp 의 역방향. 전개 영상 -> 스위트스팟에 선 사람이 볼 그림."""
        w = self.wall
        W, H = w.developed(), w.height
        zt, zb = w.base_z() + H, w.base_z()
        x0, x1, z0, z1, _, _, _ = self.plane()

        key = self._key(pw, ph, "eye")
        xm = os.path.join(tempfile.gettempdir(), "areye_%s_x.pgm" % key)
        ym = os.path.join(tempfile.gettempdir(), "areye_%s_y.pgm" % key)
        if os.path.exists(xm) and os.path.exists(ym):
            return xm, ym

        # 시선 방향 Xv 를 주면 벽의 어느 전개 위치인지. y/x 가 u 에 대해 단조라 이분법으로 푼다.
        def solve_u(xv):
            lo, hi = 0.0, W
            for _ in range(60):
                mid = (lo + hi) / 2.0
                px, py = w.plan_point(mid)
                if py / px < xv:
                    lo = mid
                else:
                    hi = mid
            return (lo + hi) / 2.0

        us = [solve_u(x0 + (px + 0.5) / pw * (x1 - x0)) for px in range(pw)]
        xs = [w.plan_point(u)[0] for u in us]
        _pgm16(xm, pw, ph, [[min(self.out_w - 1, int(u / W * self.out_w)) for u in us]] * ph)

        def yrow(py):
            zv = z1 - (py + 0.5) / ph * (z1 - z0)
            row = []
            for x in xs:
                z = zv * x                     # 그 방향의 시선이 벽면과 만나는 높이
                row.append(OUTSIDE if not (zb <= z <= zt)   # 그 방향엔 벽이 없다
                           else min(self.out_h - 1, int((zt - z) / H * self.out_h)))
            return row

        _pgm16(ym, pw, ph, (yrow(py) for py in range(ph)))
        return xm, ym


class ProjectorPlan(object):
    """프로젝터 한 대의 최종 리맵 맵. 두 왜곡을 하나로 합친다.

        프로젝터 픽셀 -> 벽 전개 좌표 -> 가상 평면 픽셀

    두 단계를 따로 두면 사이에 '벽 이미지'가 실체로 있어야 하고, 프로젝터가 벽에
    만드는 밀도를 담아내려면 그게 1만 픽셀을 훌쩍 넘는다. 파이썬에서 맵을 합성하면
    그 중간 래스터가 디스크에도 메모리에도 생기지 않고 양자화 손실도 없다.

    배치를 바꾸면 맵만 다시 구우면 된다 (수 초). 영상은 어차피 다시 인코딩해야 하므로
    나눠 두는 이점이 없다.
    """

    def __init__(self, wall, proj, plan):
        from . import projector as PJ
        self.wall, self.proj, self.plan = wall, proj, plan
        self.col = PJ.ColumnMap(wall, proj)
        self.X, self.Y, self.Z = proj.place(wall)
        h, v = proj.fov(wall)
        _, _, fv = PJ.frame_fit(proj.res, h, v)
        # 프레임의 세로 각도 범위. 벽 위아래를 다 담는 범위의 한가운데에 맞춘다.
        zb, zt = wall.base_z(), wall.base_z() + wall.height
        lo, hi = 9.9, -9.9
        for i in range(201):
            u = proj.u0 + (proj.u1 - proj.u0) * i / 200.0
            px, py = wall.plan_point(u)
            dh = math.hypot(px - self.X, py - self.Y)
            lo = min(lo, math.atan2(zb - self.Z, dh))
            hi = max(hi, math.atan2(zt - self.Z, dh))
        mid, half = (lo + hi) / 2.0, math.radians(fv) / 2.0
        self.vlo, self.vhi = mid - half, mid + half

    def _columns(self):
        """열마다 (벽 평면좌표 x, y, 프로젝터로부터의 수평거리). 벽 밖이면 None."""
        w = self.wall
        out = []
        for px in range(self.proj.res[0]):
            u = self.col.u_of_column(px)
            if u is None:
                out.append(None)
                continue
            wx, wy = w.plan_point(u)
            out.append((wx, wy, math.hypot(wx - self.X, wy - self.Y), u))
        return out

    def _rows(self, cols, rh, hit):
        """행을 훑으며 각 열의 광선이 벽면과 만나는 높이를 hit 에 넘긴다."""
        w = self.wall
        zb, zt = w.base_z(), w.base_z() + w.height
        for py in range(rh):
            th = self.vlo + (py + 0.5) / rh * (self.vhi - self.vlo)
            tn = math.tan(th)
            row = []
            for c in cols:
                if c is None:
                    row.append(OUTSIDE)
                    continue
                z = self.Z + c[2] * tn
                row.append(OUTSIDE if not (zb <= z <= zt) else hit(c, z))
            yield row

    def wall_maps(self, out_w, out_h):
        """프로젝터 픽셀 -> **벽 이미지** 픽셀. 이미 아나모픽이 걸린 영상을 받을 때 쓴다.

        합성 경로와 달리 아나모픽 변환을 다시 하지 않는다. 입력 영상의 해상도가
        그대로 상한이 되므로, 원본이 있다면 maps() 쪽이 낫다.
        """
        w = self.wall
        W, H = w.developed(), w.height
        zt = w.base_z() + H
        rw, rh = self.proj.res
        key = self.plan._key(rw, rh, out_w, out_h, self.proj.name,
                             self.proj.u0, self.proj.u1, self.proj.back,
                             self.proj.pos, self.proj.dz, "pwall")
        xm = os.path.join(tempfile.gettempdir(), "arpwall_%s_x.pgm" % key)
        ym = os.path.join(tempfile.gettempdir(), "arpwall_%s_y.pgm" % key)
        if os.path.exists(xm) and os.path.exists(ym):
            return xm, ym

        cols = self._columns()
        cl = lambda v, n: 0 if v < 0 else (n - 1 if v > n - 1 else v)
        _pgm16(xm, rw, rh, [[(OUTSIDE if c is None else cl(int(c[3] / W * out_w), out_w))
                             for c in cols]] * rh)
        _pgm16(ym, rw, rh,
               self._rows(cols, rh, lambda c, z: cl(int((zt - z) / H * out_h), out_h)))
        return xm, ym

    def maps(self):
        """-> (x맵 경로, y맵 경로, 가상평면 가로, 세로). TEMP 에 캐시한다."""
        w, p = self.wall, self.proj
        H, zt = w.height, w.base_z() + w.height
        zb = w.base_z()
        x0, x1, z0, z1, _, _, _ = self.plan.plane()
        vw, vh = self.plan.virtual_size()
        rw, rh = p.res
        kx, kz = (vw - 1) / (x1 - x0), (vh - 1) / (z1 - z0)

        key = self.plan._key(rw, rh, vw, vh, p.name, p.u0, p.u1, p.back, p.pos, p.dz, "proj")
        xm = os.path.join(tempfile.gettempdir(), "arproj_%s_x.pgm" % key)
        ym = os.path.join(tempfile.gettempdir(), "arproj_%s_y.pgm" % key)
        if os.path.exists(xm) and os.path.exists(ym):
            return xm, ym, vw, vh

        # 열마다 한 번만 구해 두면 행은 곱셈 두 번으로 끝난다
        cols = self._columns()
        cl = lambda v, n: 0 if v < 0 else (n - 1 if v > n - 1 else v)
        _pgm16(xm, rw, rh, [[(OUTSIDE if c is None else cl(int((c[1] / c[0] - x0) * kx + 0.5), vw))
                             for c in cols]] * rh)
        _pgm16(ym, rw, rh,
               self._rows(cols, rh, lambda c, z: cl(int((z1 - z / c[0]) * kz + 0.5), vh)))
        return xm, ym, vw, vh


def convert_projector(wall, projs, proj, plan, src, out_dir, alpha=None, log=print):
    """원본 -> 이 프로젝터가 쏠 영상. 아나모픽 + 프로젝터 워프를 한 번에 건다.

    alpha 에 블렌드 맵 경로를 주면 곱해서 굽는다. None 이면 워프만 하고 블렌딩은
    재생 쪽(미디어서버, nDisplay)에 맡긴다. 현장에서 눈으로 보며 조정하게 되므로
    굽지 않는 쪽이 대개 낫다.
    """
    assert os.path.isfile(src), "원본이 없다: " + src
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(src))[0]
    dst = os.path.join(out_dir, "%s_%s.mp4" % (stem, proj.name))

    pp = ProjectorPlan(wall, proj, plan)
    log("%s: 맵 준비 중..." % proj.name)
    xm, ym, vw, vh = pp.maps()
    rw, rh = proj.res
    ins = ["-i", src, "-loop", "1", "-i", xm, "-loop", "1", "-i", ym]
    graph = ("[0:v]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1[v];"
             "[1:v]format=gray16le[xm];[2:v]format=gray16le[ym];"
             "[v][xm][ym]remap=fill=black[w]" % (vw, vh, vw, vh))
    if alpha:
        ins += ["-loop", "1", "-i", alpha]
        graph += (";[3:v]format=gray16le,format=gbrp[a];[w]format=gbrp[wb];"
                  "[wb][a]blend=all_mode=multiply:shortest=1,format=yuv420p[o]")
    else:
        graph += ";[w]format=yuv420p[o]"
    _run(ins + ["-filter_complex", graph, "-map", "[o]", "-map", "0:a?", "-shortest"] + ENC + [dst])
    log("%s: %d x %d -> %s" % (proj.name, rw, rh, os.path.basename(dst)))
    return dst


def convert_projector_from_wall(wall, projs, proj, plan, src, out_dir,
                                alpha=None, log=print):
    """이미 아나모픽이 걸린 **벽 영상**에서 이 프로젝터가 쏠 영상을 만든다.

    입력 해상도가 그대로 상한이다. 프로젝터가 벽에 만드는 밀도보다 벽 영상이 성기면
    그만큼 잃는다. 원본이 있으면 convert_projector 쪽이 낫다.
    """
    assert os.path.isfile(src), "원본이 없다: " + src
    got = probe_size(src)
    assert got, "벽 영상의 해상도를 읽지 못했다 (ffprobe 필요): " + src
    ow, oh = got
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(src))[0]
    dst = os.path.join(out_dir, "%s_%s.mp4" % (stem, proj.name))

    pp = ProjectorPlan(wall, proj, plan)
    log("%s: 맵 준비 중... (벽 영상 %d x %d)" % (proj.name, ow, oh))
    xm, ym = pp.wall_maps(ow, oh)
    ins = ["-i", src, "-loop", "1", "-i", xm, "-loop", "1", "-i", ym]
    graph = ("[0:v]setsar=1[v];[1:v]format=gray16le[xm];[2:v]format=gray16le[ym];"
             "[v][xm][ym]remap=fill=black[w]")
    if alpha:
        ins += ["-loop", "1", "-i", alpha]
        graph += (";[3:v]format=gray16le,format=gbrp[a];[w]format=gbrp[wb];"
                  "[wb][a]blend=all_mode=multiply:shortest=1,format=yuv420p[o]")
    else:
        graph += ";[w]format=yuv420p[o]"
    _run(ins + ["-filter_complex", graph, "-map", "[o]", "-map", "0:a?", "-shortest"] + ENC + [dst])
    log("%s: %d x %d -> %s" % (proj.name, proj.res[0], proj.res[1], os.path.basename(dst)))
    return dst


def wall_image_shortfall(wall, projs, ow):
    """벽 영상 가로 ow 가 프로젝터 밀도를 못 따라가는 정도. -> (필요 px, 부족 배수).

    1.0 이하면 손실 없음. 2.0 이면 가장 촘촘한 곳에서 절반만 나온다.
    """
    from . import projector as PJ
    need = 0.0
    W = wall.developed()
    for p in projs:
        h, v = p.fov(wall)
        sc, _, _ = PJ.frame_fit(p.res, h, v)
        for q in p.scan(wall, 300):
            if q[4] > 0 and q[2] > 0.01:
                need = max(need, 1.0 / (q[1] / sc / math.sin(math.radians(q[2]))))
    need_px = int(need * W + 0.5)
    return need_px, (need_px / float(ow) if ow else 0.0)


def _pgm16(path, w, h, rows):
    """P5 16bit PGM. PGM 규격은 빅엔디안이라 x86 에서는 뒤집어 써야 한다."""
    with open(path, "wb") as f:
        f.write(b"P5\n%d %d\n65535\n" % (w, h))
        for r in rows:
            a = array("H", r)
            a.byteswap()
            f.write(a.tobytes())


def probe_size(src):
    """원본 해상도. ffprobe 가 없거나 못 읽으면 None. 변환을 막지는 않는다."""
    exe = shutil.which("ffprobe")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", src],
            capture_output=True, text=True, timeout=30)
        w, h = out.stdout.strip().split("x")[:2]
        return int(w), int(h)
    except Exception:
        return None


def crop_note(src, vw, vh):
    """원본을 가상 평면에 채워 넣을 때 얼마나 잘려 나가는지. -> 줄 목록.

    convert() 는 force_original_aspect_ratio=increase 로 채운 뒤 crop 한다. 비율이
    다르면 조용히 잘린다. 잘린 것은 눈에 띄지만 원근이 어긋난 것은 눈에 안 띄므로,
    적어도 얼마나 잘렸는지는 남겨 둔다.
    """
    got = probe_size(src)
    if not got:
        return []
    sw, sh = got
    sa, va = sw / float(sh), vw / float(vh)
    lines = ["원본 %dx%d (%.3f:1) -> 가상 평면 %dx%d (%.3f:1)" % (sw, sh, sa, vw, vh, va)]
    if abs(sa - va) < 1e-4:
        lines.append("  비율이 같다. 잘려 나가는 부분 없음")
        return lines
    axis, lost = ("가로", 1.0 - va / sa) if sa > va else ("세로", 1.0 - sa / va)
    lines.append("  %s %.1f%% 가 잘려 나간다.%s"
                 % (axis, lost * 100.0,
                    "  권장 렌더 크기로 다시 뽑으면 손실이 없다" if lost > 0.10 else ""))
    return lines


def _run(args):
    assert shutil.which("ffmpeg"), "ffmpeg 이 PATH 에 없다. 설치하고 PATH 에 넣을 것"
    subprocess.run(["ffmpeg", "-y"] + args, check=True)


ENC = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "copy"]


def convert(plan, src, out_dir, curved=True, log=print):
    """받은 영상을 벽에 맞게 변환한다. -> 만들어진 파일 경로.

    curved=False 면 비율만 맞춘다 (사전 왜곡 없음).
    """
    assert os.path.isfile(src), "원본이 없다: " + src
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, os.path.splitext(os.path.basename(src))[0]
                       + ("_curved.mp4" if curved else "_wall.mp4"))
    if os.path.exists(dst):
        log("덮어씀: " + dst)
    if not curved:
        fill = "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (
            plan.out_w, plan.out_h, plan.out_w, plan.out_h)
        _run(["-i", src, "-vf", fill] + ENC + [dst])
        return dst

    log("워프 맵 준비 중...")
    xm, ym, vw, vh = plan.warp_maps()
    for line in crop_note(src, vw, vh):
        log(line)
    graph = (
        # 1) 원본을 가상 평면 비율로 채워 자르고  2) 벽 모양으로 되찍고  3) 출력 크기로 축소
        "[0:v]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1[v];"
        "[1:v]format=gray16le[xm];[2:v]format=gray16le[ym];"
        "[v][xm][ym]remap=fill=black,scale=%d:%d:flags=lanczos[o]"
        % (vw, vh, vw, vh, plan.out_w, plan.out_h))
    _run(["-i", src, "-loop", "1", "-i", xm, "-loop", "1", "-i", ym,
          "-filter_complex", graph, "-map", "[o]", "-map", "0:a?", "-shortest"] + ENC + [dst])
    return dst


def preview(plan, src, out_dir, width=None, log=print):
    """전개 영상을 받아 스위트스팟 시점 영상을 만든다. 검증 전용, 벽에 넣는 파일이 아니다."""
    assert os.path.isfile(src), "원본이 없다: " + src
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, os.path.splitext(os.path.basename(src))[0] + "_eye.mp4")
    aspect = plan.plane()[5]
    # 착시가 맞는지 눈으로 보는 용도라 벽 해상도까지 갈 필요가 없다. 4K 를 넘기면
    # 인코딩만 오래 걸리고 플레이어도 버거워한다.
    pw = int(width or min(plan.out_w, 3840))
    pw -= pw % 2                                    # yuv420 은 짝수 폭이 필요
    ph = round(pw / aspect / 2) * 2
    log("눈 시점 맵 준비 중... (%dx%d)" % (pw, ph))
    xm, ym = plan.eye_maps(pw, ph)
    graph = ("[0:v]scale=%d:%d,setsar=1[v];"
             "[1:v]format=gray16le[xm];[2:v]format=gray16le[ym];"
             "[v][xm][ym]remap=fill=black[o]" % (plan.out_w, plan.out_h))
    _run(["-i", src, "-loop", "1", "-i", xm, "-loop", "1", "-i", ym,
          "-filter_complex", graph, "-map", "[o]", "-map", "0:a?", "-shortest",
          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "copy", dst])
    return dst


def merge_side_by_side(paths, dst, log=print):
    """MRQ 가 뷰포트마다 뽑은 파일을 왼쪽부터 가로로 붙인다."""
    assert len(paths) >= 2, "합칠 파일이 2개 미만이다"
    for p in paths:
        assert os.path.isfile(p), "없는 파일: " + p
    n = len(paths)
    args = []
    for p in paths:
        args += ["-i", p]
    graph = "".join("[%d:v]" % i for i in range(n)) + "hstack=inputs=%d[v]" % n
    _run(args + ["-filter_complex", graph, "-map", "[v]",
                 "-c:v", "libx264", "-crf", "16", "-preset", "medium",
                 "-pix_fmt", "yuv420p", dst])
    log("합침: " + dst)
    return dst
