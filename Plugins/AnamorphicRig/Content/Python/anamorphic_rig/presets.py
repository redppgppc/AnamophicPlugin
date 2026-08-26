"""설정을 JSON 프리셋 파일로 저장한다.

왜 DataAsset 이 아닌가: 파이썬으로 정의한 UClass 는 엔진이 transient 로 취급해서
그 클래스의 에셋은 저장이 불가능하다.

    Can't save ...: Object is an export but is an instance of class
    (.../settings_PY.AnamorphicRigSettings) which is unsaveable: It is transient.

그래서 값은 JSON 파일에 넣고, 디테일 패널은 임시 객체에 띄운다. 파일이라 diff 가 되고
git 에 올라가며 에디터 없이도 읽을 수 있다. 현장 하나가 파일 하나다.
"""
import json, os

DIRNAME = "AnamorphicRig"
EXT = ".json"


def _root():
    import unreal
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_config_dir()).rstrip("/")


def folder():
    d = os.path.join(_root(), DIRNAME)
    os.makedirs(d, exist_ok=True)
    return d


def path_of(name):
    return os.path.join(folder(), name + EXT)


def names():
    d = folder()
    return sorted(f[:-len(EXT)] for f in os.listdir(d) if f.endswith(EXT))


def exists(name):
    return os.path.isfile(path_of(name))


def load(name):
    with open(path_of(name), "r", encoding="utf-8") as f:
        return json.load(f)


def save(name, data):
    p = path_of(name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return p


def active_file():
    return os.path.join(folder(), "_active.txt")


def active():
    """마지막으로 쓴 프리셋 이름. 없으면 'default'."""
    try:
        with open(active_file(), "r", encoding="utf-8") as f:
            n = f.read().strip()
        if n and exists(n):
            return n
    except IOError:
        pass
    got = names()
    return got[0] if got else "default"


def set_active(name):
    with open(active_file(), "w", encoding="utf-8") as f:
        f.write(name)
    return name
