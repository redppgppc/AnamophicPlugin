"""Convert any video for the 77:21 wall.

    python Scripts/convert_video.py in.mp4             -> Content/Movies/in_wall.mp4
    python Scripts/convert_video.py in.mp4 --curved    -> Content/Movies/in_curved.mp4
    python Scripts/convert_video.py                    -> self-check only

The output always lands in Content/Movies/ no matter where the source is, because that is
where the VIDEO knob's project-relative path has to point. The source is never touched.

Two products, and they are NOT interchangeable:

  _wall.mp4    Fit to the developed 77:21 rectangle. The image is painted on the wall like
               wallpaper. On a bent wall a straight line visibly kinks at the corner.
               This is what an ordinary LED wall with no designed viewpoint wants.

  _curved.mp4  Anamorphic pre-warp for curved.py's bent wall. Pre-distorted so that a
               viewer standing at the sweet spot sees a flat, undistorted picture, i.e.
               the COEX-wave illusion. Correct ONLY from the sweet spot; from anywhere
               else it looks more wrong than _wall.mp4, and that is unavoidable.

The --curved warp reads its geometry straight from curved.py, so changing the rig there
changes the warp with no edits here.
"""
import hashlib, os, shutil, struct, subprocess, sys, tempfile
from array import array
import flat as rig
import curved as wall

OUT_W = 3840                                        # ponytail: one fixed output size
OUT_H = int(round(OUT_W * rig.SCREEN_H_CM / rig.SCREEN_W_CM))
OUT_H -= OUT_H % 2                                  # yuv420 needs even height
OUT_REL = "Content/Movies"                          # 프로젝트 기준. VIDEO 노브가 여길 가리킨다
OUT_DIR = os.path.join(rig.ROOT, *OUT_REL.split("/"))

# --- --curved 전용 노브 ------------------------------------------------------
CURVED_SS = 2      # remap 은 최근접 샘플링뿐이라, 크게 뜬 뒤 줄여서 계단을 없앤다
VIRT_W = 0         # 가상 평면 래스터 폭. 0 = 자동 (벽 양 끝이 1:1 이 되는 폭)
SAMPLES = 4096     # 투영 경계를 재는 표본 수


def check_rigs_agree():
    """OUT_W/OUT_H 는 flat.py 의 사각형에서 나온다. curved 벽이 그와 다르면 이 스크립트가
    조용히 틀린 종횡비의 파일을 낸다. 변환 전에 반드시 부를 것.

    curved 의 DEVELOPED_W_CM 은 FACE_B + 호 + FACE_A 로 유도되므로 딱 떨어지지 않는다.
    0.1% 까지는 눈감아 준다 (3840 px 기준 4 px 미만).
    """
    for label, key, cur, fl in (("가로", "W", wall.DEVELOPED_W_CM, rig.SCREEN_W_CM),
                                ("세로", "H", wall.SCREEN_H_CM, rig.SCREEN_H_CM)):
        assert abs(cur - fl) / fl < 1e-3, (
            "%s 크기가 어긋남: flat.py %g cm vs curved.py %g cm (%.2f%% 차이).\n"
            "  출력 크기는 flat.py 기준이라 이대로 변환하면 종횡비가 틀린다.\n"
            "  curved 쪽이 맞다면 flat.py 의 SCREEN_%s_CM 을 %.4f 로 바꿀 것."
            % (label, fl, cur, abs(cur - fl) / fl * 100, key, cur))


def virtual_plane():
    """벽을 스위트스팟에서 봤을 때의 투영 경계.

    -> (x0, x1, z0, z1, mag, aspect, band)
    관람 거리는 정규화 과정에서 상쇄되므로 1 로 두고 계산한다. 즉 화면 좌표는
    Xv = y/x, Zv = z/x 로 끝난다.
    band 는 벽 어느 지점에서도 잘리지 않는 세로 구간 (원본 위에서부터의 비율).
    """
    W, H = wall.DEVELOPED_W_CM, wall.SCREEN_H_CM
    zt, zb = wall.base_z() + H, wall.base_z()
    pts = [wall.plan_point(i * W / SAMPLES) for i in range(SAMPLES + 1)]
    xv = [y / x for x, y in pts]
    x0, x1 = min(xv), max(xv)
    z0 = min(zb / x for x, _ in pts)
    z1 = max(zt / x for x, _ in pts)
    # 양 끝의 가로 배율. 벽에서 1 갈 때 원본에서 얼마나 덜 가는가.
    d = W / SAMPLES
    def s(u):
        x, y = wall.plan_point(u)
        return (y / x - x0) / (x1 - x0)
    mag = max((2 * d / W) / (s(W - d) - s(W - 3 * d)),
              (2 * d / W) / (s(3 * d) - s(d)))
    band = ((z1 - min(zt / x for x, _ in pts)) / (z1 - z0),
            (z1 - max(zb / x for x, _ in pts)) / (z1 - z0))
    return x0, x1, z0, z1, mag, (x1 - x0) / (z1 - z0), band


