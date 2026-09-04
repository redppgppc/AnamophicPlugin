"""환경 점검. 플러그인만 받아 온 프로젝트에서 뭐가 빠졌는지 알려 준다.

플러그인은 자기 Config/DefaultInput.ini 로 입력 설정을 물려주지만, 그 값은 단일 키라
호스트 프로젝트가 명시하면 프로젝트가 이긴다. ffmpeg 은 아예 같이 줄 수가 없다.
그래서 '무엇이 왜 빠졌는지' 를 실행 전에 말해 주는 쪽으로 간다.

여기서 잡는 것들은 전부 **조용히 실패한다.** 에러 없이 결과만 틀리므로,
안 알려 주면 받는 쪽이 원인을 못 찾는다.
"""
import os
import shutil

import unreal

# 다중 노드 입력 동기를 읽는 클래스. 이게 아니면 inputSyncPolicy 가 통째로 무시된다.
WANT_INPUT_CLASS = "DisplayClusterPlayerInput"
# DefaultPawn 이 움직이려면 최소한 이만큼은 있어야 한다.
WANT_AXES = ("MoveForward", "MoveRight")


def _input_settings():
    """InputSettings CDO. 이름이 바뀌면 조용히 틀리느니 None 을 준다."""
    try:
        return unreal.get_default_object(unreal.InputSettings)
    except Exception:
        return None


def check():
    """-> (줄 목록, 경고 목록). 경고가 비어 있으면 다 갖춰진 것이다."""
    lines, warns = ["[환경]"], []

    s = _input_settings()
    if s is None:
        lines.append("  입력 설정  확인 못 함 (InputSettings 를 못 읽음)")
    else:
        try:
            cls = str(s.get_editor_property("default_player_input_class"))
        except Exception:
            cls = ""
        ok = WANT_INPUT_CLASS in cls
        lines.append("  플레이어 입력 클래스  %s%s" % (cls or "확인 못 함", "" if ok else "  <- 다름"))
        if cls and not ok:
            warns.append(
                "DefaultPlayerInputClass 가 %s 가 아니다 (%s).\n"
                "    다중 노드에서 포커스 있는 창만 움직여 벽이 어긋난다.\n"
                "    프로젝트의 Config/DefaultInput.ini 가 플러그인 값을 덮고 있다.\n"
                "    그 줄을 지우거나 /Script/DisplayCluster.DisplayClusterPlayerInput 로 고칠 것"
                % (WANT_INPUT_CLASS, cls))

        try:
            names = set(a.get_editor_property("axis_name") for a in
                        s.get_editor_property("axis_mappings"))
        except Exception:
            names = None
        if names is None:
            lines.append("  축 매핑  확인 못 함")
        else:
            missing = [n for n in WANT_AXES if n not in names]
            lines.append("  축 매핑  %d개%s"
                         % (len(names), "" if not missing else "  <- %s 없음" % ", ".join(missing)))
            if missing:
                warns.append("축 매핑 %s 가 없다. 폰이 아예 안 움직인다" % ", ".join(missing))

    ffmpeg = shutil.which("ffmpeg")
    lines.append("  ffmpeg  %s" % (ffmpeg or "없음  <- PATH 에 넣을 것"))
    if not ffmpeg:
        warns.append("ffmpeg 이 PATH 에 없다. 영상 변환과 프로젝터 변환이 전부 실패한다")

    # 플러그인 클래스가 로드됐는지로 본다. uproject 를 읽는 것보다 확실하다.
    mrq = hasattr(unreal, "MoviePipelineQueue")
    lines.append("  MovieRenderPipeline  %s" % ("켜짐" if mrq else "꺼짐  <- 켤 것"))
    if not mrq:
        warns.append("MovieRenderPipeline 이 꺼져 있다. '무비 렌더 큐 점검' 과 렌더가 안 된다")

    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).rstrip("/")
    absent = [n for n in script_names() if not os.path.isfile(os.path.join(root, n))]
    lines.append("  배포 스크립트  %s" % ("있음" if not absent else "%s 없음" % ", ".join(absent)))
    if absent:
        warns.append("프로젝트 루트에 %s 가 없다. '배포 스크립트 설치' 를 누를 것"
                     % ", ".join(absent))

    return lines, warns


# --- 배포 스크립트 -----------------------------------------------------------
def scripts_dir():
    """플러그인이 들고 있는 스크립트 폴더. 이 파일 기준으로 거슬러 올라간다."""
    here = os.path.dirname(os.path.abspath(__file__))       # .../Content/Python/anamorphic_rig
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(here))),
                        "Resources", "Scripts")


def script_names():
    d = scripts_dir()
    if not os.path.isdir(d):
        return []
    return sorted(f for f in os.listdir(d) if not f.startswith("."))


def install_scripts(overwrite=False):
    """플러그인의 스크립트를 프로젝트 루트에 복사한다. -> (복사한 것, 건너뛴 것)

    루트에 있어야 하는 이유: Package.bat 이 %~dp0 로 .uproject 를 찾고,
    Run_Packaged.ps1 이 $PSScriptRoot 로 Package/ 와 nDisplay/ 를 찾는다.
    바이트 그대로 복사한다. .bat 은 CP949 + CRLF 라 다시 쓰면 깨진다.
    """
    src = scripts_dir()
    if not os.path.isdir(src):
        raise RuntimeError("플러그인에 스크립트 폴더가 없습니다: " + src)
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).rstrip("/")
    done, skipped = [], []
    for name in script_names():
        dst = os.path.join(root, name)
        if os.path.isfile(dst) and not overwrite:
            skipped.append(name)
            continue
        shutil.copyfile(os.path.join(src, name), dst)
        done.append(name)
    return done, skipped
