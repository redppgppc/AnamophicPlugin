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
import hashlib, os, shutil, subprocess, tempfile
from array import array

CURVED_SS = 2      # remap 은 최근접 샘플링뿐이라, 크게 뜬 뒤 줄여서 계단을 없앤다
SAMPLES = 4096     # 투영 경계를 재는 표본 수


class Plan(object):
    """벽 하나에 대한 변환 계획. 출력 크기와 투영 경계를 한 번만 재서 들고 있는다."""

    def __init__(self, wall, out_w=3840, virt_w=0):
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
        OUTSIDE = 65535                        # remap 이 fill 색으로 칠하게 범위 밖 값
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


def _pgm16(path, w, h, rows):
    """P5 16bit PGM. PGM 규격은 빅엔디안이라 x86 에서는 뒤집어 써야 한다."""
    with open(path, "wb") as f:
        f.write(b"P5\n%d %d\n65535\n" % (w, h))
        for r in rows:
            a = array("H", r)
            a.byteswap()
            f.write(a.tobytes())


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
    graph = (
        # 1) 원본을 가상 평면 비율로 채워 자르고  2) 벽 모양으로 되찍고  3) 출력 크기로 축소
        "[0:v]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1[v];"
        "[1:v]format=gray16le[xm];[2:v]format=gray16le[ym];"
        "[v][xm][ym]remap=fill=black,scale=%d:%d:flags=lanczos[o]"
        % (vw, vh, vw, vh, plan.out_w, plan.out_h))
    _run(["-i", src, "-loop", "1", "-i", xm, "-loop", "1", "-i", ym,
          "-filter_complex", graph, "-map", "[o]", "-map", "0:a?", "-shortest"] + ENC + [dst])
    return dst


def preview(plan, src, out_dir, width=1920, log=print):
    """전개 영상을 받아 스위트스팟 시점 영상을 만든다. 검증 전용, 벽에 넣는 파일이 아니다."""
    assert os.path.isfile(src), "원본이 없다: " + src
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, os.path.splitext(os.path.basename(src))[0] + "_eye.mp4")
    aspect = plan.plane()[5]
    pw = int(width)
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
