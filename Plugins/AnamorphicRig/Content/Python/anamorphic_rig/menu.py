"""에디터 메뉴 등록. 설정 에셋을 골라 놓고 버튼을 누르면 동작한다.

버튼이 하는 일은 전부 다른 모듈에 있다. 여기는 배선만 한다.
"""
import os

import unreal

from . import build as B
from . import config as CF
from . import env as EN
from . import presets as PR
from . import blend as BL
from . import projector as PJ
from . import preview as PV
from . import report as R
from . import settings as S
from . import video as V

MENU = "LevelEditor.MainMenu.Tools"
SECTION = "AnamorphicRig"
ROOT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).rstrip("/")

# 마지막으로 고른 설정 에셋. 콘텐츠 브라우저 선택이 우선이고, 없으면 이걸 쓴다.
_last = [None]


def _log(msg):
    unreal.log("[AnamorphicRig] %s" % msg)


def _dialog(title, msg):
    unreal.EditorDialog.show_message(title, msg, unreal.AppMsgType.OK)


def _ask(title, msg):
    """예/아니오. 예를 누르면 True."""
    r = unreal.EditorDialog.show_message(title, msg, unreal.AppMsgType.YES_NO)
    return r == unreal.AppReturnType.YES


def _open(path):
    """OS 기본 프로그램으로 연다. 변환 결과는 평범한 mp4 라 이게 제일 빠르다."""
    try:
        os.startfile(path)                      # 윈도우
    except AttributeError:
        import subprocess
        subprocess.Popen(["xdg-open", path])
    except OSError as e:
        _log("열지 못했습니다 (%s). 직접 여세요: %s" % (e, path))


MOVIES = None       # 늦게 계산한다. ROOT 가 필요해서.


def movies_dir():
    d = os.path.join(ROOT, "Content", "Movies")
    os.makedirs(d, exist_ok=True)
    return d


def act_open_movies():
    """변환 결과가 쌓이는 폴더를 연다."""
    d = movies_dir()
    _open(d)
    _log("폴더: " + d)


def _details(title, obj, width=520, height=640):
    """임시 객체를 디테일 패널 대화상자로 띄운다. OK 를 누르면 True."""
    o = unreal.EditorDialogLibraryObjectDetailsViewOptions()
    o.set_editor_property("show_object_name", False)
    o.set_editor_property("allow_search", True)
    o.set_editor_property("allow_resizing", True)
    o.set_editor_property("min_width", width)
    o.set_editor_property("min_height", height)
    return unreal.EditorDialog.show_object_details_view(title, obj, o)


def current_settings():
    """활성 프리셋을 읽어 임시 설정 객체로 만든다. 파일이 없으면 기본값."""
    name = PR.active()
    s = S.new_settings(name)
    if PR.exists(name):
        S.apply_dict(s, PR.load(name))
    return s


_editing = {}       # 프리셋 이름 -> 지금 탭에서 편집 중인 설정 객체


def act_edit():
    """설정을 **모달리스** 탭으로 연다. 저장은 탭 안의 '저장' 버튼이 한다.

    등록된 AssetTypeActions 가 없는 UObject 를 열면 엔진이 범용 프로퍼티 에디터를
    띄운다 (AssetEditorSubsystem.cpp 의 OpenEditorForAsset 마지막 else 가
    FSimpleAssetEditor::CreateEditor 를 부른다). 도킹되는 보통 탭이라 뷰포트를
    가리지 않는다. 모달 대화상자로는 평면도를 보면서 값을 만질 수가 없었다.

    이 객체는 에셋이 아니라 임시 객체지만, 툴킷이 FGCObject 로 참조를 잡아 주므로
    탭이 열려 있는 동안 GC 되지 않는다. 툴바의 저장 버튼은 에셋이 아닌 객체를 그냥
    건너뛴다 (AssetEditorToolkit.cpp 의 SaveAsset_Execute). 그래서 프리셋 저장은
    디테일 패널의 '저장' 버튼이 한다.
    """
    name = PR.active()
    s = _editing.get(name)
    if s is None:
        s = current_settings()
        _editing[name] = s
    sub = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
    sub.close_all_editors_for_asset(s)          # 같은 탭이 여러 장 뜨는 것을 막는다
    if sub.open_editor_for_assets([s]):
        _log("설정 탭을 열었습니다: %s  (탭 안의 '저장' 을 눌러야 프리셋에 기록됩니다)" % name)
        return
    # 범용 에디터를 못 띄우는 환경이면 예전의 모달 대화상자로 돌아간다.
    _log("모달리스 탭을 열지 못해 대화상자로 엽니다")
    if _details("설정 - %s   (확인을 눌러야 저장됩니다)" % name, s):
        act_save(s)


