"""에디터에 노출되는 설정. unreal.uclass / ustruct 로 정의하면 디테일 패널이 자동 생성된다.

이 모듈은 언리얼 안에서만 import 된다. 형상 계산은 geometry.py 가 하고,
여기서는 UI 표현과 geometry 객체로의 변환만 담당한다.

단위는 UI 에서 m 로 받고 내부에서 cm 로 바꾼다. 도면 값을 그대로 타이핑할 수 있는
단위가 실수가 가장 적다.

주의: 이 클래스는 **에셋으로 저장할 수 없다.** 파이썬으로 정의한 UClass 를 엔진이
transient 로 취급하기 때문이다. 값은 presets.py 가 JSON 파일에 넣고, 이 객체는
디테일 패널을 띄우기 위한 임시 그릇으로만 쓴다.
"""
import unreal

from . import geometry as G

M = 100.0   # m -> cm


# ---------------------------------------------------------------------------
# 디테일 패널의 순서에 대하여
#
# 파이썬으로 정의한 UClass 는 필드가 **선언의 역순**으로 순회된다. 그래서
#   1) 카테고리 순서   TFieldIterator 로 처음 만나는 순서를 따른다 (ObjectPropertyNode.cpp
#                     의 GetCategoryProperties). 사용자 정의 정렬은 블루프린트 전용이라
#                     여기엔 안 먹는다. -> **카테고리 블록을 역순으로 선언**해서 맞춘다.
#   2) 카테고리 안 순서 DisplayPriority 메타로 정한다 (PropertyEditorHelpers.cpp 의
#                     OrderPropertiesFromMetadata). 작은 값이 위로 간다.
#
# 그래서 아래 블록은 07 -> 01 로 거꾸로 적혀 있다. 화면에는 01 -> 07 로 나온다.
# 새 프로퍼티를 넣을 때는 DisplayPriority 도 같이 줄 것. 안 주면 그 카테고리의 맨 아래로 간다.
# ---------------------------------------------------------------------------


def _m(cat, prio, **kw):
    """카테고리·순서·기타 메타를 한 번에. 반복을 줄이려는 것뿐이다."""
    d = dict(Category=cat, DisplayPriority=str(prio))
    d.update(kw)
    return d


BENT = dict(EditCondition="bent_wall", EditConditionHides=True)
FLAT = dict(EditCondition="!bent_wall", EditConditionHides=True)


@unreal.ustruct()
class ARPanel(unreal.StructBase):
    """화면 한 장. 구조체 안에서도 순서가 뒤집히므로 DisplayPriority 로 고정한다."""
    free_yaw = unreal.uproperty(float, meta=_m("패널", 110, DisplayName="법선 방향 (도)",
                                               EditCondition="detached"))
    free_y_m = unreal.uproperty(float, meta=_m("패널", 100, DisplayName="평면 Y (m)",
                                               EditCondition="detached"))
    free_x_m = unreal.uproperty(float, meta=_m("패널", 90, DisplayName="평면 X (m)",
                                               EditCondition="detached"))
    detached = unreal.uproperty(bool, meta=_m("패널", 80, DisplayName="체인에서 분리",
                                          ToolTip="켜면 앞 패널과 이어 붙이지 않고 좌표를 직접 쓴다"))
    res_y = unreal.uproperty(int, meta=_m("패널", 70, DisplayName="세로 (px)",
                                          EditCondition="!auto_res"))
    res_x = unreal.uproperty(int, meta=_m("패널", 60, DisplayName="가로 (px)",
                                          EditCondition="!auto_res"))
    auto_res = unreal.uproperty(bool, meta=_m("패널", 50, DisplayName="해상도를 피치에서 자동",
                                          ToolTip="끄면 아래 픽셀 값을 직접 입력한다"))
    panel_base_m = unreal.uproperty(float, meta=_m("패널", 40,
        DisplayName="관람 바닥에서 화면 하단 (m)",
        ToolTip="기준면은 눈높이와 같아야 한다. 관람자가 서는 바닥을 쓴다.\n"
                "벽이 더 낮은 지대에 서 있으면 음수가 된다. 그게 정상이다.\n"
                "예: 관람 지대가 벽 지대보다 3 m 높고 벽 하단이 제 지대에서 5 m -> 2.0"))
    height_m = unreal.uproperty(float, meta=_m("패널", 30, DisplayName="세로 (m)", ClampMin="0.01"))
    width_m = unreal.uproperty(float, meta=_m("패널", 20, DisplayName="가로 (m)", ClampMin="0.01",
                                          ToolTip="표시 영역 실측 가로. 사양서 말고 자로 잰 값"))
    name = unreal.uproperty(str, meta=_m("패널", 10, DisplayName="이름"))


