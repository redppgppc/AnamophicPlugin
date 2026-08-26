"""에디터 메뉴 등록. 설정 에셋을 골라 놓고 버튼을 누르면 동작한다.

버튼이 하는 일은 전부 다른 모듈에 있다. 여기는 배선만 한다.
"""
import os

import unreal

from . import build as B
from . import config as CF
from . import presets as PR
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
    lines, warns = R.summarize(wall, s.warn_grazing_deg, s.warn_band_pct, s.warn_density_ratio)
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
        root=ROOT, res_w=2560,
        video=S.video_path_of(s), video_passthrough=s.video_passthrough,
        exposure_bias=s.exposure_bias, rig_origin=(0.0, 0.0, s.eye_height_m * S.M),
        show_floor=s.show_floor, eye_height=s.eye_height_m * S.M,
        arc_seg=s.arc_seg, face_seg=s.face_seg, seg_v=s.seg_v,
        flip_v=s.flip_v, flip_winding=s.flip_winding)


# --- 버튼 -------------------------------------------------------------------
def act_check(s=None):
    s = current_settings() if s is None else s      # 설정 대화상자가 편집 중인 값을 넘긴다
    wall = S.to_wall(s)
    lines, warns = R.summarize(wall, s.warn_grazing_deg, s.warn_band_pct, s.warn_density_ratio)
    for l in lines:
        _log(l)
    for w in warns:
        unreal.log_warning("[AnamorphicRig] " + w)
    o = _opts(s)
    lines = lines + ["", "프리셋 %s -> 에셋 %s/%s"
                     % (S.preset_of(s) or PR.active(), o["asset_dir"], o["asset_name"])]
    _dialog("형상 점검", "\n".join(lines + ([""] + ["! " + w for w in warns] if warns else [])))


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
    B.build_level(wall, _opts(s))
    _log("빌드 완료")


def act_launch(s=None):
    s = current_settings() if s is None else s      # 설정 대화상자가 편집 중인 값을 넘긴다
    wall = S.to_wall(s)
    o = _opts(s)
    cfg, ww, wh = CF.build(wall, "%s/%s.%s" % (o["asset_dir"], o["asset_name"], o["asset_name"]),
                           o["res_w"])
    CF.write(cfg, o["cfg_path"])
    exe = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.engine_dir()),
                       "Binaries", "Win64", "UnrealEditor.exe")
    uproject = unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())
    level = unreal.EditorLevelLibrary.get_editor_world().get_path_name().split(".")[0]
    args = CF.launch_args(exe, uproject, level, o["cfg_path"], ww, wh,
                          hide_screen_messages=s.hide_screen_messages)
    _log("클러스터 실행: %dx%d" % (ww, wh))
    _log("작업표시줄 자동 숨김과 디스플레이 배율 100%% 를 확인할 것")
    import subprocess
    subprocess.Popen(args)


def act_convert_curved():
    _convert(True)


def act_convert_wall():
    _convert(False)


def _convert(curved):
    s = current_settings()
    plan = V.Plan(S.to_wall(s))
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
    plan = V.Plan(S.to_wall(s))
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
        ("Check", "형상 점검", "치수·화각·입사각과 경고를 출력 로그에 찍는다", act_check),
        ("Plan", "평면도 보기 / 지우기", "에디터 뷰포트에 평면도를 그린다. 다시 누르면 지운다", act_preview),
        ("Build", "벽 만들기", "워프 메시와 리그를 현재 레벨에 만든다", act_build),
        ("Launch", "클러스터 실행", "nDisplay 창을 별도 프로세스로 띄운다", act_launch),
    ]),
    ("Video", "영상", [
        ("Curved", "영상 변환 (아나모픽)", "받은 영상을 벽 형상에 맞게 역왜곡한다", act_convert_curved),
        ("Wall2", "영상 변환 (전개만)", "꺾임 보정 없이 비율만 맞춘다", act_convert_wall),
        ("Eye", "눈 시점으로 되돌려 보기", "벽 없이 착시가 맞는지 확인한다. 납품물 아님", act_preview_video),
        ("MRQ", "무비 렌더 큐 점검", "출력 해상도가 뷰포트와 맞는지 본다", act_check_mrq),
        ("Merge", "렌더 결과 좌우 합치기", "Saved/MovieRenders 의 뷰포트 파일을 가로로 붙인다", act_merge),
        ("Movies", "출력 폴더 열기", "변환한 영상이 쌓이는 Content/Movies 를 연다", act_open_movies),
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