def act_save(s=None):
    """편집 중인 값을 활성 프리셋 파일에 기록하고 형상 요약을 낸다."""
    s = current_settings() if s is None else s
    name = S.preset_of(s) or PR.active()        # 탭이 열린 뒤 활성이 바뀌었어도 제 것에 저장한다
    path = PR.save(name, S.to_dict(s))
    _log("저장: " + path)
    wall = S.to_wall(s)
    lines, warns = R.summarize(wall, S.res_w_of(s, wall), s.warn_grazing_deg,
                               s.warn_band_pct, s.warn_density_ratio,
                               s.warn_video_w)
    for l in lines:
        _log(l)
    for w in warns:
        unreal.log_warning("[AnamorphicRig] " + w)
    _dialog("저장됨 - %s" % name,
            "\n".join([path, ""] + lines + ([""] + ["! " + w for w in warns] if warns else [])))


@unreal.uclass()
class _PresetPick(unreal.Object):
    """프리셋 하나를 고르기 위한 임시 그릇.

    GetOptions 메타가 붙은 문자열은 디테일 패널에서 콤보 박스로 그려진다.
    안 그려지는 환경이면 그냥 타이핑해도 된다.
    """
    name = unreal.uproperty(str, meta=dict(DisplayName="프리셋", GetOptions="get_names"))

    @unreal.ufunction(ret=unreal.Array(str), pure=True)
    def get_names(self):
        return PR.names()


@unreal.uclass()
class _PresetName(unreal.Object):
    """새 이름을 받기 위한 임시 그릇. 목록을 주면 기존 이름을 덮어쓰기 쉬워서 일부러 자유 입력."""
    name = unreal.uproperty(str, meta=dict(DisplayName="새 이름"))


def act_load():
    """프리셋을 골라 활성으로 삼는다."""
    got = PR.names()
    if not got:
        raise RuntimeError("저장된 프리셋이 없습니다.\n"
                           "'설정 편집' 으로 값을 넣고 확인을 누르면 첫 프리셋이 만들어집니다.")
    o = unreal.new_object(_PresetPick.static_class())
    o.name = PR.active()
    if not _details("프리셋 불러오기", o, 460, 160):
        return
    name = (o.name or "").strip()
    if not PR.exists(name):
        raise RuntimeError("없는 프리셋입니다: %s\n있는 것: %s" % (name, ", ".join(got)))
    PR.set_active(name)
    _editing.pop(name, None)                    # 다음에 열 때 파일에서 새로 읽도록
    _log("불러옴: %s  (%s)" % (name, PR.path_of(name)))
    act_check()


def act_save_as():
    """지금 활성 프리셋의 값을 새 이름으로 복사한다."""
    o = unreal.new_object(_PresetName.static_class())
    o.name = PR.active() + "_copy"
    if not _details("다른 이름으로 저장  (있는 것: %s)"
                    % (", ".join(PR.names()) or "없음"), o, 460, 140):
        return
    name = (o.name or "").strip()
    if not name:
        raise RuntimeError("이름이 비었습니다")
    if any(c in name for c in '\\/:*?"<>|'):
        raise RuntimeError("파일 이름에 쓸 수 없는 문자가 있습니다: " + name)
    existed = PR.exists(name)
    src = _editing.get(PR.active()) or current_settings()   # 탭이 열려 있으면 그 값을 복사
    p = PR.save(name, S.to_dict(src))
    PR.set_active(name)
    _log("%s: %s" % ("덮어씀" if existed else "새로 저장", p))
    _dialog("다른 이름으로 저장", "활성 프리셋: %s\n%s" % (name, p))


def _safe(name):
    """프리셋 이름 -> 에셋 이름에 쓸 수 있는 형태. 한글은 그대로 둔다."""
    out = "".join(c if (c.isalnum() or c == "_") else "_" for c in name)
    return out.strip("_") or "Preset"


def _warn_video_w(s, plan_w):
    """영상 가로가 인코더 상한을 넘으면 로그에 남기고 문자열을 돌려준다. 안 넘으면 None.

    형상 점검에만 두면 늦다. 해상도가 바뀌는 자리(벽 만들기)와 실제로 뽑는 자리
    (무비 렌더 큐 점검, 영상 변환)에서 각각 알려 준다. 오래 걸리는 작업이 끝난 뒤에
    인코더가 실패하는 것이 가장 나쁘다.
    """
    w = R.video_warning(plan_w, s.warn_video_w)
    if w:
        unreal.log_warning("[AnamorphicRig] " + w)
    return w