@unreal.ustruct()
class ARSeam(unreal.StructBase):
    """패널 사이의 이음매. 앞 패널에서 몇 도 꺾이는지만 주면 된다."""
    gap_m = unreal.uproperty(float, meta=_m("이음매", 30, DisplayName="틈 (m)", ClampMin="0"))
    convex = unreal.uproperty(bool, meta=_m("이음매", 20, DisplayName="볼록",
                                        ToolTip="켜면 코너가 관람자 쪽으로 튀어나온다"))
    turn_deg = unreal.uproperty(float, meta=_m("이음매", 10, DisplayName="꺾임 (도)",
                                               ClampMin="0", ClampMax="179",
                                           ToolTip="도면에서 읽은 각. 0 이면 일직선"))


@unreal.ustruct()
class ARProjector(unreal.StructBase):
    """프로젝터 한 대. 담당 구간은 겹침을 포함한 실제 투사 범위다."""
    res_y = unreal.uproperty(int, meta=_m("프로젝터", 80, DisplayName="세로 (px)"))
    res_x = unreal.uproperty(int, meta=_m("프로젝터", 70, DisplayName="가로 (px)"))
    height_m = unreal.uproperty(float, meta=_m("프로젝터", 60,
        DisplayName="관람 바닥에서 높이 (m)",
        ToolTip="0 이면 벽 세로 한가운데. 벽 중앙을 벗어나면 세로 입사각이 생긴다"))
    free_y_m = unreal.uproperty(float, meta=_m("프로젝터", 50, DisplayName="평면 Y (m)",
                                               EditCondition="place_free"))
    free_x_m = unreal.uproperty(float, meta=_m("프로젝터", 40, DisplayName="평면 X (m)",
                                               EditCondition="place_free"))
    place_free = unreal.uproperty(bool, meta=_m("프로젝터", 30, DisplayName="좌표 직접 지정",
        ToolTip="끄면 담당 구간 한가운데의 벽 법선에서 물러난 거리로 배치한다"))
    back_m = unreal.uproperty(float, meta=_m("프로젝터", 20, DisplayName="벽에서 물러난 거리 (m)",
        ClampMin="0.1", EditCondition="!place_free",
        ToolTip="담당 구간 한가운데의 법선을 따라 뒤로. 멀수록 화각이 좁고 입사각이 균일해진다"))
    span_end_m = unreal.uproperty(float, meta=_m("프로젝터", 15, DisplayName="담당 끝 (m)",
        ToolTip="전개 좌표. 옆 프로젝터와 겹치도록 넉넉히 준다"))
    span_start_m = unreal.uproperty(float, meta=_m("프로젝터", 12, DisplayName="담당 시작 (m)",
        ToolTip="전개 좌표. 왼쪽 끝이 0"))
    name = unreal.uproperty(str, meta=_m("프로젝터", 10, DisplayName="이름"))


@unreal.uclass()
class ARFilePick(unreal.Object):
    """파일 하나를 고르기 위한 임시 그릇. FilePath 는 찾아보기 버튼이 붙는다."""
    file = unreal.uproperty(unreal.FilePath, meta=dict(DisplayName="파일", FilePathFilter="mp4"))


