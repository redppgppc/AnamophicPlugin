"""레벨에 리그를 만든다. 언리얼 안에서만 동작한다.

만드는 것:
  - BentWall 이면 전개 길이로 UV 를 매긴 워프 메시 (Screen 은 항상 평면이라 필요하다)
  - DCRA (nDisplay 설정 에셋에서 스폰). 손으로 옮겨 둔 위치는 유지한다
  - 영상 플레이트 (워프 메시를 그대로 한 벌 더 써서 UV 가 자동으로 1:1 이 된다)
  - 영상 1:1 패스스루용 포스트프로세스 볼륨
"""
import os

import unreal

from . import config as CF
from . import geometry as G

LABEL = "AR_"       # 이 플러그인이 만든 액터의 라벨 접두사


def _actors():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def build_warp_mesh(wall, asset_dir, mesh_name, arc_seg, face_seg, seg_v,
                    flip_v=True, flip_winding=False):
    """전개 길이로 UV 를 매긴 워프 메시를 만든다. 리그 로컬 좌표 그대로 굽는다."""
    md = unreal.StaticMesh.create_static_mesh_description()
    pg = md.create_polygon_group()
    us = wall.column_us(arc_seg, face_seg)
    W, z0, H = wall.developed(), wall.base_z(), wall.height
    cols = []
    for u in us:
        x, y = wall.plan_point(u)
        col = []
        for j in range(seg_v + 1):
            f = j / float(seg_v)
            v = md.create_vertex()
            md.set_vertex_position(v, unreal.Vector(x, y, z0 + H * f))
            inst = md.create_vertex_instance(v)
            md.set_vertex_instance_uv(inst, unreal.Vector2D(u / W, (1.0 - f) if flip_v else f), 0)
            col.append(inst)
        cols.append(col)
    for i in range(len(us) - 1):
        for j in range(seg_v):
            a, b, c, d = cols[i][j], cols[i + 1][j], cols[i + 1][j + 1], cols[i][j + 1]
            if flip_winding:
                b, d = d, b
            md.create_triangle(pg, [a, b, c])
            md.create_triangle(pg, [a, c, d])

    # 기존 메시를 그대로 다시 빌드하면 렌더 리소스가 해제되지 않아 에디터가 죽는다.
    # (A FRenderResource was deleted without being released first!)
    # 에셋 삭제 경로는 리소스를 제대로 해제하므로 지우고 새로 만든다.
    path = "%s/%s" % (asset_dir, mesh_name)
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.SystemLibrary.collect_garbage()      # 파괴된 액터가 쥐고 있던 참조를 먼저 놓는다
        if not unreal.EditorAssetLibrary.delete_asset(path):
            raise RuntimeError(
                "워프 메시를 다시 만들지 못했습니다: %s\n"
                "다른 레벨이나 액터가 이 메시를 참조하고 있습니다. "
                "콘텐츠 브라우저에서 직접 지우고 다시 빌드하세요." % path)
    mesh = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        mesh_name, asset_dir, unreal.StaticMesh, None)
    if mesh is None:
        raise RuntimeError("워프 메시 에셋을 만들지 못했습니다: " + path)
    mesh.build_from_static_mesh_descriptions([md], False, True)
    # nDisplay 는 워프 지오메트리를 CPU 에서 읽는다. 에디터에서는 그냥 되지만 패키징하면
    # GPU 로만 올라가서 워프가 죽는다 (DisplayClusterRender_MeshComponent.cpp:69).
    mesh.set_editor_property("allow_cpu_access", True)
    # 벽은 충돌체가 아니다. 꺼야 GetPhysicsTriMeshData 경고가 사라진다.
    mesh.get_editor_property("body_setup").set_editor_property(
        "collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh)
    unreal.log("워프 메시: %s (%d 열)" % (path, len(us)))
    return mesh


def spawn_passthrough_volume(exposure_bias=0.0):
    """영상 1:1 출력. 자동노출과 ACES 톤커브를 꺼서 파일 색이 그대로 나가게 한다."""
    v = _actors().spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0))
    v.set_actor_label(LABEL + "passthrough")
    v.set_editor_property("unbound", True)
    v.set_editor_property("priority", 1000.0)
    s = v.get_editor_property("settings")
    for k, val in (("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL),
                   ("auto_exposure_apply_physical_camera_exposure", False),
                   ("auto_exposure_bias", float(exposure_bias)),
                   ("tone_curve_amount", 0.0), ("expand_gamut", 0.0), ("blue_correction", 0.0)):
        s.set_editor_property("override_" + k, True)
        s.set_editor_property(k, val)
    v.set_editor_property("settings", s)
    return v


def spawn_player_start(dcra):
    """스위트스팟에 PlayerStart 를 놓는다. 이미 남의 것이 있으면 건드리지 않는다.

    PIE 로는 nDisplay 뷰포트가 안 보인다 (클러스터 실행 전용). 씬을 둘러보는 용도다.
    """
    for a in _actors().get_all_level_actors():
        if isinstance(a, unreal.PlayerStart) and not a.get_actor_label().startswith(LABEL):
            unreal.log("PlayerStart 가 이미 있어 건너뜁니다: " + a.get_actor_label())
            return None
    act = _actors().spawn_actor_from_class(
        unreal.PlayerStart, dcra.get_actor_location(), dcra.get_actor_rotation())
    act.set_actor_label(LABEL + "start")
    return act


def spawn_floor(dcra, wall, eye_height_cm):
    """벽 아래에 격자 바닥을 깐다.

    리그 로컬 기준으로 바닥은 눈보다 eye_height 만큼 아래다. 크기는 벽과 시야를
    다 덮도록 평면도 범위에서 유도한다. 관람자 뒤쪽으로도 조금 깔아야 서 있는
    느낌이 난다.
    """
    W = wall.developed()
    pts = [wall.plan_point(i * W / 64.0) for i in range(65)] + [(0.0, 0.0)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    far, near = max(xs), min(0.0, min(xs))
    depth = (far - near) * 1.6
    width = max(max(ys) - min(ys), depth * 0.5) * 1.6
    cx, cy = (far + near) / 2.0, (max(ys) + min(ys)) / 2.0

    cube = unreal.load_object(None, "/Engine/BasicShapes/Cube.Cube")
    grid = unreal.load_object(None, "/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial")
    loc = dcra.get_actor_location() + unreal.Vector(cx, cy, -eye_height_cm - 10.0)
    act = _actors().spawn_actor_from_object(cube, loc, dcra.get_actor_rotation())
    act.set_actor_label(LABEL + "floor")
    act.set_actor_scale3d(unreal.Vector(depth / 100.0, width / 100.0, 0.2))
    act.static_mesh_component.set_material(0, grid)
    unreal.log("바닥: %.1f x %.1f m" % (depth / 100.0, width / 100.0))
    return act


def spawn_media_plate(mesh, dcra, video_abs):
    """워프 메시를 그대로 한 벌 더 놓는다. UV 가 같으므로 자동으로 1:1 이 된다.

    평면 플레이트를 쓰면 꺾인 벽에서 최대 6 m 어긋난다. 시선이 벽에 닿는 지점과
    플레이트에 닿는 지점이 다르기 때문. DCRA 와 같은 변환에 놓아야 한다
    (메시 정점이 리그 로컬 좌표이기 때문).
    """
    plate = _actors().spawn_actor_from_class(
        unreal.MediaPlate, dcra.get_actor_location(), dcra.get_actor_rotation())
    plate.set_actor_label(LABEL + "video")
    comp = plate.get_editor_property("media_plate_component")
    res = unreal.MediaPlateResource()
    res.set_editor_property("type", unreal.MediaPlateResourceType.EXTERNAL)
    res.set_editor_property("external_media_path", video_abs)
    comp.set_editor_property("media_plate_resource", res)
    # 켜져 있으면 영상 종횡비에 맞춰 메시 스케일을 덮어쓴다. 우리 메시는 이미 실측 cm 다.
    comp.set_is_aspect_ratio_auto(False)
    comp.set_editor_property("loop", True)
    # 메시는 생성자에서만 세팅되고 머티리얼은 컴포넌트 오버라이드(슬롯 0)라 그대로 남는다.
    smc = plate.get_editor_property("static_mesh_component")
    smc.set_static_mesh(mesh)
    smc.set_relative_scale3d(unreal.Vector(1.0, 1.0, 1.0))
    return plate


def apply_regions(dcra, wall, res_w, per_node=0):
    """DCRA 인스턴스의 뷰포트 Region 과 창 크기를 형상에 맞춘다.

    무비 렌더 큐는 .ndisplay 파일을 읽지 않고 이 값을 그대로 출력 해상도로 쓴다
    (DisplayClusterMovieGraphRenderCameraSource_Math.cpp 의
    GetCameraOverscannedResolution -> RenderTargetRect.Size()). 여기서 갱신해 두지
    않으면 해상도를 바꿔도 렌더 결과는 에셋을 임포트하던 시점의 크기로 계속 나온다.
    """
    cfg = dcra.get_editor_property("current_config_data")
    if cfg is None:
        raise RuntimeError("DCRA 에 current_config_data 가 없다. 에셋 임포트가 실패했는지 확인할 것")
    nodes = cfg.get_editor_property("cluster").get_editor_property("nodes")

    _, vps, ww, wh = CF.screens_and_viewports(wall, res_w)
    want_nodes = CF.make_nodes(vps, ww, wh, per_node)
    missing = [n for n in want_nodes if n not in nodes]
    extra = [n for n in nodes if n not in want_nodes]
    if missing or extra:
        raise RuntimeError(
            "DCRA 에셋의 노드가 설정과 다름.\n"
            "  에셋에 있는 것: %s\n  설정이 원하는 것: %s\n"
            "  없는 것: %s / 남는 것: %s\n"
            "해결: 콘텐츠 브라우저에서 nDisplay 에셋을 지우고 다시 빌드할 것"
            % (sorted(nodes), sorted(want_nodes), missing, extra))

    def rect(x, y, w, h):
        r = unreal.DisplayClusterConfigurationRectangle()
        for k, v in (("x", x), ("y", y), ("w", w), ("h", h)):
            r.set_editor_property(k, int(v))
        return r

    said = []
    for nname in CF.node_order(want_nodes):
        node, want = nodes[nname], want_nodes[nname]["viewports"]
        have = dict(node.get_editor_property("viewports"))
        miss, ext = [n for n in want if n not in have], [n for n in have if n not in want]
        if miss or ext:
            raise RuntimeError(
                "DCRA 에셋 %s 의 뷰포트가 설정과 다름.\n"
                "  에셋에 있는 것: %s\n  설정이 원하는 것: %s\n"
                "  없는 것: %s / 남는 것: %s\n"
                "해결: 콘텐츠 브라우저에서 nDisplay 에셋을 지우고 다시 빌드할 것. "
                "(nDisplay 임포트는 기존 에셋을 덮어쓰지 못한다)"
                % (nname, sorted(have), sorted(want), miss, ext))
        w = want_nodes[nname]["window"]
        node.set_editor_property("window_rect", rect(w["x"], w["y"], w["w"], w["h"]))
        for name, v in want.items():
            g = v["region"]
            have[name].set_editor_property("region", rect(g["x"], g["y"], g["w"], g["h"]))
        said.append("%s 창 %dx%d [%s]"
                    % (nname, w["w"], w["h"],
                       ", ".join("%s=%dx%d" % (n, v["region"]["w"], v["region"]["h"])
                                 for n, v in sorted(want.items()))))
    unreal.log("뷰포트 해상도 적용: " + " / ".join(said))


def asset_layout(asset, name):
    """에셋에 구워진 노드 -> 뷰포트 이름 목록. 못 읽으면 None.

    블루프린트 CDO 에서는 컴포넌트를 열거할 수 없어서 (항상 빈 목록이 나온다)
    설정 데이터로 판정한다. 뷰포트와 스크린은 1:1 이라 같은 얘기다.

    뷰포트 이름만 보면 안 된다. 노드를 쪼개도 이름은 그대로라, 멀티 노드로 바꾼 것을
    못 알아채고 재임포트를 건너뛴다. 그러면 apply_regions 가 노드가 없다고 죽는다.
    """
    cls = unreal.load_object(None, "%s.%s_C" % (asset, name))
    if cls is None:
        return None
    try:
        cfg = unreal.get_default_object(cls).get_editor_property("current_config_data")
        if cfg is None:
            return None
        got = {}
        for nname, node in cfg.get_editor_property("cluster").get_editor_property("nodes").items():
            got[str(nname)] = sorted(str(v) for v in node.get_editor_property("viewports").keys())
        return got
    except Exception:
        return None


def ensure_asset(asset, name, cfg_path, want):
    """설정에 맞는 nDisplay 에셋을 준비한다. 구성이 다르면 지우고 다시 임포트한다.

    want 는 {노드 이름: [뷰포트 이름]} 이다.

    nDisplay 임포트 팩토리는 기존 에셋을 덮어쓰지 못한다. 그래서 지우는 수밖에 없다.
    지우기 전에 이 에셋을 쓰는 액터는 이미 파괴돼 있어야 한다 (build_level 이 먼저 한다).
    """
    want = {str(k): sorted(v) for k, v in want.items()}

    def do_import():
        task = unreal.AssetImportTask()
        task.filename = cfg_path
        task.destination_path, task.destination_name = asset.rsplit("/", 1)[0], name
        task.automated = task.replace_existing = task.save = True
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    if not unreal.EditorAssetLibrary.does_asset_exist(asset):
        do_import()
        return

    have = asset_layout(asset, name)
    if have == want:
        return                      # 구성이 같으면 그대로 쓴다. 시퀀스 바인딩도 유지된다.

    unreal.log("[AnamorphicRig] 에셋 구성이 %s 라 설정(%s)과 다릅니다. 다시 만듭니다"
               % (have, want))
    # 참조가 남아 있으면 지우기가 실패한다. 실패하면 사람이 지울 수 있게 안내한다.
    if not unreal.EditorAssetLibrary.delete_asset(asset):
        raise RuntimeError(
            "nDisplay 에셋을 자동으로 다시 만들지 못했습니다.\n"
            "  에셋에 있는 것: %s\n  설정이 원하는 것: %s\n"
            "콘텐츠 브라우저에서 %s 를 직접 지우고 다시 빌드하세요.\n"
            "(다른 레벨이나 시퀀스가 이 에셋을 참조하고 있으면 지워지지 않습니다)"
            % (have, want, asset))
    do_import()
    if not unreal.EditorAssetLibrary.does_asset_exist(asset):
        raise RuntimeError("에셋을 지웠지만 다시 임포트하지 못했습니다: " + cfg_path)



def resolve_video(video, root):
    """영상 경로를 찾는다. 절대경로, 프로젝트 기준 상대경로, 파일명만 준 경우를 다 받는다."""
    tried = []
    for cand in (video,
                 os.path.join(root, video),
                 os.path.join(root, "Content", "Movies", video),
                 os.path.join(root, "Content", "Movies", os.path.basename(video))):
        if os.path.isfile(cand):
            return cand
        tried.append(cand)
    raise RuntimeError("영상 파일을 찾지 못했습니다: %s\n찾아본 곳:\n  %s"
                       % (video, "\n  ".join(tried)))


def build_level(wall, opts):
    """레벨을 통째로 다시 만든다. opts 는 dict (settings.py 가 채운다).

    필요한 키: asset_dir, asset_name, mesh_name, cfg_path, root, res_w,
               video, video_passthrough, exposure_bias, rig_origin,
               follow_player, exit_on_esc, per_node,
               arc_seg, face_seg, seg_v, flip_v, flip_winding
    """
    actors = _actors()

    # 액터를 에셋보다 먼저 파괴해야 임포트가 거부되지 않는다 ("이 파일이 이미 있습니다").
    # 손으로 옮겨 둔 DCRA 위치는 rig_origin 보다 우선한다.
    keep = None
    for a in actors.get_all_level_actors():
        if isinstance(a, unreal.DisplayClusterRootActor):
            keep = (a.get_actor_location(), a.get_actor_rotation())
            actors.destroy_actor(a)
        elif a.get_actor_label().startswith(LABEL):
            actors.destroy_actor(a)

    # 워프 메시는 두 군데에 쓴다. BentWall 은 Screen 이 항상 평면이라 반드시 필요하고,
    # 다중 패널은 Screen 은 패널마다 따로 두지만 영상 플레이트로 이 메시가 필요하다.
    mesh = None
    if isinstance(wall, G.BentWall) or opts.get("video"):
        mesh = build_warp_mesh(wall, opts["asset_dir"], opts["mesh_name"],
                               opts["arc_seg"], opts["face_seg"], opts["seg_v"],
                               opts["flip_v"], opts["flip_winding"])

    asset = "%s/%s" % (opts["asset_dir"], opts["asset_name"])
    per_node = opts.get("per_node", 0)
    cfg, ww, wh = CF.build(wall, "%s.%s" % (asset, opts["asset_name"]), opts["res_w"],
                           follow_player=opts.get("follow_player", False),
                           exit_on_esc=opts.get("exit_on_esc", True), per_node=per_node)
    CF.write(cfg, opts["cfg_path"])
    want = dict((n, list(v["viewports"]))
                for n, v in cfg["nDisplay"]["cluster"]["nodes"].items())
    ensure_asset(asset, opts["asset_name"], opts["cfg_path"], want)

    if opts.get("video_passthrough"):
        spawn_passthrough_volume(opts.get("exposure_bias", 0.0))

    cls = unreal.load_object(None, "%s.%s_C" % (asset, opts["asset_name"]))
    if keep:
        dcra = actors.spawn_actor_from_class(cls, keep[0], keep[1])
        unreal.log("DCRA 를 이전 위치 %s 에 다시 놓음 (기본 원점 무시)" % keep[0])
    else:
        dcra = actors.spawn_actor_from_class(cls, unreal.Vector(*opts["rig_origin"]))
    dcra.set_actor_label(opts["asset_name"])

    # DCRA 기본 뷰포인트가 z=50 이라 눈이 반 미터 뜬다. 원점으로 고정.
    for c in dcra.get_components_by_class(unreal.DisplayClusterCameraComponent):
        if c.get_name() == CF.EYE_NAME:
            c.set_relative_location(unreal.Vector(0, 0, 0), False, False)

    # 컴포넌트는 에셋 임포트 때 구워진다. 이름/개수를 바꿨으면 에셋을 새로 만들어야 한다.
    have = {c.get_name(): c
            for c in dcra.get_components_by_class(unreal.DisplayClusterScreenComponent)}
    want = cfg["nDisplay"]["scene"]["screens"]
    missing, extra = [n for n in want if n not in have], [n for n in have if n not in want]
    if missing or extra:
        # ensure_asset 이 앞에서 맞춰 놨어야 한다. 여기까지 왔다면 임포트가 조용히 실패한 것.
        raise RuntimeError(
            "에셋을 다시 만들었는데도 컴포넌트가 설정과 다릅니다.\n"
            "  에셋에 있는 것: %s\n  설정이 원하는 것: %s\n"
            "  없는 것: %s / 남는 것: %s\n"
            "%s 를 직접 지우고 다시 빌드해 보세요."
            % (sorted(have), sorted(want), missing, extra, asset))

    if isinstance(wall, G.BentWall):
        # 형상이 메시에 구워져 있으므로 컴포넌트는 항등 변환이어야 한다.
        c = have[CF.SCREEN_ONE]
        c.set_static_mesh(mesh)
        c.set_relative_location_and_rotation(unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0),
                                             False, False)
        c.set_relative_scale3d(unreal.Vector(1.0, 1.0, 1.0))
    else:
        for p in wall.panels:
            c = have[p.name]
            c.set_relative_location_and_rotation(
                unreal.Vector(p.center[0], p.center[1], p.dz),
                unreal.Rotator(roll=0.0, pitch=0.0, yaw=p.yaw), False, False)
            c.set_relative_scale3d(unreal.Vector(1.0, p.w, p.h))

    apply_regions(dcra, wall, opts["res_w"], per_node)

    if opts.get("show_floor"):
        spawn_floor(dcra, wall, opts["eye_height"])
    spawn_player_start(dcra)

    video = opts.get("video")
    if video:
        spawn_media_plate(mesh, dcra, resolve_video(video, opts["root"]))

    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        # 로그의 Error Code 32 = 다른 에디터가 이 레벨을 열고 있음.
        raise RuntimeError("레벨 저장 실패. 언리얼 에디터가 이 레벨을 열고 있는지 확인할 것")
    unreal.log("리그 준비됨: DCRA %s = 관람자의 눈 (%s)"
               % (dcra.get_actor_location(), "레벨 위치 유지" if keep else "기본 원점"))
    return dcra