def _opts(s):
    """설정 -> build_level 이 쓰는 dict.

    에셋 이름에 프리셋 이름을 넣는다. 프리셋마다 컴포넌트 구성이 다를 수 있는데
    에셋 하나를 공유하면 서로 지우라고 요구하게 된다.
    """
    tag = _safe(S.preset_of(s) or PR.active())
    name = "NDC_" + tag
    return dict(
        asset_dir="/Game/AnamorphicRig", asset_name=name, mesh_name="SM_" + tag,
        cfg_path=os.path.join(ROOT, "nDisplay", name + ".ndisplay"),
        root=ROOT, res_w=S.res_w_of(s),
        video=S.video_path_of(s), video_passthrough=s.video_passthrough,
        exposure_bias=s.exposure_bias, rig_origin=(0.0, 0.0, s.eye_height_m * S.M),
        show_floor=s.show_floor, eye_height=s.eye_height_m * S.M,
        follow_player=s.follow_player, exit_on_esc=s.exit_on_esc,
        per_node=1 if s.multi_node else 0, fit_preview=s.fit_preview,
        arc_seg=s.arc_seg, face_seg=s.face_seg, seg_v=s.seg_v,
        flip_v=s.flip_v, flip_winding=s.flip_winding)


# --- 버튼 -------------------------------------------------------------------
def act_check(s=None):
    s = current_settings() if s is None else s      # 설정 대화상자가 편집 중인 값을 넘긴다
    wall = S.to_wall(s)
    # 플러그인만 받아 온 프로젝트에서 뭐가 빠졌는지 먼저 본다. 여기서 잡는 것들은
    # 전부 조용히 실패해서, 안 알려 주면 원인을 못 찾는다.
    env_lines, env_warns = EN.check()
    lines, warns = R.summarize(wall, S.res_w_of(s, wall), s.warn_grazing_deg,
                               s.warn_band_pct, s.warn_density_ratio,
                               s.warn_video_w)
    lines, warns = env_lines + [""] + lines, env_warns + warns
    for l in lines:
        _log(l)
    for w in warns:
        unreal.log_warning("[AnamorphicRig] " + w)
    o = _opts(s)
    lines = lines + ["", "프리셋 %s -> 에셋 %s/%s"
                     % (S.preset_of(s) or PR.active(), o["asset_dir"], o["asset_name"])]

    # DCRA 에셋에 구워진 노드 구성. 설정과 다르면 '벽 만들기' 전까지 실행 결과가 어긋난다.
    # 노드만 바뀌었을 때는 뷰포트 이름이 그대로라 눈으로 구분이 안 된다. 여기서 대조해 준다.
    asset = "%s/%s" % (o["asset_dir"], o["asset_name"])
    want = dict((n, sorted(v["viewports"])) for n, v in
                CF.build(wall, "%s.%s" % (asset, o["asset_name"]), o["res_w"],
                         per_node=o["per_node"])[0]["nDisplay"]["cluster"]["nodes"].items())
    have = B.asset_layout(asset, o["asset_name"])
    lines += ["", "설정이 원하는 노드  %s" % want,
              "에셋에 구워진 노드  %s" % ("없음 (아직 안 만듦)" if have is None else have)]
    if have != want:
        lines.append("!! 다릅니다. '벽 만들기' 를 눌러야 반영됩니다")
        warns = warns + ["에셋 노드 구성이 설정과 다르다. '벽 만들기' 를 돌릴 것"]
    for l in lines[-4:]:
        _log(l)
    _dialog("형상 점검", "\n".join(lines + ([""] + ["! " + w for w in warns] if warns else [])))


def act_projectors(s=None):
    """프로젝터 배치를 검토한다. 설치 전에 배치를 정하는 용도다.

    실제 워프 맵은 여기서 만들지 않는다. 그건 카메라 캘리브레이션의 몫이고,
    이 계산은 대수·위치·담당 구간·이음매 자리를 정하는 데 쓴다.
    """
    s = current_settings() if s is None else s
    projs = S.to_projectors(s)
    if not projs:
        raise RuntimeError(
            "프로젝터가 정의되지 않았습니다.\n"
            "설정 편집 > 08 프로젝터 > 프로젝터 목록 에 추가하세요.\n"
            "LED 벽이면 이 기능은 쓰지 않습니다.")
    wall = S.to_wall(s)
    lines, warns = PJ.analyze(wall, projs, s.warn_grazing_deg, s.warn_blend_pct)
    for l in lines:
        _log(l)
    for w in warns:
        unreal.log_warning("[AnamorphicRig] " + w)
    _dialog("프로젝터 배치 점검",
            "\n".join(lines + ([""] + ["! " + w for w in warns] if warns else ["", "경고 없음"])))

    # 겹침을 밀도 교차점으로 옮길 여지가 있으면 제안한다. 폭은 그대로 두고 위치만 민다.
    spans, notes = BL.suggest_spans(wall, projs)
    diff = max(abs(a - p.u0) + abs(b - p.u1) for p, (a, b) in zip(projs, spans))
    if diff < 1.0:
        _log("이음매가 이미 밀도 교차점에 있습니다")
        return
    cur = "\n".join("  %-8s %6.3f ~ %6.3f m" % (p.name, p.u0 / 100.0, p.u1 / 100.0)
                    for p in projs)
    new = "\n".join("  %-8s %6.3f ~ %6.3f m" % (p.name, a / 100.0, b / 100.0)
                    for p, (a, b) in zip(projs, spans))
    msg = ("겹침을 밀도 교차점으로 옮기면 램프가 도는 동안 선명도가 변하지 않습니다.\n"
           "겹침 폭은 그대로 두고 위치만 옮깁니다.\n\n지금:\n%s\n\n제안:\n%s\n\n%s\n\n"
           "설정에 적용할까요?" % (cur, new, "\n".join(notes)))
    if not _ask("이음매 자동 산출", msg):
        return
    for r, (a, b) in zip(sorted(s.projectors, key=lambda q: q.span_start_m), spans):
        r.set_editor_property("span_start_m", a / S.M)
        r.set_editor_property("span_end_m", b / S.M)
    _log("담당 구간을 갱신했습니다. 저장을 눌러야 프리셋에 남습니다")
    _dialog("이음매 자동 산출", "담당 구간을 갱신했습니다.\n\n%s\n\n"
                             "'저장' 을 눌러야 프리셋 파일에 남습니다." % new)