@unreal.uclass()
class AnamorphicRigSettings(unreal.Object):
    """현장 하나의 설정. 값은 JSON 프리셋 파일에 저장된다 (presets.py)."""

    # === 08 프로젝터 ======================================================
    # 비워 두면 프로젝터 관련 기능이 전부 꺼진다. LED 벽이면 그대로 두면 된다.
    warn_blend_pct = unreal.uproperty(float, meta=_m("08 프로젝터", 30,
        DisplayName="겹침 폭 경고 (%)",
        ToolTip="겹침이 좁은 쪽 담당의 이 비율보다 작으면 경고. 알파 램프가 돌 폭이 필요하다"))
    bake_blend = unreal.uproperty(bool, meta=_m("08 프로젝터", 50,
        DisplayName="블렌드를 영상에 굽기",
        ToolTip="끄면 워프만 하고 알파는 nDisplay/blend 에 따로 남긴다. 블렌딩은 현장에서\n"
                "눈으로 보며 조정하게 되므로 재생 쪽에서 곱하는 편이 대개 낫다.\n"
                "재생 장비가 단순 플레이어뿐이면 켠다"))
    blend_gamma = unreal.uproperty(float, meta=_m("08 프로젝터", 40,
        DisplayName="블렌드 커브 감마", ClampMin="0.2", ClampMax="5.0",
        ToolTip="1 이면 대칭 램프. 올리면 선명한 쪽이 더 오래 지배해 겹침 구간의\n"
                "선명도 저하 구간이 좁아진다. 합은 항상 1 로 유지된다"))
    projectors = unreal.uproperty(unreal.Array(ARProjector), meta=_m("08 프로젝터", 10,
        DisplayName="프로젝터 목록",
        ToolTip="관람자 기준 왼쪽부터. 비워 두면 프로젝터 검토를 하지 않는다"))

    # === 07 경고 기준 =====================================================
    warn_density_ratio = unreal.uproperty(float, meta=_m("07 경고 기준", 30,
        DisplayName="화소 밀도 차 경고 (배)"))
    warn_band_pct = unreal.uproperty(float, meta=_m("07 경고 기준", 20,
        DisplayName="안전 세로 밴드 경고 (%)"))
    warn_grazing_deg = unreal.uproperty(float, meta=_m("07 경고 기준", 10,
        DisplayName="입사각 경고 (도)",
        ToolTip="벽 끝의 입사각이 이 값보다 작으면 경고. 그 아래로는 픽셀이 가로로 뭉개진다"))

    # === 06 고급 (워프 메시) ==============================================
    flip_winding = unreal.uproperty(bool, meta=_m("06 고급", 50, DisplayName="면 뒤집기",
        ToolTip="벽이 통째로 까맣게 나오면 켠다 (백페이스 컬링)", **BENT))
    flip_v = unreal.uproperty(bool, meta=_m("06 고급", 40, DisplayName="UV 상하 뒤집기",
        ToolTip="영상이 위아래로 뒤집혀 보이면 끈다", **BENT))
    seg_v = unreal.uproperty(int, meta=_m("06 고급", 30, DisplayName="세로 분할",
        ClampMin="1", **BENT))
    face_seg = unreal.uproperty(int, meta=_m("06 고급", 20, DisplayName="면 분할",
        ClampMin="1", **BENT))
    arc_seg = unreal.uproperty(int, meta=_m("06 고급", 10, DisplayName="호 분할",
        ClampMin="1", **BENT))

    # === 05 출력 ==========================================================
    exit_on_esc = unreal.uproperty(bool, meta=_m("05 출력", 70, DisplayName="ESC 로 종료",
        ToolTip="끄면 ESC 를 눌러도 클러스터가 안 꺼진다. 전시 현장에서는 꺼 두는 편이 안전하다"))
    follow_player = unreal.uproperty(bool, meta=_m("05 출력", 60,
        DisplayName="플레이어 카메라 따라가기",
        ToolTip="켜면 리그가 로컬 플레이어 카메라를 따라간다. 폰을 조종하면 벽 화면도 같이 움직인다. "
                "벽이 리그에 붙어 다니므로 아나모픽은 그대로 맞는다. "
                "관람자가 한자리에 서는 전시에서는 끈다"))
    show_floor = unreal.uproperty(bool, meta=_m("05 출력", 50, DisplayName="바닥 만들기",
        ToolTip="벽 아래에 격자 바닥을 깐다. 빈 맵에서 벽만 떠 있으면 거리감이 없어\n"
                "착시가 맞는지 눈으로 판단하기 어렵다"))
    hide_screen_messages = unreal.uproperty(bool, meta=_m("05 출력", 40,
        DisplayName="디버그 오버레이 숨김",
        ToolTip="주의: 온스크린 경고를 전부 끈다. 개발 중에는 끄는 게 안전하다"))
    exposure_bias = unreal.uproperty(float, meta=_m("05 출력", 30,
        DisplayName="노출 보정 (EV)", EditCondition="video_passthrough"))
    video_passthrough = unreal.uproperty(bool, meta=_m("05 출력", 20,
        DisplayName="영상 1:1 패스스루",
        ToolTip="자동노출과 ACES 톤커브를 꺼서 파일 색이 그대로 나간다. 3D 를 섞으면 끌 것"))
    video_path = unreal.uproperty(unreal.FilePath, meta=_m("05 출력", 10,
        DisplayName="영상 파일", FilePathFilter="mp4", RelativeToGameDir=True,
        ToolTip="벽에 붙일 영상. 오른쪽 ... 버튼으로 고른다. 비우면 영상 없음.\n"
                "보통 '영상 변환 (아나모픽)' 이 만든 _curved.mp4 를 넣는다"))

    # === 04 LED ===========================================================
    pitch_mm = unreal.uproperty(float, meta=_m("04 LED", 10, DisplayName="픽셀 피치 (mm)",
        ClampMin="0", ToolTip="패널의 '해상도를 피치에서 자동' 이 켜져 있으면 크기에서 유도한다",
        **FLAT))

    # === 03 스위트스팟 ====================================================
    rotate_deg = unreal.uproperty(float, meta=_m("03 스위트스팟", 50,
        DisplayName="전체 회전 (도)", ToolTip="자동 정렬에서 미세 조정", **FLAT))
    anchor_seam = unreal.uproperty(int, meta=_m("03 스위트스팟", 40,
        DisplayName="정면에 둘 이음매",
        ToolTip="0 = 첫 패널 왼쪽 끝, 1 = 1-2번 사이, ... -1 = 전체 중앙", **FLAT))
    eye_offset_m = unreal.uproperty(float, meta=_m("03 스위트스팟", 30,
        DisplayName="좌우 치우침 (m)", ToolTip="대칭축에서 벗어난 거리. + 가 오른쪽", **BENT))
    eye_height_m = unreal.uproperty(float, meta=_m("03 스위트스팟", 20,
        DisplayName="눈높이 (m)",
        ToolTip="관람자가 서는 바닥에서 눈까지. 서면 1.5~1.7, 앉으면 1.1~1.2.\n"
                "벽 높이 값과 반드시 같은 기준면에서 재야 한다. 리그는 둘의 차이만 쓴다"))
    eye_dist_m = unreal.uproperty(float, meta=_m("03 스위트스팟", 10,
        DisplayName="관람 거리 (m)",
        ToolTip="눈에서 기준 지점까지, 정면 방향 거리. 직선거리가 아니다"))

    # === 02 다중 패널 =====================================================
    seams = unreal.uproperty(unreal.Array(ARSeam), meta=_m("02 다중 패널", 20,
        DisplayName="이음매", ToolTip="패널보다 정확히 하나 적어야 한다. 패널 2장이면 이음매 1개",
        **FLAT))
    panels = unreal.uproperty(unreal.Array(ARPanel), meta=_m("02 다중 패널", 10,
        DisplayName="패널 목록", ToolTip="관람자 기준 왼쪽부터. 크기와 해상도가 달라도 된다",
        **FLAT))

    # === 02 꺾인 벽 =======================================================
    base_m = unreal.uproperty(float, meta=_m("02 꺾인 벽", 70,
        DisplayName="관람 바닥에서 벽 하단 (m)",
        ToolTip="건물 외벽에 매달린 벽이면 5 등. 0 이면 관람 바닥에 붙는다.\n"
                "기준면은 눈높이와 같아야 한다. 관람자가 서는 바닥을 쓴다.\n"
                "벽이 더 낮은 지대에 서 있으면 음수가 된다. 그게 정상이다", **BENT))
    convex = unreal.uproperty(bool, meta=_m("02 꺾인 벽", 60,
        DisplayName="볼록 (코너가 관람자 쪽)", **BENT))
    fillet_r_m = unreal.uproperty(float, meta=_m("02 꺾인 벽", 50,
        DisplayName="코너 라운드 반지름 (m)", ClampMin="0", **BENT))
    bend_deg = unreal.uproperty(float, meta=_m("02 꺾인 벽", 40,
        DisplayName="꺾임 (도)", ClampMin="0", ClampMax="179", **BENT))
    wall_height_m = unreal.uproperty(float, meta=_m("02 꺾인 벽", 30,
        DisplayName="벽 높이 (m)", **BENT))
    face_a_m = unreal.uproperty(float, meta=_m("02 꺾인 벽", 20,
        DisplayName="오른쪽 면 길이 (m)", ToolTip="왼쪽과 달라도 된다", **BENT))
    face_b_m = unreal.uproperty(float, meta=_m("02 꺾인 벽", 10,
        DisplayName="왼쪽 면 길이 (m)", ToolTip="전개 길이. 코너 호는 포함하지 않는다", **BENT))

    # === 01 벽 종류 =======================================================
    bent_wall = unreal.uproperty(bool, meta=_m("01 벽 종류", 10,
        DisplayName="꺾인 벽 (한 장 연속)",
        ToolTip="켜면 코너에서 둥글게 꺾인 연속 벽 한 장. 워프 메시를 굽는다.\n"
                "끄면 평평한 화면 여러 장을 이어 붙인 다중 패널."))

    # === 실행 =============================================================
    # CallInEditor 가 붙은 무인자 UFUNCTION 은 디테일 패널에서 버튼으로 그려진다
    # (FObjectDetails::AddCallInEditorMethods). 버튼 순서는 프로퍼티와 달리 선언 순서와
    # 무관하고, 카테고리 -> DisplayPriority -> 이름 순으로 정렬된다
    # (PropertyCustomizationHelpers.cpp 의 GetCallInEditorFunctionsForClassInternal).
    # 그래서 프로퍼티와 같은 _m() 을 그대로 쓰면 된다.
    #
    # 여기서 도는 동작은 이 대화상자가 들고 있는 **편집 중인 값**을 쓴다. 확인을 눌러
    # 저장하기 전에 그대로 시험해 볼 수 있다는 뜻이다.
    #
    # 이 패널은 모달리스 탭이라 (menu.act_edit 참고) 뷰포트를 보면서 눌러도 된다.
    # 자동 저장이 아니므로 '저장' 을 눌러야 프리셋 파일에 남는다.

    @unreal.ufunction(meta=_m("실행", 40, CallInEditor="true",
                            DisplayName="클러스터 실행",
                            ToolTip="nDisplay 창을 별도 프로세스로 띄운다. 먼저 벽 만들기를 할 것"))
    def act_launch(self):
        self._run(lambda m: m.act_launch(self))

    @unreal.ufunction(meta=_m("실행", 30, CallInEditor="true",
                            DisplayName="벽 만들기",
                            ToolTip="워프 메시와 리그를 현재 레벨에 만들고 레벨을 저장한다"))
    def act_build(self):
        self._run(lambda m: m.act_build(self))

    @unreal.ufunction(meta=_m("실행", 20, CallInEditor="true",
                            DisplayName="평면도 보기 / 지우기",
                            ToolTip="에디터 뷰포트에 평면도를 그린다. 한 번 더 누르면 지운다"))
    def act_preview(self):
        self._run(lambda m: m.act_preview(self))

    @unreal.ufunction(meta=_m("실행", 5, CallInEditor="true",
                            DisplayName="저장",
                            ToolTip="지금 값을 활성 프리셋 파일에 기록한다. 이 탭은 자동 저장이 아니다"))
    def act_save(self):
        self._run(lambda m: m.act_save(self))

    @unreal.ufunction(meta=_m("실행", 10, CallInEditor="true",
                            DisplayName="형상 점검",
                            ToolTip="치수·화각·입사각과 경고를 대화상자와 출력 로그에 낸다"))
    def act_check(self):
        self._run(lambda m: m.act_check(self))

    def _run(self, fn):
        """버튼 하나를 돌린다. 여기서 터지면 로그에만 남고 사용자는 모르므로 대화상자로 보여 준다."""
        from . import menu as MN          # 늦게 import 한다 (menu 가 이 모듈을 쓴다)
        try:
            fn(MN)
        except Exception as e:
            unreal.log_error("[AnamorphicRig] %s" % e)
            MN._dialog("Anamorphic Rig", str(e))

    # === 00 프리셋 ========================================================
    # 어느 프리셋을 편집 중인지 패널에서 바로 보이게 한다. 탭을 여러 개 띄우거나
    # 도중에 다른 프리셋을 불러오면 활성 이름만으로는 어느 값이 어디로 저장될지
    # 알 수 없다. 그래서 이름을 설정 객체가 직접 들고 다닌다 (저장 대상도 이걸 쓴다).
    preset_name = unreal.uproperty(str, meta=_m("00 프리셋", 10, DisplayName="프리셋",
        EditCondition="false", ToolTip="이 패널의 '저장' 이 기록할 대상. 바꾸려면 "
                                       "Tools > Anamorphic Rig > 프리셋 불러오기"))

    def _post_init(self):
        """언리얼이 새 인스턴스를 만들 때 부르는 훅. 쓸 만한 기본값을 넣는다."""
        self.set_editor_properties(dict(
            bent_wall=True,
            face_b_m=36.5365045915, face_a_m=36.5365045915, wall_height_m=21.0,
            bend_deg=90.0, fillet_r_m=2.5, convex=True, base_m=0.0,
            eye_dist_m=35.0, eye_offset_m=0.0, eye_height_m=1.6,
            anchor_seam=1, rotate_deg=0.0, pitch_mm=7.8,
            video_passthrough=True, exposure_bias=0.0,
            hide_screen_messages=True, show_floor=True,
            follow_player=False, exit_on_esc=True,
            arc_seg=24, face_seg=8, seg_v=4, flip_v=True, flip_winding=False,
            warn_grazing_deg=20.0, warn_band_pct=60.0, warn_density_ratio=2.0,
            warn_blend_pct=8.0, blend_gamma=1.0, bake_blend=False,
        ))


