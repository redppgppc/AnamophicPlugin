"""임포트한 머티리얼의 usage flag 를 로그를 보고 고친다.

    에디터 Output Log 의 Cmd 를 Python 으로 바꾸고 한 줄:

        exec(open(r"D:\\Temp\\Moniter_2\\Fix_MaterialUsage.py", encoding="utf-8").read())

왜 필요한가: 머티리얼에 bUsedWithMorphTargets 같은 플래그가 없으면 그 메시에 쓸 수 없어
언리얼 기본 회색 머티리얼로 대체된다. 에디터는 로드하면서 플래그를 자동으로 켜 주지만
(Material.cpp:1893), 게임 빌드는 안 켜 준다. 그래서 툴에서는 멀쩡하고 클러스터에서만
회색으로 나온다.

에디터가 켜 준 값이 저장되면 끝나는데, 로드 중에는 MarkPackageDirty() 가 실패해서
콘텐츠 브라우저에 저장 표시가 안 붙는다 (Material.cpp:1918). '모두 저장' 이 건너뛰는 이유다.
여기서는 값을 직접 다시 넣어 확실히 dirty 로 만든 뒤 저장한다.

Fab / Sketchfab glTF 를 임포트할 때마다 반복되는 문제라 로그에서 대상을 찾게 해 뒀다.
"""
import os
import re

import unreal

# 로그 한 줄: Material /Game/... missing usage flag MorphTargets!
LINE = re.compile(r"Material (/[^\s]+) missing usage flag (\w+)")


def newest_log():
    d = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()) + "Logs"
    logs = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".log")]
    if not logs:
        raise RuntimeError("로그가 없습니다: " + d)
    return max(logs, key=os.path.getmtime)


def prop_name(usage):
    """'MorphTargets' -> 'used_with_morph_targets'"""
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", usage).lower()
    return "used_with_" + snake


def fix(log_path=None):
    log_path = log_path or newest_log()
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        found = set(LINE.findall(f.read()))
    if not found:
        unreal.log("고칠 것이 없습니다. %s 에 usage flag 경고가 없습니다"
                   % os.path.basename(log_path))
        return 0

    # 플래그는 인스턴스가 아니라 부모 UMaterial 에만 있다 (MaterialInstance.cpp:1772 도
    # 부모를 본다). 인스턴스 여러 개가 부모 하나를 공유하므로 부모 기준으로 모은다.
    targets = {}
    for path, usage in sorted(found):
        # 로그의 /Game/A/B.B 형태에서 에셋 경로만 남긴다
        asset = path.split(".")[0]
        m = unreal.load_asset(asset)
        if m is None:
            unreal.log_warning("못 찾음: " + asset)
            continue
        base = m.get_base_material()
        if base is None:
            unreal.log_warning("베이스 머티리얼이 없음: " + asset)
            continue
        targets.setdefault(base.get_path_name(), (base, set()))[1].add(prop_name(usage))

    done = 0
    for key, (base, props) in sorted(targets.items()):
        if key.startswith("/Engine/"):
            unreal.log_error("엔진 머티리얼이라 저장할 수 없습니다: " + key)
            continue
        try:
            for prop in sorted(props):
                base.set_editor_property(prop, True)
        except Exception as e:
            unreal.log_error("%s 에 %s 를 못 넣었습니다: %s" % (key, sorted(props), e))
            continue
        unreal.MaterialEditingLibrary.recompile_material(base)
        if unreal.EditorAssetLibrary.save_loaded_asset(base):
            unreal.log("고침: %s (%s)" % (key, ", ".join(sorted(props))))
            done += 1
        else:
            unreal.log_error("저장 실패: " + key)

    unreal.log("%d개 고쳤습니다. 클러스터를 다시 띄우고 로그에 "
               "'missing usage flag' 가 없으면 끝입니다" % done)
    return done


fix()
