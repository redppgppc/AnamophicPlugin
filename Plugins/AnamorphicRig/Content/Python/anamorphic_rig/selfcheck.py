"""언리얼 없이 도는 자체 점검.

    python -m anamorphic_rig.selfcheck

geometry / config / projector / blend 은 언리얼에 의존하지 않아 각자 demo() 가 있다.
문제는 settings / menu / build 다. 이 셋은 `import unreal` 을 해서 평소에는 돌려 볼 수가
없는데, **import 단계에서 죽으면 플러그인이 통째로 안 뜬다.** 메뉴가 사라진 것 말고는
단서가 없고, 진짜 이유는 출력 로그 깊은 곳에 한 줄 남는다.

실제로 그렇게 죽은 적이 있다: uproperty 메타에 EditCondition 을 직접 주면서 **BENT 도
같이 풀어 써서 키워드가 겹쳤다. TypeError 는 클래스 본문이 실행되는 import 시점에 난다.

그래서 여기서는 unreal 을 흉내 낸 가짜 모듈을 sys.modules 에 끼워 넣고 import 만 해 본다.
동작을 검증하는 게 아니라 **"불러올 수는 있는가"** 를 본다. 그것만으로 위 부류는 다 잡힌다.
"""
import sys
import types


class _Any(object):
    """무엇을 하든 자기 자신을 돌려주는 자리표시자."""

    def __init__(self, *a, **k):
        pass

    def __call__(self, *a, **k):
        return self

    def __getattr__(self, name):
        return self

    def __iter__(self):
        return iter(())


def _fake_unreal():
    """settings / menu / build 가 import 시점에 건드리는 것만 채운 가짜 모듈."""
    u = types.ModuleType("unreal")

    def deco(*a, **k):
        return lambda cls: cls

    u.uclass = deco
    u.ustruct = deco
    u.ufunction = deco
    u.uproperty = lambda t, meta=None: None    # 키워드가 겹치면 _m() 에서 이미 터진다
    u.Object = type("Object", (object,), {})
    u.StructBase = type("StructBase", (object,), {})
    u.Array = lambda t: t
    u.__getattr__ = lambda name: _Any()        # 나머지는 전부 자리표시자
    return u


def main():
    from . import geometry, config, projector, blend
    for m in (geometry, config, projector, blend):
        m.demo()

    # 가짜 unreal 을 끼워 넣고 나머지를 불러 본다. 이미 진짜가 있으면 (에디터 안이면)
    # 건드리지 않는다.
    if "unreal" not in sys.modules:
        sys.modules["unreal"] = _fake_unreal()
    from . import settings
    from . import build as _build
    from . import menu as _menu

    # SCALARS 에 적힌 이름이 실제 프로퍼티로 선언돼 있는가. 하나라도 빠지면 그 값은
    # 저장도 복원도 조용히 안 된다.
    cls = settings.AnamorphicRigSettings
    missing = [k for k in settings.SCALARS if not hasattr(cls, k)]
    assert not missing, "SCALARS 에 있는데 프로퍼티 선언이 없다: %s" % missing

    assert hasattr(settings, "res_w_of"), "res_w_of 가 없다"
    assert callable(_build.build_level) and callable(_menu.register)
    print("selfcheck ok  (settings / build / menu import 포함)")


if __name__ == "__main__":
    main()