# --- JSON 직렬화 -----------------------------------------------------------
# 필드를 여기 한곳에만 적는다. 새 knob 을 추가하면 이 목록에도 넣어야 저장된다.
SCALARS = ("bent_wall", "face_b_m", "face_a_m", "wall_height_m", "bend_deg", "fillet_r_m",
           "convex", "base_m", "eye_dist_m", "eye_offset_m", "eye_height_m", "anchor_seam",
           "rotate_deg", "pitch_mm", "video_path", "video_passthrough", "exposure_bias",
           "hide_screen_messages", "show_floor", "follow_player", "exit_on_esc",
           "arc_seg", "face_seg", "seg_v",
           "flip_v", "flip_winding", "warn_grazing_deg", "warn_band_pct", "warn_density_ratio",
           "warn_blend_pct", "blend_gamma", "bake_blend")
PROJ_FIELDS = ("name", "span_start_m", "span_end_m", "back_m", "place_free",
               "free_x_m", "free_y_m", "height_m", "res_x", "res_y")
PANEL_FIELDS = ("name", "width_m", "height_m", "panel_base_m", "auto_res", "res_x", "res_y",
                "detached", "free_x_m", "free_y_m", "free_yaw")
SEAM_FIELDS = ("turn_deg", "convex", "gap_m")