def act_blend(s=None):
    """프로젝터마다 알파 블렌드 맵을 16비트 PGM 으로 만든다.

    겹침 구간에서 두 대의 알파 합이 항상 1 이 되도록 정규화한다. 램프 두 개를 그냥
    마주 놓으면 합이 1 이 안 되어 겹침이 밝거나 어둡게 뜬다.
    """
    s = current_settings() if s is None else s
    projs = S.to_projectors(s)
    if len(projs) < 2:
        raise RuntimeError("프로젝터가 2대 이상이라야 블렌딩할 것이 있습니다")
    wall = S.to_wall(s)
    lo, hi = BL.check_sum(wall, projs, s.blend_gamma)
    if abs(lo - 1.0) > 1e-6 or abs(hi - 1.0) > 1e-6:
        raise RuntimeError("알파 합이 1 이 아닙니다 (%.6f ~ %.6f). 담당 구간에 구멍이 "
                           "있는지 확인하세요." % (lo, hi))
    out = os.path.join(ROOT, "nDisplay", "blend")
    made = BL.write_maps(wall, projs, out, s.blend_gamma, _log)
    _log("알파 합 검사 통과 (%.6f ~ %.6f)" % (lo, hi))
    if _ask("블렌드 맵", "%d 장을 만들었습니다.\n\n%s\n\n폴더를 열까요?"
            % (len(made), "\n".join(os.path.basename(m) for m in made))):
        _open(out)


def act_preview(s=None):
    """평면도를 그린다. 이미 떠 있으면 지운다 (카메라도 원래 자리로 되돌린다)."""
    if PV.is_drawn():
        PV.clear()
        _log("평면도 지움")
        return
    s = current_settings() if s is None else s      # 설정 대화상자가 편집 중인 값을 넘긴다
    wall = S.to_wall(s)
    origin = (0.0, 0.0, s.eye_height_m * S.M)
    for a in B._actors().get_all_level_actors():
        if isinstance(a, unreal.DisplayClusterRootActor):
            loc = a.get_actor_location()
            origin = (loc.x, loc.y, loc.z)
            break
    PV.draw(wall, origin)


def act_build(s=None):
    s = current_settings() if s is None else s      # 설정 대화상자가 편집 중인 값을 넘긴다
    wall = S.to_wall(s)
    bad = wall.check()
    if bad:
        raise RuntimeError("형상이 잘못됨:\n  " + "\n  ".join(bad))
    o = _opts(s)
    B.build_level(wall, o)
    _log("빌드 완료")
    w = _warn_video_w(s, V.Plan(wall, o["res_w"]).out_w)
    if w:
        _dialog("벽 만들기", "빌드는 끝났습니다." + chr(10) * 2 + "! " + w)


def act_probe(s=None):
    """벽 뒤에 격자 방을 놓거나 지운다 (토글). 착시 검증용."""
    n = B.clear_probe_room()
    if n:
        _log("검증 방 지움 (%d)" % n)
        return
    s = current_settings() if s is None else s      # 설정 대화상자가 편집 중인 값을 넘긴다
    dcra = next((a for a in B._actors().get_all_level_actors()
                 if isinstance(a, unreal.DisplayClusterRootActor)), None)
    if dcra is None:
        raise RuntimeError("DCRA 가 없습니다. 먼저 '벽 만들기' 를 실행할 것")
    B.spawn_probe_room(dcra, S.to_wall(s))
    _log("검증 방 놓음. 클러스터 실행으로 코너가 사라지는지 볼 것")