def virtual_size():
    """가상 평면 래스터 크기. 벽 양 끝이 1:1 이 되도록 잡는다."""
    _, _, _, _, mag, aspect, _ = virtual_plane()
    vw = VIRT_W or round(OUT_W * mag / 2) * 2
    return vw, round(vw / aspect / 2) * 2


def _pgm16(path, w, h, rows):
    """P5 16bit PGM. PGM 규격은 빅엔디안이라 x86 에서는 뒤집어 써야 한다."""
    with open(path, "wb") as f:
        f.write(b"P5\n%d %d\n65535\n" % (w, h))
        for r in rows:
            a = array("H", r)
            a.byteswap()
            f.write(a.tobytes())


def build_maps():
    """벽 픽셀 -> 가상 평면 픽셀 좌표 맵 두 장. TEMP 에 캐시하고 경로를 돌려준다.

    Xv 는 열에만, Zv 는 z * (1/x) 의 외적 구조라 열별 1/x 를 미리 잡아 두면
    행마다 곱셈 한 번으로 끝난다. numpy 없이도 견딜 만하다.
    """
    W, H = wall.DEVELOPED_W_CM, wall.SCREEN_H_CM
    zt = wall.base_z() + H
    x0, x1, z0, z1, _, _, _ = virtual_plane()
    vw, vh = virtual_size()
    mw, mh = OUT_W * CURVED_SS, OUT_H * CURVED_SS

    key = hashlib.md5(repr(wall.geom_key() + (mw, mh, vw, vh)).encode()).hexdigest()[:12]
    xm = os.path.join(tempfile.gettempdir(), "wallwarp_%s_x.pgm" % key)
    ym = os.path.join(tempfile.gettempdir(), "wallwarp_%s_y.pgm" % key)
    if os.path.exists(xm) and os.path.exists(ym):
        return xm, ym, vw, vh

    cols = [wall.plan_point((px + 0.5) / mw * W) for px in range(mw)]
    kx, kz = (vw - 1) / (x1 - x0), (vh - 1) / (z1 - z0)
    clampx = lambda v: 0 if v < 0 else (vw - 1 if v > vw - 1 else v)
    clampz = lambda v: 0 if v < 0 else (vh - 1 if v > vh - 1 else v)
    _pgm16(xm, mw, mh,
           [[clampx(int((y / x - x0) * kx + 0.5)) for x, y in cols]] * mh)
    invx = [1.0 / x for x, _ in cols]
    def yrow(py):
        zk = (zt - (py + 0.5) / mh * H) * kz
        b = z1 * kz + 0.5
        return [clampz(int(b - zk * ix)) for ix in invx]
    _pgm16(ym, mw, mh, (yrow(py) for py in range(mh)))
    return xm, ym, vw, vh