def new_settings(preset=""):
    """기본값이 채워진 임시 설정 객체.

    preset 을 주면 객체 이름에도 넣는다. 범용 프로퍼티 에디터의 탭 제목이 객체
    이름이라, 안 넣으면 탭이 전부 AnamorphicRigSettings_0 처럼 보인다.
    """
    tag = "".join(c if (c.isalnum() or c == "_") else "_" for c in preset).strip("_")
    obj = unreal.new_object(AnamorphicRigSettings.static_class(),
                            name=("AnamorphicRig_" + tag) if tag else "None")
    obj.set_editor_property("preset_name", preset)
    return obj


def preset_of(s):
    """이 설정이 어느 프리셋의 것인가. 비어 있으면 빈 문자열."""
    return s.get_editor_property("preset_name") or ""


def video_path_of(s):
    """설정의 영상 경로를 문자열로. 비어 있으면 빈 문자열."""
    fp = s.get_editor_property("video_path")
    return (fp.get_editor_property("file_path") or "") if fp is not None else ""


def _set_video_path(s, value):
    fp = unreal.FilePath()
    fp.set_editor_property("file_path", value or "")
    s.set_editor_property("video_path", fp)


VERSION = 2     # 1 -> 2: 패널의 세로 위치가 '눈높이 기준 중심' 에서 '바닥 기준 하단' 으로