def act_install_scripts():
    """플러그인이 들고 있는 배포 스크립트를 프로젝트 루트에 복사한다."""
    done, skipped = EN.install_scripts()
    if skipped and not done:
        if not _ask("배포 스크립트 설치",
                    "이미 있습니다: %s%s%s덮어쓸까요?"
                    % (", ".join(skipped), chr(10), chr(10))):
            return
        done, skipped = EN.install_scripts(overwrite=True)
    for n in done:
        _log("설치: " + n)
    _dialog("배포 스크립트 설치",
            "복사함: %s%s건너뜀: %s"
            % (", ".join(done) or "없음", chr(10), ", ".join(skipped) or "없음"))


def act_launch(s=None):
    s = current_settings() if s is None else s      # 설정 대화상자가 편집 중인 값을 넘긴다
    wall = S.to_wall(s)
    o = _opts(s)
    asset = "%s/%s.%s" % (o["asset_dir"], o["asset_name"], o["asset_name"])
    cfg, ww, wh = CF.build(wall, asset, o["res_w"], follow_player=o["follow_player"],
                           exit_on_esc=o["exit_on_esc"], per_node=o["per_node"])
    CF.write(cfg, o["cfg_path"])
    exe = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.engine_dir()),
                       "Binaries", "Win64", "UnrealEditor.exe")
    uproject = unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())
    level = unreal.EditorLevelLibrary.get_editor_world().get_path_name().split(".")[0]
    # 창이 모니터보다 크면 좌우가 잘려 착시를 볼 수가 없다. 비율을 지켜 줄이고 가운데에 놓는다.
    # 줄인 설정은 따로 쓴다. 원본 .ndisplay 는 현장에 나가는 파일이라 건드리지 않는다.
    path = o["cfg_path"]
    w, h, x, y, k = CF.fit_window(ww, wh, shrink=o["fit_preview"])
    if k < 1.0:
        cfg, w, h = CF.build(wall, asset, o["res_w"], follow_player=o["follow_player"],
                             exit_on_esc=o["exit_on_esc"], scale=k, per_node=o["per_node"])
        path = o["cfg_path"][:-len(".ndisplay")] + "_preview.ndisplay"
        CF.write(cfg, path)
        w, h, x, y, _ = CF.fit_window(w, h)
        _log("창 %dx%d 가 화면보다 커서 %d%% 로 줄였습니다 -> %dx%d "
             "(원본 크기로 보려면 '화면에 맞춰 축소' 를 끌 것)" % (ww, wh, k * 100, w, h))
        _log("미리보기 설정: %s (원본 %s 는 그대로)"
             % (os.path.basename(path), os.path.basename(o["cfg_path"])))
    # 노드마다 프로세스가 하나씩. 프라이머리(node_0)가 먼저 떠야 나머지가 붙는다.
    # x, y 는 캔버스를 화면 가운데에 놓는 오프셋이고, 노드 창은 캔버스 안의 제 자리에 놓인다.
    nodes = cfg["nDisplay"]["cluster"]["nodes"]
    order = CF.node_order(nodes)
    # 현장 배치(축소 끔)에서는 노드를 모니터에 하나씩 놓는다. 캔버스 좌표를 그대로 쓰면
    # 패널 화소 수가 모니터 크기와 달라 창 하나가 두 모니터에 걸친다.
    mons = [] if (o["fit_preview"] or len(order) < 2) else CF.monitors()
    spots = CF.place_on_monitors([(nodes[n]["window"]["w"], nodes[n]["window"]["h"])
                                  for n in order], mons)
    if len(order) > 1 and not o["fit_preview"] and spots is None:
        _log("모니터가 %d 대라 노드 %d 개를 하나씩 못 놓습니다. 캔버스 좌표로 이어 붙입니다"
             % (len(mons), len(order)))
    import subprocess
    for i, nname in enumerate(order):
        r = nodes[nname]["window"]
        wx, wy = spots[i] if spots else (x + r["x"], y + r["y"])
        args = CF.launch_args(exe, uproject, level, path, r["w"], r["h"],
                              win_x=wx, win_y=wy, node=nname,
                              hide_screen_messages=s.hide_screen_messages)
        _log("%s 실행: %dx%d  창 위치 (%d, %d)%s  뷰포트 %s"
             % (nname, r["w"], r["h"], wx, wy,
                ("  모니터 %d" % (i + 1)) if spots else "",
                ", ".join(sorted(nodes[nname]["viewports"]))))
        subprocess.Popen(args)
    area = CF.screen_bounds()
    if area and (ww > area[0] or wh > area[1]) and not o["fit_preview"]:
        _log("캔버스 %dx%d 가 화면 %dx%d 보다 큽니다. 화면 밖 창은 안 보입니다 "
             "(현장 출력이 붙으면 그 자리에 나갑니다)" % (ww, wh, area[0], area[1]))
    if len(nodes) > 1:
        _log("노드 %d 개. 프레임 동기는 소프트웨어 배리어(ethernet)다. "
             "창을 하나씩 닫으면 나머지가 동기를 기다리며 멈춘다" % len(nodes))
    _log("작업표시줄 자동 숨김과 디스플레이 배율 100% 를 확인할 것")


