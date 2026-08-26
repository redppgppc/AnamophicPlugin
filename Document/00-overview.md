# Moniter_2 — nDisplay 리그 프로젝트 개요

Unreal Engine 5.8 + nDisplay 로 **오프액시스(anamorphic) 스크린 리그**를 구성하는 프로젝트.
모든 리그 형상은 `Scripts/*.py` 의 상수 몇 개로 정의되고, 거기서 nDisplay 설정(JSON)과
실행 배치 파일이 생성된다. 손으로 편집하는 것은 파이썬 상수뿐이다.

- 엔진: `D:\Epic Games\UE_5.8`
- 프로젝트: `D:\Temp\Moniter_2\Moniter_2.uproject`
- 최종 갱신: 2026-08-24

---

## 0. 용어 (먼저 읽을 것)

"라운드"라는 말이 두 가지로 쓰여서 한 번 크게 헷갈렸다. 코드에서는 이 단어를 쓰지 않는다.

| 용어 | 뜻 | 어디에 |
|---|---|---|
| **필렛 (fillet)** | 벽이 평면도에서 꺾이는 부분의 곡률 | `curved.py` 의 `FILLET_R_CM` |
| ~~외곽 마스크~~ | ~~화면 네 모서리를 둥글게 깎기~~ | **제거됨** (아래 참고) |

원래 요구사항은 **"77×21m 벽이 가운데에서 90도로 꺾이는데, 꺾이는 부분이 라운드지면서
꺾인다"** 였다. 즉 필렛이다. 그런데 초기 구현(`round.py`)이 이걸 화면 외곽선 모서리를
깎는 것으로 잘못 읽었다. 코드에 흔적이 남아 있었다.

```python
# 구 round.py
CORNER_RADIUS_CM = 300.0    # ponytail: guessed, drawing does not say
```

도면에 없는 게 당연했다. 도면에 있던 건 꺾임부 반지름이었으니까. 이 오해로 리그가 3개
(`Round` / `RoundVideo` / `Square`) 생겼는데 셋의 차이는 요청한 적 없는 마스크의 on/off
조합뿐이었다. 2026-08-24 에 전부 정리하고 **평면 벽 1개 + 꺾인 벽 1개**로 합쳤다.

구 파일은 지우지 않고 `_deprecated/` 로 옮겨 뒀다.

---

## 1. 구성 (3가지 리그)

| 리그 | 스크립트 | nDisplay 설정 | 레벨 재빌드 | 실행 | 맵 |
|---|---|---|---|---|---|
| 아나모픽 2모니터 코너 | `Scripts/anamorphic.py` | `nDisplay/Anamorphic_2Mon.ndisplay` | `Rebuild_Level.bat` | `Run_Anamorphic.bat` | `Maps/Main` |
| 평면 77×21m 벽 | `Scripts/flat.py` | `nDisplay/FlatWall.ndisplay` | `Rebuild_FlatWall.bat` | `Run_FlatWall.bat` | `Maps/FlatWall` |
| 꺾인 벽 (90도 + 필렛) | `Scripts/curved.py` | `nDisplay/Curved_1Screen.ndisplay` | `Rebuild_Curved.bat` | `Run_Curved.bat` | `Maps/Curved` |
| 영상 77:21 변환 (ffmpeg) | `Scripts/convert_video.py` | - | - | - | - |

세 리그 모두 독립 스크립트다. 서로 import 하지 않는다.

---

## 2. 두 가지 갱신 경로 (중요)

값을 바꿨을 때 무엇을 다시 돌려야 하는지가 이 프로젝트의 핵심 규칙이다.

### 경로 A — 설정만 바뀌는 값 (python 실행 → 바로 실행)

```
python Scripts\flat.py        (또는 anamorphic.py / curved.py)
  -> .ndisplay 재작성
  -> Run_*.bat 재작성
Run_FlatWall.bat              실행
```

런타임이 설정 파일에서 스크린의 **위치와 회전**을 다시 읽으므로 레벨 재빌드가 필요 없다.
설정의 `misc` 에 다음 두 플래그가 켜져 있어야 이 동작이 보장된다.

- `bOverrideViewportsFromExternalConfig: true`
- `bOverrideTransformsFromExternalConfig: true`

플래그가 없으면 런타임은 블루프린트에 마지막으로 임포트된 형상을 조용히 사용하고
파일 내용을 무시한다.

### 경로 B — 레벨 재빌드까지 필요한 값

```
python Scripts\flat.py        (먼저 설정 갱신)
Rebuild_FlatWall.bat          (헤드리스 에디터로 레벨에 액터 재배치 + 저장)
Run_FlatWall.bat
```

레벨에 실제로 배치되는 것에 영향을 주는 값이 여기 해당한다.

- 스크린 메시 **크기** (`MON_W_CM` / `MON_H_CM`, `SCREEN_W_CM` / `SCREEN_H_CM`)
  설정의 `size` 는 임포트 시점에만 반영되고, 위 오버라이드는 위치/회전만 갱신한다.
- 리그 원점 `RIG_ORIGIN`
- 데모 콘텐츠 (`DEMO`, `DEMO_ALCOVE`)
- 비디오 플레이트 (`VIDEO`, `PLATE_YAW`)

