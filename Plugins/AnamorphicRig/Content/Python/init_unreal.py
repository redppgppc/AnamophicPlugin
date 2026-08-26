"""플러그인 진입점. 언리얼이 시작할 때 자동으로 실행한다."""
import unreal

try:
    import anamorphic_rig.menu as menu
    menu.register()
except Exception as e:                  # 여기서 터지면 에디터 시작이 시끄러워진다
    unreal.log_error("[AnamorphicRig] 메뉴 등록 실패: %s" % e)