def _proj_setup(s):
    """프로젝터 변환에 필요한 것들. -> (wall, projs, plan, 블렌드 맵 경로 목록 또는 None)."""
    projs = S.to_projectors(s)
    if not projs:
        raise RuntimeError("프로젝터가 정의되지 않았습니다.\n"
                           "설정 편집 > 08 프로젝터 > 프로젝터 목록 에 추가하세요.")
    wall = S.to_wall(s)
    bad = wall.check()
    if bad:
        raise RuntimeError("형상이 잘못됨:\n  " + "\n  ".join(bad))
    _, warns = PJ.analyze(wall, projs, s.warn_grazing_deg, s.warn_blend_pct)
    if warns:
        if not _ask("프로젝터 영상 변환",
                    "배치에 경고가 %d 개 있습니다.\n\n%s\n\n그래도 변환할까요?"
                    % (len(warns), "\n".join("! " + w for w in warns))):
            return None
    maps = None
    if len(projs) > 1 and s.bake_blend:
        lo, hi = BL.check_sum(wall, projs, s.blend_gamma)
        if abs(lo - 1.0) > 1e-6 or abs(hi - 1.0) > 1e-6:
            raise RuntimeError("알파 합이 1 이 아닙니다 (%.6f ~ %.6f)" % (lo, hi))
        maps = BL.write_maps(wall, projs, os.path.join(ROOT, "nDisplay", "blend"),
                             s.blend_gamma, _log)
    return wall, projs, V.Plan(wall, S.res_w_of(s, wall)), maps


def _proj_out():
    d = os.path.join(movies_dir(), "proj")
    os.makedirs(d, exist_ok=True)
    return d


def act_proj_from_source(s=None):
    """원본에서 프로젝터별 영상을 만든다. 아나모픽과 프로젝터 워프를 한 번에 건다.

    두 왜곡을 파이썬에서 합성하므로 중간 '벽 이미지'가 실체로 생기지 않는다.
    프로젝터가 벽에 만드는 밀도를 담으려면 벽 이미지가 1만 픽셀을 넘는데, 합성하면
    그 래스터가 디스크에도 메모리에도 안 생기고 양자화 손실도 없다.
    """
    s = current_settings() if s is None else s
    got = _proj_setup(s)
    if got is None:
        return
    wall, projs, plan, maps = got
    src = _pick_file("변환할 원본 영상 고르기")
    if not src:
        return
    out = _proj_out()
    made = [V.convert_projector(wall, projs, p, plan, src, out,
                                alpha=(maps[i] if maps else None), log=_log)
            for i, p in enumerate(projs)]
    _finish_proj(made, out, maps)


def act_proj_from_wall(s=None):
    """이미 아나모픽이 걸린 벽 영상(_curved.mp4)에서 프로젝터별 영상을 만든다.

    아나모픽을 다시 걸지 않는다. 입력 해상도가 그대로 상한이라, 원본이 있으면
    '원본에서' 쪽이 화질이 낫다.
    """
    s = current_settings() if s is None else s
    got = _proj_setup(s)
    if got is None:
        return
    wall, projs, plan, maps = got
    src = _pick_file("이미 변환된 벽 영상 고르기")
    if not src:
        return
    size = V.probe_size(src)
    if size:
        need, ratio = V.wall_image_shortfall(wall, projs, size[0])
        if ratio > 1.05:
            if not _ask("프로젝터 영상 변환",
                        "벽 영상이 가로 %d px 인데 프로젝터를 다 살리려면 %d px 가 "
                        "필요합니다 (%.1f 배 부족).\n\n가장 촘촘한 구간에서 %.0f%% 만 "
                        "나옵니다. 원본이 있으면 '원본에서' 쪽이 낫습니다.\n\n"
                        "그래도 진행할까요?" % (size[0], need, ratio, 100.0 / ratio)):
                return
    out = _proj_out()
    made = [V.convert_projector_from_wall(wall, projs, p, plan, src, out,
                                          alpha=(maps[i] if maps else None), log=_log)
            for i, p in enumerate(projs)]
    _finish_proj(made, out, maps)


def _finish_proj(made, out, maps):
    note = ("블렌드를 구웠습니다." if maps else
            "블렌드는 굽지 않았습니다. nDisplay/blend 의 알파 맵을 재생 쪽에서 곱하세요.")
    _log(note)
    if _ask("프로젝터 영상 변환", "%d 장을 만들었습니다.\n\n%s\n\n%s\n\n폴더를 열까요?"
            % (len(made), "\n".join(os.path.basename(m) for m in made), note)):
        _open(out)