def migrate(d):
    """옛 프리셋 dict 을 지금 형식으로. 자리에서 고치고 그대로 돌려준다.

    v1 은 패널 세로 위치를 center_z_m (눈높이 기준, 화면 중심) 로 적었다. 꺾인 벽의
    base_m (바닥 기준, 화면 하단) 과 기준이 달라서 도면 값을 그대로 넣을 수가 없었다.
    v2 는 둘을 맞춘다.
    """
    if d.get("version", 1) >= VERSION:
        return d
    eye = d.get("eye_height_m", 1.6)
    for pd in d.get("panels", []):
        if "panel_base_m" in pd:
            continue
        # 눈 기준 중심 -> 바닥 기준 하단
        pd["panel_base_m"] = pd.pop("center_z_m", 0.0) + eye - pd.get("height_m", 0.0) / 2.0
    d["version"] = VERSION
    return d


def to_dict(s):
    d = dict((k, s.get_editor_property(k)) for k in SCALARS if k != "video_path")
    d["version"] = VERSION
    d["video_path"] = video_path_of(s)
    d["panels"] = [dict((k, p.get_editor_property(k)) for k in PANEL_FIELDS) for p in s.panels]
    d["seams"] = [dict((k, q.get_editor_property(k)) for k in SEAM_FIELDS) for q in s.seams]
    d["projectors"] = [dict((k, r.get_editor_property(k)) for k in PROJ_FIELDS)
                       for r in s.projectors]
    return d