def build_preview_maps(pw, ph):
    """--curved 의 역방향. 전개 영상 -> 스위트스팟에 선 사람이 볼 그림.

    검증용이다. `_curved.mp4` 를 이걸로 되돌리면 원본과 같아야 하고,
    `_wall.mp4` 를 되돌리면 코너에서 꺾인 그림이 나와야 한다.
    """
    W, H = wall.DEVELOPED_W_CM, wall.SCREEN_H_CM
    zt, zb = wall.base_z() + H, wall.base_z()
    x0, x1, z0, z1, _, _, _ = virtual_plane()

    key = hashlib.md5(repr(wall.geom_key() + (pw, ph, "eye")).encode()).hexdigest()[:12]
    xm = os.path.join(tempfile.gettempdir(), "walleye_%s_x.pgm" % key)
    ym = os.path.join(tempfile.gettempdir(), "walleye_%s_y.pgm" % key)
    if os.path.exists(xm) and os.path.exists(ym):
        return xm, ym

    # 시선 방향 Xv 를 주면 벽의 어느 전개 위치인지. y/x 가 u 에 대해 단조라 이분법으로 푼다.
    def solve_u(xv):
        lo, hi = 0.0, W
        for _ in range(60):
            mid = (lo + hi) / 2.0
            px, py = wall.plan_point(mid)
            if py / px < xv:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0

    us = [solve_u(x0 + (px + 0.5) / pw * (x1 - x0)) for px in range(pw)]
    xs = [wall.plan_point(u)[0] for u in us]
    OUTSIDE = 65535                                   # remap 이 fill 색으로 칠하게 범위 밖 값
    _pgm16(xm, pw, ph, [[min(OUT_W - 1, int(u / W * OUT_W)) for u in us]] * ph)

    def yrow(py):
        zv = z1 - (py + 0.5) / ph * (z1 - z0)
        row = []
        for x in xs:
            z = zv * x                                # 그 방향의 시선이 벽면과 만나는 높이
            row.append(OUTSIDE if not (zb <= z <= zt)  # 그 방향엔 벽이 없다
                       else min(OUT_H - 1, int((zt - z) / H * OUT_H)))
        return row
    _pgm16(ym, pw, ph, (yrow(py) for py in range(ph)))
    return xm, ym


def preview(src):
    """전개 영상을 받아 스위트스팟 시점 영상을 만든다. 검증 전용."""
    check_rigs_agree()
    os.makedirs(OUT_DIR, exist_ok=True)
    dst = os.path.join(OUT_DIR, os.path.splitext(os.path.basename(src))[0] + "_eye.mp4")
    _, _, _, _, _, aspect, _ = virtual_plane()
    pw = 1920
    ph = round(pw / aspect / 2) * 2
    print("eye map 준비 중... (%dx%d)" % (pw, ph))
    xm, ym = build_preview_maps(pw, ph)
    graph = ("[0:v]scale=%d:%d,setsar=1[v];"
             "[1:v]format=gray16le[xm];[2:v]format=gray16le[ym];"
             "[v][xm][ym]remap=fill=black[o]" % (OUT_W, OUT_H))
    subprocess.run(["ffmpeg", "-y", "-i", src, "-loop", "1", "-i", xm, "-loop", "1", "-i", ym,
                    "-filter_complex", graph, "-map", "[o]", "-map", "0:a?", "-shortest",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "copy", dst],
                   check=True)
    return dst


def convert(src, curved=False):
    check_rigs_agree()
    os.makedirs(OUT_DIR, exist_ok=True)
    dst = os.path.join(OUT_DIR, os.path.splitext(os.path.basename(src))[0]
                       + ("_curved.mp4" if curved else "_wall.mp4"))
    # 원본 폴더가 달라도 파일명이 같으면 덮어쓴다. 되돌릴 수 있는 파생물이라 막지는 않고 알리기만.
    if os.path.exists(dst):
        print("overwriting " + dst)
    enc = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "copy", dst]
    if not curved:
        fill = "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (
            OUT_W, OUT_H, OUT_W, OUT_H)
        subprocess.run(["ffmpeg", "-y", "-i", src, "-vf", fill] + enc, check=True)
        return dst

    print("warp map 준비 중...")
    xm, ym, vw, vh = build_maps()
    graph = (
        # 1) 원본을 가상 평면 비율로 채워 자르고  2) 벽 모양으로 되찍고  3) 출력 크기로 축소
        "[0:v]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1[v];"
        "[1:v]format=gray16le[xm];[2:v]format=gray16le[ym];"
        "[v][xm][ym]remap=fill=black,scale=%d:%d:flags=lanczos[o]"
        % (vw, vh, vw, vh, OUT_W, OUT_H))
    subprocess.run(["ffmpeg", "-y", "-i", src, "-loop", "1", "-i", xm, "-loop", "1", "-i", ym,
                    "-filter_complex", graph, "-map", "[o]", "-map", "0:a?", "-shortest"] + enc,
                   check=True)
    return dst