def act_convert_curved():
    _convert(True)


def act_convert_wall():
    _convert(False)


def _convert(curved):
    s = current_settings()
    wall = S.to_wall(s)
    plan = V.Plan(wall, S.res_w_of(s, wall))
    w = _warn_video_w(s, plan.out_w)
    if w and not _ask("영상 변환", "! " + w + chr(10) * 2 + "그래도 진행할까요?"):
        return
    src = _pick_file("변환할 영상 고르기")
    if not src:
        return
    out = movies_dir()
    if curved:
        msg, warn = R.band_warning(plan.plane()[6], s.warn_band_pct)
        _log(msg)
        if warn:
            unreal.log_warning("[AnamorphicRig] " + warn)
    dst = V.convert(plan, src, out, curved, _log)
    _log("만듦: " + dst)
    if _ask("영상 변환", "%s\n\n지금 열어 볼까요?" % dst):
        _open(dst)


def act_preview_video():
    s = current_settings()
    wall = S.to_wall(s)
    plan = V.Plan(wall, S.res_w_of(s, wall))
    src = _pick_file("되돌려 볼 전개 영상 고르기")
    if not src:
        return
    dst = V.preview(plan, src, movies_dir(), log=_log)
    _log("만듦 (검증 전용, 벽에 넣는 파일이 아님): " + dst)
    if _ask("눈 시점 미리보기",
            "%s\n\n격자가 곧게 펴져 있으면 설정이 맞는 것입니다.\n\n지금 열어 볼까요?" % dst):
        _open(dst)


def act_merge():
    """MRQ 가 뷰포트마다 뽑은 파일을 붙인다. 순서는 설정의 패널 순서를 따른다.

    파일명 알파벳순으로 붙이면 패널 이름에 따라 좌우가 뒤집힌다
    (예: Center/Left/Right 는 알파벳순이 가운데부터다).
    """
    d = os.path.join(ROOT, "Saved", "MovieRenders")
    got = [f for f in sorted(os.listdir(d)) if f.lower().endswith(".mp4")] if os.path.isdir(d) else []
    got = [f for f in got if "_merged" not in f]

    wall = S.to_wall(current_settings())
    panels = getattr(wall, "panels", None)      # 커브드 벽은 뷰포트가 하나라 붙일 게 없다
    if not panels or len(panels) < 2:
        raise RuntimeError("뷰포트가 하나뿐입니다. MRQ 결과를 그대로 영상 파일에 넣으면 됩니다")
    order = [CF.viewport_name(p.name) for p in panels]
    picked = []
    for vp in order:
        hit = [f for f in got if vp in f]
        if not hit:
            raise RuntimeError(
                "뷰포트 %s 의 렌더 결과를 못 찾았습니다.\n"
                "  찾아본 곳: %s\n  있는 파일: %s\n"
                "MRQ 출력 파일명에 뷰포트 이름이 들어가야 합니다 (기본 {render_pass})."
                % (vp, d, got or "없음"))
        if len(hit) > 1:
            raise RuntimeError("뷰포트 %s 에 해당하는 파일이 여러 개입니다: %s\n"
                               "예전 렌더 결과를 치우고 다시 하세요." % (vp, hit))
        picked.append(hit[0])
    got = picked
    _log("붙이는 순서 (설정의 패널 순서): " + ", ".join(got))

    dst = os.path.join(d, os.path.splitext(got[0])[0].rsplit("vp_", 1)[0] + "merged.mp4")
    V.merge_side_by_side([os.path.join(d, f) for f in got], dst, _log)
    if _ask("좌우 합치기", "%s\n\n지금 열어 볼까요?" % dst):
        _open(dst)


def act_check_mrq():
    """MRQ 출력 해상도가 뷰포트와 맞는지. 안 맞으면 렌더 결과가 조용히 다른 크기로 나온다."""
    s = current_settings()
    wall = S.to_wall(s)
    _, vps, ww, wh = CF.screens_and_viewports(wall, _opts(s)["res_w"])
    lines = ["뷰포트 해상도:"]
    for n, v in sorted(vps.items()):
        lines.append("  %-12s %d x %d" % (n, v["region"]["w"], v["region"]["h"]))
    lines += ["", "무비 렌더 큐는 .ndisplay 파일이 아니라 레벨의 DCRA 에 구워진 값을 쓴다.",
              "'벽 만들기' 를 한 번 돌리면 위 값이 DCRA 에 반영된다.",
              "Movie Graph 의 Output Resolution 은 별개이며 전 뷰포트에 공통 적용된다."]
    w = _warn_video_w(s, max(v["region"]["w"] for v in vps.values()))
    if w:
        lines += ["", "! " + w,
                  "  MRQ 의 MP4 인코더는 플랫폼 하드웨어 인코더라 대개 4096 에서 막힌다.",
                  "  이미지 시퀀스 노드로 바꾸거나 벽 해상도를 낮출 것."]
    for l in lines:
        _log(l)
    _dialog("무비 렌더 큐 점검", "\n".join(lines))