`curved.py` 는 형상이 워프 메시 정점에 구워지므로, 스크립트 [2] 구역의 값을 하나라도
바꾸면 **항상 경로 B** 다. 눈 위치/창 크기만 바꾸는 [1] 구역만 경로 A 로 끝난다.

주의: `Rebuild_*.bat` 은 `build_level()` 만 호출하고 `.ndisplay` 를 다시 쓰지 않는다.
설정을 바꿨다면 **반드시 python 을 먼저 돌린 뒤** 재빌드해야 한다.

---

## 3. 파라미터

### 3.1 anamorphic.py — 2모니터 코너 리그

세계 원점 = 관찰자의 눈. +X 코너 방향, +Y 오른쪽, +Z 위. 단위 cm.

| 값 | 현재 | 의미 |
|---|---|---|
| `BEZEL_CM` | 0.8 | 물리적 코너 모서리에서 액티브 영역까지의 베젤 |
| `CORNER_DEG` | -90.0 | 두 패널 사이 내각. **음수 = 볼록(convex)**, 코너 모서리가 관찰자 쪽으로 튀어나옴 |
| `EYE_DIST_CM` | 60.0 | 눈에서 코너 모서리까지 수평 거리 (오목 90도는 약 51 초과 필요) |
| `SCREEN_DZ_CM` | -4.6 | 눈높이 대비 스크린 수직 중심 (+ 가 위) |
| `MON_W_CM` / `MON_H_CM` | 70.8 / 39.8 | 액티브 영역 실측 크기 (32" 16:9) |
| `RES_W, RES_H` | 2560, 1440 | 모니터 1대 해상도 (창은 5120×1440) |
| `SWAP_OUTPUTS` | False | 왼쪽 패널이 데스크톱 오른쪽 절반이면 True |
| `FOLLOW_PLAYER` | False | True 면 리그가 플레이어 카메라를 따라감 (콘텐츠 프리뷰용) |
| `RIG_ORIGIN` | (0, 0, 1000) | 레벨에 DCRA 가 아직 없을 때의 눈 위치 |
| `DEMO_ALCOVE` | False | 데모 벽/큐브 (오목 코너에서만 의미 있음) |
| `HIDE_SCREEN_MESSAGES` | True | 엔진 온스크린 메시지 끄기 (6장 참고). 개발 중엔 False 가 안전 |

수치는 스펙 시트가 아니라 **실측값**을 넣는다.

### 3.2 flat.py — 평면 77×21m 벽

| 값 | 현재 | 의미 |
|---|---|---|
| `SCREEN_W_CM` / `SCREEN_H_CM` | 7700 / 2100 | 벽 크기 (도면 77000×21000 mm) |
| `EYE_DIST_CM` | 3500 | 스위트스팟, 눈에서 벽까지 |
| `EYE_HEIGHT_CM` | 160 | 바닥에서 눈높이. 벽 하단은 바닥에 붙는다 |
| `RES_W` | 2560 | 테스트 창 폭. 높이는 77:21 비율로 자동 계산 (698) |
| `VIDEO` | `MediaExample_wall.mp4` | 벽에 붙일 영상. `""` = 없음 |
| `PLATE_YAW` | 0.0 | 벽이 검게 나오면 180 으로 (플레이트 메시는 단면) |
| `DEMO` / `DEMO_DEPTH_CM` | False / 6000 | 시차 확인용 큐브와 뒷벽 |
| `HIDE_SCREEN_MESSAGES` | True | 엔진 온스크린 메시지 끄기 (6장 참고). 개발 중엔 False 가 안전 |

수평 화각 95.45도. 평면 한 장이므로 nDisplay Screen 컴포넌트로 정확히 표현된다.

### 3.3 curved.py — 꺾인 코너 벽

#### 벽 높이 / 스위트스팟 위치

| knob | 뜻 |
|---|---|
| `EYE_HEIGHT_CM` | 바닥에서 눈높이 |
| `SCREEN_BASE_CM` | 바닥에서 **벽 하단**까지. 건물 외벽에 매달린 벽이면 500 (5 m) 등. 0 = 바닥에 붙음 |
| `EYE_DIST_CM` | 눈 -> 호 정점, **대칭축 방향** 거리 (직선거리가 아님) |
| `EYE_OFFSET_Y_CM` | 스위트스팟이 좌우 대칭축에서 벗어난 거리. + = 오른쪽(면 A), - = 왼쪽(면 B) |

셋 다 워프 메시에 구워지므로 **경로 B** (python -> `Rebuild_Curved.bat`). `base_z()` 가
`SCREEN_BASE_CM - EYE_HEIGHT_CM` 을 돌려주고, 메시 정점과 `convert_video.py` 가 이걸 쓴다.

#### 스위트스팟이 축에서 벗어날 때 (EYE_OFFSET_Y_CM)

관람 공간 제약으로 정면 대칭축에 설 수 없는 경우. 벽은 물리적으로 고정이므로
**눈만 옆으로 옮긴다.** `plan_point()` 가 모든 y 를 반대로 밀어서 처리한다.
워프 메시, nDisplay 프러스텀, `convert_video.py` 의 가상 평면 전부 자동으로 따라간다.

공짜는 아니다. 실측 (`DEVELOPED_W_CM=7700`, `R=250`, `EYE_DIST_CM=3500`, 좌측 이동):

| 오프셋 | 면B / 호 / 면A (deg) | 먼 끝 입사각 | 가까운 끝 | 성김 | 가상 래스터 |
|---|---|---|---|---|---|
| 0 | 21.3 / 5.7 / 21.3 | 20.9 | 20.9 | 2.5x | 7052x5048 |
| -500 | 25.3 / 5.6 / 17.2 | 17.1 | 24.8 | 3.0x | 8268x5918 |
| -1000 | 28.9 / 5.3 / 13.2 | 13.6 | 29.0 | 3.7x | 9994x7154 |
| -1500 | 31.9 / 4.8 / 9.5 | 10.3 | 33.4 | 4.7x | 12630x9042 |
| -2000 | 34.1 / 4.3 / 6.4 | 7.3 | 38.0 | 6.3x | 12630x9042 |
| -2500 | 35.5 / 3.8 / 3.7 | 4.5 | 42.6 | 9.6x | 26718x19128 |
| -3000 | 36.1 / 3.3 / 1.5 | 1.9 | 47.2 | 21.3x | 26718x19128 |
| -3500 | **실패** (`가로 매핑이 단조가 아님`) | | | | |

읽는 법:

- **먼 끝 입사각**이 실질 한계다. 20도 아래면 그 끝은 거의 스치듯 보이고, LED 픽셀이
  가로로 뭉갠다. -1000 (10 m) 정도까지가 실용 범위.
- **성김**은 양 끝 화소가 정점 대비 몇 배로 늘어나는지다. 같은 배 만큼 해상도가 깎인다.
- **가상 래스터**는 `--curved` 변환의 중간 버퍼다. -2500 부터 2.7 억 픽셀이라 변환이
  느려지고 메모리를 많이 먹는다.
- **-3500 에서는 자체 점검이 막는다.** 눈이 면 A 의 평면을 넘어가서 그 면이 접혀 보인다.
  물리적으로 표현 불가능한 배치이고, 이건 버그가 아니라 정상적인 거부다.

레벨에서는 DCRA 가 스위트스팟에 그대로 있고 **벽이 반대로 이동한다.** 손으로 놓아 둔
DCRA 가 있다면 재빌드 후 실제 관람 위치와 맞는지 다시 확인할 것.


| 값 | 현재 | 의미 |
|---|---|---|
| `DEVELOPED_W_CM` | 7700 | **전개 총길이** (면B + 호 + 면A). 펼쳤을 때의 LED 총폭 |
| `SCREEN_H_CM` | 2100 | 벽 높이 |
| `BEND_DEG` | 90 | 평면도에서 두 면이 이루는 꺾임 각 |
| `FILLET_R_CM` | 250 | 필렛 반지름 (지름 5 m) |
| `CONVEX` | True | True: 코너가 관람자 쪽으로 볼록. False: 관람자가 코너 안쪽에 섬 |
| `EYE_DIST_CM` | 3500 | 눈에서 **호 정점**(가장 튀어나온 지점)까지 |
| `EYE_HEIGHT_CM` | 160 | 바닥에서 눈높이 |
| `ARC_SEG/FACE_SEG/SEG_V` | 24/8/4 | 워프 메시 분할. 호에만 몰아준다 |
| `BUFFER_RATIO` | 1.0 | 내부 렌더 타깃 배율. 면 바깥쪽이 뿌옇게 보이면 1.3 |
| `FLIP_V` / `FLIP_WINDING` | True / False | **실행 검증 완료된 값.** 그대로 두면 된다 |
| `VIDEO` | `MediaExample_wall.mp4` | 벽에 붙일 영상. `""` = 없음 |
| `DEMO` / `DEMO_DEPTH_CM` | False / 6000 | VIDEO 와 같이 켜지 말 것 (4.3 참고) |
| `HIDE_SCREEN_MESSAGES` | True | 엔진 온스크린 메시지 끄기 (6장 참고). 개발 중엔 False 가 안전 |

현재 값으로 나오는 형상 (`python Scripts\curved.py` 출력):

```
전개 7700 cm = 면 3653.7 + 호 392.7 + 면 3653.7   (R=250, 90 deg, 볼록)
호 정점 (3500.0, 0), 접점 (3573.2, +-176.8), 양 끝 (6156.7, +-2760.3)
수평 화각 48.30 deg (호 5.66 + 면 21.32 x2)
입사각: 정점 90.0 deg -> 접점 42.2 deg -> 양 끝 20.9 deg
화소 밀도: 호 69 cm/deg, 면 171 cm/deg (양 끝이 2.5 배 성김)
```

읽는 법:

- **입사각**이 양 끝에서 20.9도까지 떨어진다. 스위트스팟에서 면 바깥쪽을 거의 스치듯 본다는
  뜻이다. 이 구간은 어떤 보정으로도 화질이 좋아지지 않는다. 물리적 한계다.
- **화소 밀도**가 양 끝에서 2.5배 성기다. 즉 LED 화소 1개가 렌더 화소 0.4개분만 받는다.
  뿌옇게 보이면 `BUFFER_RATIO` 를 올린다.
- `CONVEX = False`(오목)로 뒤집으면 수평 화각이 **146도**로 폭증한다. 단일 뷰포트의
  원근 렌더 타깃으로는 감당이 안 되므로, 오목으로 갈 거면 면/호를 뷰포트 3개로 쪼개야 한다.

---

## 4. 꺾인 벽은 왜 별도 리그인가

nDisplay 의 Screen 컴포넌트는 **언제나 평면 직사각형**이다. 그래서 평면 벽(`flat.py`)은
Screen 컴포넌트 하나로 끝나지만, 꺾인 벽은 표현할 방법이 없다.

`curved.py` 는 형상을 **정적 메시로 구워서** mesh 프로젝션 폴리시가 그 메시를 가리키게 한다.

### 4.1 UV 가 핵심

**메시의 UV 가 곧 출력 영상이다.** u 축을 **전개 길이**(호를 편 길이)로 매개변수화해야 한다.
LED 화소는 패널 표면을 따라 균일하게 박혀 있지 투영된 X 를 따라 박혀 있지 않기 때문이다.
u 를 투영 X 로 잡으면 호 구간에서 화소가 뭉친다.

`curved.py` 는 열 위치를 호에만 몰아서 분할하지만(`ARC_SEG=24, FACE_SEG=8`) UV 는 각 정점의
전개 좌표 u 로 직접 계산하므로, 분할이 불균일해도 등호길이 매개변수화는 그대로 유지된다.
자체 점검의 "3D 표면 길이 == 전개 길이" assert 가 이걸 잠근다.

### 4.2 메시를 어디에 실을 것인가

새 컴포넌트를 만들지 않고 **기존 Screen 컴포넌트(`screen_0`)를 그대로 쓴다**.
`UDisplayClusterScreenComponent` 가 `UStaticMeshComponent` 를 상속하므로 mesh 폴리시가
이름으로 찾아낸다. 블루프린트에 컴포넌트를 새로 추가하는 것보다 코드가 훨씬 짧다.
대신 두 가지를 지켜야 한다.

- 설정의 `screens.screen_0` 은 위치/회전 0, `size` 1x1 (형상이 이미 메시에 들어 있음)
- `build_level()` 이 인스턴스의 스케일을 (1,1,1) 로 되돌림

런타임에 `bOverrideTransformsFromExternalConfig` 는 위치/회전만 건드리므로
(`UpdateComponentTransformsOnly`) 메시와 스케일은 안전하다.

**`bAllowCPUAccess` 를 켜야 한다.** nDisplay 는 워프 지오메트리를 CPU 에서 읽는다
(`DisplayClusterRender_MeshComponent.cpp:69`). 에디터에서는 그냥 되지만 패키징하면
지오메트리가 GPU 로만 올라가서 워프가 죽는다. `build_mesh_asset()` 이 이 플래그와
충돌 트레이스 플래그를 함께 세팅한다.

### 4.3 영상 플레이트도 곡면이어야 한다

`flat.py` 는 평면 MediaPlate 를 스크린 평면에 정확히 겹쳐 놓는다. 벽이 평면이라
시선이 벽에 닿는 지점과 플레이트에 닿는 지점이 같으므로 1:1 이 성립한다.

꺾인 벽에 평면 플레이트를 쓰면 성립하지 않는다. 실측:

| 전개 위치 | 벽에 있어야 할 위치 | 평면 플레이트가 보내는 위치 | 오차 |
|---|---|---|---|
| 0.50 W | 0.500 W | 0.500 W | 0 cm |
| 0.60 W | 0.600 W | 0.663 W | +487 cm |
| 0.70 W | 0.700 W | 0.778 W | +599 cm |
| 0.80 W | 0.800 W | 0.868 W | +522 cm |
| 1.00 W | 1.000 W | 1.000 W | 0 cm |

양 끝과 정중앙만 우연히 맞고 중간은 최대 6 m 어긋난다.

그래서 `curved.py` 는 **워프 메시(`SM_WallCurved`)를 한 벌 더 씬에 놓고** 거기에 미디어를
입힌다. UV 가 같은 메시이므로 자동으로 1:1 이다. `MediaPlate` 액터를 띄운 뒤 그 액터의
정적 메시만 갈아끼우는 방식이다. 엔진 소스 기준으로 안전한 이유는 두 가지다.

- `AMediaPlate` 는 정적 메시를 **생성자에서만** 설정한다. 인스턴스에서 바꿔도 되돌리지 않는다
- 미디어 머티리얼은 `StaticMeshComponent->SetMaterial(0, ...)` 즉 **컴포넌트 오버라이드**라,
  메시를 바꿔도 슬롯 0 이 있으면 그대로 남는다 (생성 메시는 머티리얼 슬롯 1개)

두 가지를 지켜야 한다.

- `set_is_aspect_ratio_auto(False)`. 켜져 있으면 영상 종횡비에 맞춰 메시 스케일을 덮어쓴다
- 플레이트를 **DCRA 와 같은 변환**에 놓아야 한다. 메시 정점이 리그 로컬 좌표이기 때문에
  `RIG_ORIGIN` 에 고정하면 DCRA 를 손으로 옮겼을 때 어긋난다

**DEMO 와 VIDEO 를 같이 켜지 말 것.** DEMO 큐브 중 일부는 벽보다 **앞**에 있다.
예를 들어 `CRV_cue0` 은 눈에서 4934 cm, 같은 방향의 벽면은 5236 cm 라서 큐브가 영상을
뚫고 튀어나온다. 아나모픽 동작상 정상이지만 영상 확인에는 방해가 된다.

### 4.4 실행 검증 결과 (2026-08-24)

`Rebuild_Curved.bat` + `Run_Curved.bat` 실전 실행으로 확인한 것들.

| 항목 | 결과 |
|---|---|
| 워프 메시 생성 | `warp mesh built: /Game/Curved/SM_WallCurved (41 columns)` |
| mesh 프로젝션 폴리시 | `Handling StartScene()` 성공. warpblend 실패 메시지 없음 |
| 영상 재생 | `LogElectraPlayer: Playback started` + 루프 정상 |
| `FLIP_V = True` | **맞음.** 영상이 똑바로 나온다 |
| `FLIP_WINDING = False` | **맞음.** 벽이 검게 나오지 않는다 |
| u 방향 | **맞음.** 로고가 좌우 반전되지 않는다 |
| 전개 매핑 | 테스트 패턴의 컬러 바가 등간격 수직선으로 나온다. 출력 = 입력 영상 그대로 |

즉 `메시 UV -> 출력` 과 `플레이트 UV -> 메시` 왕복이 항등이다. 이게 이 설계의 핵심 주장이었고
테스트 패턴으로 실측 확인됐다.

`flat.py` 도 같은 방식으로 실행 검증했다 (영상 재생, 모서리 직각, 전체 사각형).

---

## 5. 영상 변환 (convert_video.py)

```
python Scripts\convert_video.py in.mp4             -> Content\Movies\in_wall.mp4
python Scripts\convert_video.py in.mp4 --curved    -> Content\Movies\in_curved.mp4
python Scripts\convert_video.py 전개본.mp4 --preview  -> Content\Movies\전개본_eye.mp4
python Scripts\convert_video.py                    -> 자체 점검만
```

**산출물 두 가지는 서로 대체할 수 없다.**

| | `_wall.mp4` | `_curved.mp4` |
|---|---|---|
| 무엇 | 전개 77:21 에 맞추기만 | 아나모픽 사전 왜곡 |
| 벽에서 | 벽지처럼 붙음. 코너에서 그림이 꺾임 | 스위트스팟에서 평면처럼 보임 (코엑스 파도) |
| 맞는 곳 | 관람 위치가 정해지지 않은 일반 벽 | `curved.py` 꺾인 벽, 지정된 관람 위치 |
| 소재 비율 | 77:21 (3.667:1) | **1.494:1** |

**출력은 원본이 어디 있든 항상 `Content\Movies\` 로 간다.** `VIDEO` 노브가 프로젝트 기준
상대경로를 요구하기 때문이다. 변환이 끝나면 그대로 붙여 넣을 줄까지 찍어 준다.

```
> python Scripts\convert_video.py "D:\받은자료\clip.mp4"
wrote D:\Temp\Moniter_2\Content\Movies\clip_wall.mp4
VIDEO = "Content/Movies/clip_wall.mp4"
```

- 출력 3840×1046 (77:21, yuv420 을 위해 짝수 높이), libx264 crf 18, 오디오 복사
- 원본은 목표 비율을 채우도록 확대 후 중앙 크롭 (레터박스 없음)
- 원본 파일은 건드리지 않는다
- 서로 다른 폴더의 같은 이름 원본은 결과물이 덮어써진다. 막지는 않고
  `overwriting ...` 을 찍어 알린다 (원본에서 언제든 다시 만들 수 있는 파생물이므로)
- 필요: `ffmpeg` (PATH)

**두 리그가 같은 파일을 쓴다.** 꺾여도 전개하면 같은 77:21 직사각형이고, LED 프로세서에
들어가는 것은 어차피 전개 이미지이기 때문이다. `convert_video.py` 의 자체 점검이
`flat.py` 와 `curved.py` 의 전개 크기가 일치하는지 assert 로 확인한다.

구 `--rounded` 옵션은 제거했다. 그것은 삭제된 외곽 마스크와 짝이었다. 따라서
`Content/Movies/` 의 `*_wall_round.mp4` 와 `*_mask.png` (ffmpeg 오버레이용 중간 산출물)
도 이제 쓸 데가 없다. 지워도 된다.

> 실측 확인: `TestPattern_wall.mp4` 는 네 모서리가 각진 채로 화면을 꽉 채우고,
> `TestPattern_wall_round.mp4` 는 네 모서리에 검은 라운드가 그대로 남는다.
> `MediaExample` 계열로는 구분이 안 된다. 영상 배경이 거의 검정이라 검은 마스크가 묻힌다.

### --curved 아나모픽 사전 왜곡

꺾인 벽에 평평한 영상을 그냥 붙이면 코너에서 그림이 꺾여 보인다. 스위트스팟에 선 관람자
눈에 평면으로 보이게 하려면 미리 반대로 찌그러뜨려 둬야 한다. 그게 이 옵션이다.

원리는 한 줄이다. **벽 위의 점과, 그 점이 참조할 가상 평면 위의 점이, 눈에서 같은 방향**
이면 된다. 관람 거리는 정규화에서 상쇄되므로 화면 좌표는 `Xv = y/x`, `Zv = z/x` 로 끝난다.
자체 점검이 이 방향 일치를 직접 assert 한다.

기하는 `curved.py` 에서 직접 읽는다. 리그를 바꾸면 왜곡도 따라 바뀐다. 편집할 것이 없다.

**콘텐츠 제작자에게 전달할 사양** (`python Scripts\convert_video.py` 출력):

```
가상 평면 종횡비 1.494 : 1   <- 77:21 이 아니다. 대략 3:2
가상 래스터 7052x4718  (양 끝 배율 1.84 배 보정)
항상 벽에 보이는 세로 밴드: 원본 위에서 39.9% ~ 96.7%
스위트스팟 3500 cm 에서만 정확함
```

- **비율이 3:2 에 가깝다.** 전개 77:21 소재를 넣으면 위아래가 크게 잘린다
- **세로 안전 영역은 39.9% ~ 96.7% 뿐이다.** 벽 양 끝은 거리가 멀어 세로 화각이 좁아지므로,
  그 바깥은 벽 가운데에서만 보이고 양 끝에서는 잘린다. 중요한 요소는 이 밴드 안에 둘 것
- **가로 7052 px 이상**을 받는 게 이상적이다. 양 끝에서 원본을 1.84 배 늘려 쓰기 때문.
  더 작으면 양 끝이 부드러워진다. 가운데는 반대로 0.41 배로 버린다
- **스위트스팟에서만 맞다.** 다른 위치에서는 `_wall.mp4` 보다 더 이상하게 보인다. 원리상 불가피

구현은 ffmpeg `remap` 필터용 좌표맵(16bit PGM) 두 장을 만들어 쓴다. `remap` 은 최근접
샘플링뿐이라 `CURVED_SS = 2` 로 크게 뜬 뒤 lanczos 로 줄여 계단을 없앤다. 맵은 기하값
해시를 키로 TEMP 에 캐시되므로 두 번째 변환부터는 즉시 시작한다.

### --preview 로 눈으로 확인하기

벽이 아직 없어도 착시가 맞는지 확인할 수 있다. `--preview` 는 **전개 영상을 받아
스위트스팟에 선 사람이 볼 그림**을 만든다. `--curved` 의 역방향이다.
벽에 올리는 파일이 아니라 검증 전용이다.

```
python Scripts\convert_video.py grid.mp4 --curved
python Scripts\convert_video.py Content\Movies\grid_curved.mp4 --preview   <- 원본과 같아야 함

python Scripts\convert_video.py grid.mp4                                    (대조군)
python Scripts\convert_video.py Content\Movies\grid_wall.mp4 --preview     <- 꺾여 보여야 함
```

검증 완료 (2026-08-24, 격자 소재):

| 단계 | 결과 |
|---|---|
| `_curved.mp4` 자체 | 세로선이 가운데에서 촘촘, 양 끝에서 벌어짐. 가로선은 코너에서 아래로 모임 |
| `_curved.mp4` -> preview | **격자가 완전히 곧게 복원됨.** 세로 수직, 가로 수평, 정사각형 |
| `_wall.mp4` -> preview | 건물 모서리처럼 코너에서 확 꺾임 |
| 안전 영역 | 원본 좌상단에 둔 표식이 실제로 사라짐. 39.9%~96.7% 밴드 경고가 유효 |

preview 결과의 검은 영역은 그 방향에 벽이 없는 부분이다. 위쪽이 지붕처럼 깎여 있는데,
그게 세로 안전 밴드가 56.8% 뿐인 이유를 그림으로 보여 준다.

### 미디어 플레이트

벽 영상은 `MediaPlate` 액터로 배치되며 BeginPlay 에 자동 재생, 루프한다.
`curved.py` 의 플레이트는 워프 메시를 재사용하므로 **영상이 벽에 1:1 로 붙는다**(벽지 방식).
즉 엔진에서 재생할 때는 `_wall.mp4` 를 쓴다. `_curved.mp4` 는 LED 프로세서에 직접 넣어
엔진을 거치지 않는 경로용이다.

---

## 6. 실행 조건과 함정 (실전에서 걸린 것들)

| 증상 | 원인 / 해결 |
|---|---|
| 창은 뜨는데 nDisplay 가 아니라 일반 플레이어 카메라가 보임 | `-dc_dev_mono` 누락. 이게 없으면 렌더 디바이스 자체가 생성되지 않는다 |
| 창이 엉뚱한 모니터로 튐 / 크기가 안 맞음 | **작업표시줄 자동 숨김 필수.** 안 그러면 주 모니터 작업 영역이 48px 부족 → SWindow 가 창을 잘라냄 → 요청 크기와 달라져 `FSceneViewport::ResizeFrame` 이 다른 모니터 작업 영역 원점으로 재스냅 |
| 창 위치가 설정대로 안 감 | 창을 실제로 배치하는 것은 bat 의 `WinX/WinY/ResX/ResY`. 설정 JSON 의 window 사각형은 창을 움직이지 못한다 (5.8 의 `ResizeWindow` 는 死코드) |
| 재빌드 시 "이 파일이 이미 있습니다" | 액터가 에셋을 참조 중. `build_level()` 이 에셋보다 액터를 먼저 파괴하는 이유 |
| 재빌드 시 Error 32 / 저장 실패 | 다른 에디터가 해당 `.umap` 을 열고 있음. 그쪽에서 다른 레벨을 열고 다시 실행 |
| 눈 위치가 50cm 위로 뜸 | DCRA 기본 뷰포인트가 z=50. 설정과 인스턴스 양쪽에서 `DefaultViewPoint` 를 원점으로 고정 |
| 벽이 통째로 검게 나옴 | `curved.py`: `FLIP_WINDING` 뒤집기. `flat.py`: `PLATE_YAW` 를 180 으로 |
| 영상 파일 경로가 틀림 | 벽이 까맣게만 나온다. `demo()` 의 파일 존재 assert 가 레벨 빌드 전에 잡는다 |
| 디스플레이 배율 | 100% 여야 함 |
| 형상 knob 을 바꿨는데 `--curved` 결과가 그대로 | 리맵 맵은 `%TEMP%\wallwarp_*.pgm` 에 캐시된다. 키는 `curved.geom_key()`. **형상 knob 을 새로 추가하면 반드시 `geom_key()` 에도 넣을 것** |
| 렌더할 때마다 DCRA 위치가 제멋대로 바뀜 | **레벨 시퀀스가 DCRA 를 Possess 하고 Transform 트랙으로 덮어쓴다.** 아래 참조 |

DCRA 를 손으로 옮겨 놓았다면 재빌드가 그 위치를 **유지**한다 (`keep_transform`). `RIG_ORIGIN` 은
레벨에 DCRA 가 아직 없을 때만 쓰인다.

### 시퀀서 Transform 트랙이 리그 위치를 덮어쓴다 (2026-08-25 실사례)

증상: MRQ 로 구우면 `vp_left` 가 통째로 비고, DCRA 위치가 렌더할 때마다 바뀐다
(`0,0,245` → `-1790,870,130`). 손으로 옮겨도 다음 렌더에 날아간다.

원인: `Content/Movies/TestRenderMovie.uasset` (레벨 시퀀스) 이 `NDC_Anamorphic_2Mon` 을
Possess 하고 `MovieScene3DTransformTrack` 으로 위치/회전/스케일을 키로 잡고 있었다.
시퀀스가 끝나도 Restore State 가 꺼져 있어 마지막 키 값이 레벨에 그대로 남는다.

진단법: 디테일 패널에서 위치/회전/스케일 오른쪽의 **주황 마름모**가 채워져 있으면
현재 열린 시퀀스에 그 프로퍼티의 키가 있다는 뜻이다. 빈 회색 마름모는 키 없음.
바이너리로 확인하려면 `strings TestRenderMovie.uasset | grep -i transform`.

해결: 시퀀서에서 Transform 트랙 삭제. (연출로 움직여야 하면 섹션 우클릭 >
When Finished > Restore State 로 레벨 값 보존)

### vp_left 가 비는지 각도로 확인하기

convex 코너 리그의 두 뷰포트는 90도씩 갈라지지 않는다. **붙어서 49도 부채꼴 하나**를 만들고
경계가 리그 정면(0도)이다. `EYE_DIST_CM=60`, `MON_W_CM=70.8`, `CORNER_DEG=-90` 기준:

```
screen_left   -24.46 ~   0 도
screen_right      0 ~ +24.46 도
```

리그 코 끝보다 왼쪽에 아무것도 없으면 `vp_left` 는 절반이 아니라 **0** 이다.
실사례에서 눈 `(-1790,870,130)` / Yaw 315도 / 대상 `(0,0,0)` 은 상대각 **+19.1도** 라
전부 `vp_right` 에 몰렸다. Yaw 를 334.1 로 돌려서 해결.

대상을 정면에 놓는 각도 계산:

```python
import math
world = math.degrees(math.atan2(obj_y - eye_y, obj_x - eye_x))   # 이 값을 Yaw 로
rel   = (world - yaw + 180) % 360 - 180                          # 음수면 vp_left, 양수면 vp_right
```

에디터에서는 대상이 꽉 차게 뷰를 놓고 **액터 > 뷰에 오브젝트 스냅**이 더 빠르다.

### 좌상단 빨간 디버그 오버레이

`StereoView: Primary / Stereo rendering method: Splitscreen-like` 가 세 리그 모두에서 나온다.
`-dc_dev_mono` 가 nDisplay 스테레오 디바이스를 만들어서 `bStereoView` 가 참이 되기 때문이고,
리그 설정과는 무관하다. 출처는 `Renderer/Private/SceneRendering.cpp:4827` 의
`#if !UE_BUILD_SHIPPING` 블록이며, 상위 게이트는 이것이다.

```cpp
// SceneRendering.cpp:4635
if ((GAreScreenMessagesEnabled && !GEngine->bSuppressMapWarnings) && bViewHasWarnings)
```

각 스크립트의 `HIDE_SCREEN_MESSAGES = True` 가 Run bat 에 콘솔 명령을 붙여서 끈다.

```
 -nosplash -fixedseed -NoVerifyGC -unattended -ExecCmds="DisableAllScreenMessages"
```

로그에 `LogEngine: Onscreen warnings/messages are now DISABLED` 가 찍히면 적용된 것이다.

**주의: 이건 온스크린 경고를 전부 끈다.** "Lighting needs to be rebuilt" 같은 진짜 경고도
같이 사라진다. 상영용으로는 맞지만 개발 중에는 `False` 가 안전하다. 설정만 바뀌므로
python 만 다시 돌리면 된다 (경로 A).

---

## 7. 자체 검증

각 스크립트에 `demo()` 자체 점검이 들어 있고, 파일을 쓰기 전에 항상 먼저 실행된다.

- `anamorphic.py`: 스크린 법선이 관찰자를 향하는지, 이미지가 좌우 반전되지 않는지,
  안쪽 모서리가 베젤 위치에 정확히 오는지, 코너 각도, 뷰포인트 정의 여부, bat 와 설정의 창 크기 일치
- `flat.py`: 벽 하단이 바닥에 붙는지, 창 종횡비 = 벽 종횡비, 뷰포인트/mesh_component 해석 가능
  여부, bat 와 설정 일치, VIDEO 파일 존재
- `curved.py`: 전개 길이 = 면+호+면, 두 면이 실제로 `BEND_DEG` 를 이루는지, 호 정점이
  `EYE_DIST` 에 있는지, **3D 표면 길이 = 전개 길이**(UV 등호길이 매개변수화 검증),
  모든 지점이 눈 앞에 있고 법선이 관람자를 마주보는지, 창 종횡비, VIDEO 파일 존재
- `convert_video.py`: 출력 종횡비/짝수 높이, flat 과 curved 의 전개 크기 일치, ffmpeg 존재

```
python Scripts\anamorphic.py     # 검증 + 파일 생성
python Scripts\flat.py           # 검증 + 파일 생성
python Scripts\curved.py         # 검증 + 파일 생성 + 형상 수치 출력
python Scripts\convert_video.py  # 검증만
```

---

## 8. 알아두면 좋은 구조적 특징

**에셋 재임포트 조건.** `build_level()` 은 `.uasset` 이 **없을 때만** nDisplay 설정을 임포트한다.
스크린 크기처럼 임포트 시점에만 반영되는 값을 바꿨다면 해당 에셋
(`/Game/FlatWall/NDC_FlatWall`, `/Game/Curved/NDC_Curved`, `/Game/Anamorphic/NDC_Anamorphic_2Mon`)
을 지우고 재빌드해야 한다.

**액터 라벨 접두사.** 재빌드는 자기 접두사가 붙은 액터만 지운다.
`anamorphic.py` = `ANA_`, `flat.py` = `FLAT_`, `curved.py` = `CRV_`.
손으로 배치한 콘텐츠에는 이 접두사를 쓰지 말 것.

**편집기 표시용 프레임.** `flat.py` 는 벽 윤곽을 눈으로 확인할 수 있도록 `FLAT_top/bottom/
left/right` 막대 4개를 배치한다. 스크린 평면 위에 있어 콘텐츠를 가리므로
`set_actor_hidden_in_game(True)` 로 게임에서는 숨긴다.

---

## 9. 미확정 / 확인 필요

- `curved.py` 의 `FILLET_R_CM = 250` (지름 5 m) 은 **협의로 정한 기준값**이지 도면 확정값이 아님
- `curved.py` 의 `CONVEX = True` (코너가 관람자 쪽으로 볼록) 는 평면도 스케치를 읽은 결과.
  실제 설치가 오목이면 `CONVEX = False` 로 뒤집되, 화각이 146도가 되므로 뷰포트 분할 설계가 필요
- `curved.py` 는 `FILLET_R_CM = 0`(진짜 직각)에서 ZeroDivisionError 로 죽는다.
  `plan_point` / `plan_normal` / `column_us` / `demo` 네 군데에 R=0 가드가 필요하다.
  우회로: `FILLET_R_CM = 1.0` (호 1.6 cm, 사실상 직각)
- `RES_W = 2560` 은 데스크톱 모니터 1대에서 돌리는 **테스트 창** 크기.
  실제 LED 벽 해상도와 노드 구성(멀티 노드 클러스터)은 아직 반영되지 않았다
- `EYE_HEIGHT_CM = 160` 은 일반값. 실제 설치 조건에 맞춰 조정 필요
- 이 저장소의 `CLAUDE.md` 는 다른 프로젝트(web2d)의 템플릿이 그대로 남아 있어 본 프로젝트와
  맞지 않는다. 정리 여부 결정 필요

### 남아 있는 정리 대상 (지우려면 손으로)

파일 삭제는 하지 않았다. 확인 후 지우면 된다.

- `_deprecated/` 폴더 전체 (구 round/round_video/square 스크립트, 설정, bat, 마스크 obj)
- 언리얼 에디터에서: `Content/VprodProject/Maps/{Round, RoundVideo, Square}.umap`
- 언리얼 에디터에서: `Content/Round/` (구 `NDC_Round_1Screen`)
- `Content/Movies/*_wall_round.mp4` 와 `*_mask.png` (외곽 마스크와 짝이던 파일들)