def demo():
    assert abs(OUT_W / OUT_H - rig.SCREEN_W_CM / rig.SCREEN_H_CM) < 0.01, "출력 종횡비 != 벽 종횡비"
    assert OUT_H % 2 == 0, "yuv420 은 짝수 높이가 필요"
    check_rigs_agree()
    assert shutil.which("ffmpeg"), "ffmpeg 이 PATH 에 없음"

    x0, x1, z0, z1, mag, aspect, band = virtual_plane()
    vw, vh = virtual_size()
    W = wall.DEVELOPED_W_CM
    assert x0 < x1 and z0 < z1, "투영 경계가 뒤집힘"
    assert all(wall.plan_point(i * W / 64)[0] > 0 for i in range(65)), "벽 일부가 눈 뒤에 있음"
    assert 2 * abs(wall.half_fov_deg()) < 120, \
        "화각 %.0f도. 평면 가상 스크린으로는 감당이 안 된다 (CONVEX 확인)" % (2 * wall.half_fov_deg())
    # 스위트스팟이 대칭축 위에 있을 때만 호 정점이 가상 이미지의 가로 정중앙이다.
    # 축에서 벗어난 스위트스팟이면 정중앙이 아닌 것이 정상이다.
    xc, yc = wall.plan_point(W / 2)
    if not wall.EYE_OFFSET_Y_CM:
        assert abs((yc / xc - x0) / (x1 - x0) - 0.5) < 1e-6, "호 정점이 가상 이미지 중앙이 아님"
    # 매핑이 가로로 단조여야 좌우가 뒤집히거나 접히지 않는다.
    sv = [wall.plan_point(i * W / 64)[1] / wall.plan_point(i * W / 64)[0] for i in range(65)]
    assert all(a < b for a, b in zip(sv, sv[1:])), "가로 매핑이 단조가 아님 (이미지가 접힘)"
    assert vw >= OUT_W and vh > 0
    # 핵심 검증: 벽 위의 점과 그 점이 참조하는 가상 평면 위의 점이 눈에서 같은 방향이어야
    # 한다. 같은 방향이라야 관람자 눈에 둘이 겹쳐 보이고, 그게 이 착시의 전부다.
    # Xv=y/x, Zv=z/x 라는 식의 부호나 축이 틀리면 여기서 잡힌다.
    for i in range(9):
        u = i * W / 8.0
        for f in (0.0, 0.5, 1.0):
            x, y = wall.plan_point(u)
            z = wall.base_z() + f * wall.SCREEN_H_CM
            a = (x, y, z)                       # 눈 -> 벽 위의 점
            b = (1.0, y / x, z / x)             # 눈 -> 그 점이 참조하는 가상 평면 위의 점
            na = sum(v * v for v in a) ** 0.5
            nb = sum(v * v for v in b) ** 0.5
            cos = sum(p * q for p, q in zip(a, b)) / (na * nb)
            assert cos > 1 - 1e-12, "u=%g f=%g: 벽과 가상 평면의 시선 방향이 어긋남" % (u, f)

    print("ok: 전개 출력 %dx%d (%g:%g), ffmpeg 확인됨" % (OUT_W, OUT_H, rig.SCREEN_W_CM, rig.SCREEN_H_CM))
    print("--curved 아나모픽:")
    print("  가상 평면 종횡비 %.3f : 1  ->  소재는 이 비율로 받는 게 이상적" % aspect)
    print("  가상 래스터 %dx%d  (양 끝 배율 %.2f 배 보정)" % (vw, vh, mag))
    print("  항상 벽에 보이는 세로 밴드: 원본 위에서 %.1f%% ~ %.1f%%" % (band[0] * 100, band[1] * 100))
    print("  스위트스팟 %g cm 에서만 정확함" % wall.EYE_DIST_CM)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        demo()
        sys.exit(0)
    if "--preview" in sys.argv:
        print("wrote " + preview(args[0]) + "\n(스위트스팟 시점 미리보기. 벽에 올리는 파일이 아님)")
        sys.exit(0)
    dst = convert(args[0], "--curved" in sys.argv)
    print("wrote " + dst)
    # 그대로 flat.py / curved.py 의 VIDEO 에 붙여 넣으라고 경로를 만들어 준다.
    print('VIDEO = "%s/%s"' % (OUT_REL, os.path.basename(dst)))