def apply_dict(s, d):
    """JSON 에서 읽은 값을 객체에 넣는다. 모르는 키는 무시하고, 빠진 키는 기본값을 둔다."""
    d = migrate(d)
    for k in SCALARS:
        if k not in d:
            continue
        if k == "video_path":
            _set_video_path(s, d[k])
        else:
            s.set_editor_property(k, d[k])
    panels = []
    for pd in d.get("panels", []):
        p = ARPanel()
        for k in PANEL_FIELDS:
            if k in pd:
                p.set_editor_property(k, pd[k])
        panels.append(p)
    seams = []
    for sd in d.get("seams", []):
        q = ARSeam()
        for k in SEAM_FIELDS:
            if k in sd:
                q.set_editor_property(k, sd[k])
        seams.append(q)
    projs = []
    for rd in d.get("projectors", []):
        r = ARProjector()
        for k in PROJ_FIELDS:
            if k in rd:
                r.set_editor_property(k, rd[k])
        projs.append(r)
    s.panels, s.seams, s.projectors = panels, seams, projs
    return s


# ---------------------------------------------------------------------------
def to_projectors(s):
    """설정 -> projector.Projector 목록. 비어 있으면 빈 목록."""
    from . import projector as PJ
    out = []
    for i, r in enumerate(s.projectors):
        out.append(PJ.Projector(
            r.name or "proj_%d" % i, r.span_start_m * M, r.span_end_m * M,
            back=max(0.1, r.back_m) * M,
            pos=((r.free_x_m * M, r.free_y_m * M) if r.place_free else None),
            dz=((r.height_m - s.eye_height_m) * M) if r.height_m else None,
            res=(max(1, r.res_x), max(1, r.res_y))))
    return out


def to_wall(s):
    """설정 -> geometry 객체. 계산은 전부 geometry.py 가 한다."""
    if s.bent_wall:
        return G.BentWall(
            face_b=s.face_b_m * M, face_a=s.face_a_m * M, height=s.wall_height_m * M,
            bend_deg=s.bend_deg, fillet_r=s.fillet_r_m * M, convex=s.convex,
            eye_dist=s.eye_dist_m * M, eye_offset_y=s.eye_offset_m * M,
            eye_height=s.eye_height_m * M, base=s.base_m * M)

    panels, free = [], {}
    for i, p in enumerate(s.panels):
        panels.append(G.Panel(
            p.name or "screen_%d" % i, p.width_m * M, p.height_m * M,
            None if p.auto_res else p.res_x, None if p.auto_res else p.res_y,
            # 안에서는 눈 기준 중심(dz)으로 쓴다. UI/JSON 은 바닥 기준 하단이다.
            dz=(p.panel_base_m + p.height_m / 2.0 - s.eye_height_m) * M))
        if p.detached:
            free[i] = (p.free_x_m * M, p.free_y_m * M, p.free_yaw)
    seams = [G.Seam(k.turn_deg, k.convex, k.gap_m * M) for k in s.seams]
    return G.PanelChain(panels, seams, eye_dist=s.eye_dist_m * M,
                        anchor_seam=None if s.anchor_seam < 0 else s.anchor_seam,
                        rotate_deg=s.rotate_deg, pitch_mm=s.pitch_mm, free=free)