def _pick_file(title):
    """영상 파일 고르기.

    블루프린트에 노출된 파일 대화상자 API 가 없어서, FilePath 프로퍼티 하나짜리
    임시 객체를 디테일 패널로 띄운다. FilePath 는 찾아보기 버튼이 붙는다.
    """
    o = unreal.new_object(S.ARFilePick.static_class())
    if not _details(title, o, 560, 140):
        return None
    p = o.file.get_editor_property("file_path")
    if not p:
        return None
    if os.path.isabs(p):
        return p
    for cand in (os.path.join(ROOT, p), os.path.join(movies_dir(), os.path.basename(p))):
        if os.path.isfile(cand):
            return cand
    return os.path.join(ROOT, p)


def act_video():
    """영상 도구를 모달리스 탭으로 연다. 설정 편집과 같은 방식이다 (act_edit 참고).

    설정 패널과 달리 값을 안 들고 있어서 편집 중인 상태를 살려 둘 이유가 없다.
    누를 때마다 새로 만든다.
    """
    panel = unreal.new_object(S.ARVideoTools.static_class())
    sub = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
    if not sub.open_editor_for_assets([panel]):
        _details("영상 도구", panel, 560, 360)


# --- 등록 -------------------------------------------------------------------
# 메뉴는 모달이 아니라, 누르는 즉시 뷰포트가 그대로 보인다. 평면도처럼 뷰포트를 봐야
# 하는 동작은 설정 대화상자 안의 버튼보다 여기가 낫다. 섹션으로 묶어 둔다.
GROUPS = [
    ("Preset", "프리셋", [
        ("Edit", "설정 편집", "설정을 모달리스 탭으로 연다. 탭 안의 저장 버튼이 프리셋에 기록한다", act_edit),
        ("Load", "프리셋 불러오기", "저장된 현장 목록에서 골라 활성으로 삼는다", act_load),
        ("SaveAs", "프리셋 다른 이름으로 저장", "지금 값을 새 이름으로 복사한다", act_save_as),
    ]),
    ("Wall", "벽", [
        ("Probe", "검증 방 놓기 / 지우기",
         "벽 뒤에 격자 방을 판다. 착시가 맞으면 코너가 사라진다. 다시 누르면 지운다", act_probe),
        ("Scripts", "배포 스크립트 설치",
         "Package.bat / Run_Packaged.ps1 등을 프로젝트 루트에 복사한다. 플러그인만 받았을 때 한 번 누른다", act_install_scripts),
        ("Proj", "프로젝터 배치 점검", "담당 구간·화각·입사각·겹침·밀도 교차점을 낸다", act_projectors),
        ("Blend", "블렌드 맵 만들기", "프로젝터별 알파 맵을 nDisplay/blend 에 쓴다", act_blend),
    ]),
    ("Video", "영상", [
        ("Video", "영상 도구", "변환·미리보기·렌더 결과를 모달리스 탭으로 연다", act_video),
    ]),
]

ENTRIES = [e for _, _, es in GROUPS for e in es]


def register():
    menus = unreal.ToolMenus.get()
    tools = menus.find_menu(MENU)
    if not tools:
        unreal.log_warning("[AnamorphicRig] %s 메뉴를 못 찾음. 등록 건너뜀" % MENU)
        return
    sub = tools.add_sub_menu(MENU, SECTION, "AnamorphicRig", "Anamorphic Rig")
    for sec, label, entries in GROUPS:
        sub.add_section(sec, label)
        for key, name, tip, _fn in entries:
            e = unreal.ToolMenuEntry(name=key, type=unreal.MultiBlockType.MENU_ENTRY)
            e.set_label(name)
            e.set_tool_tip(tip)
            e.set_string_command(unreal.ToolMenuStringCommandType.PYTHON, "",
                                 "import anamorphic_rig.menu as m; m.run('%s')" % key)
            sub.add_menu_entry(sec, e)
    menus.refresh_all_widgets()
    unreal.log("[AnamorphicRig] 메뉴 등록: Tools > Anamorphic Rig")


def run(key):
    """메뉴 항목 하나를 실행한다. 예외는 대화상자로 보여 준다."""
    fn = dict((k, f) for k, _, _, f in ENTRIES).get(key)
    if not fn:
        unreal.log_error("[AnamorphicRig] 알 수 없는 항목: %s" % key)
        return
    try:
        fn()
    except Exception as e:                       # 메뉴에서 터지면 로그만 남고 사용자는 모른다
        unreal.log_error("[AnamorphicRig] %s: %s" % (key, e))
        _dialog("Anamorphic Rig", str(e))
