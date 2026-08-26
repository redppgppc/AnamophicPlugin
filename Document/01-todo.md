# TODO

미해결 작업 목록. 최종 갱신 2026-08-24.
전체 구조와 결정 사항은 `00-overview.md` 참고.

---

## 0. 완료: 아나모픽 사전 왜곡 (2026-08-24)

`convert_video.py --curved` 로 `_curved.mp4` 생성. 코엑스 파도식 착시용.
기하는 `curved.py` 에서 직접 읽는다. 상세는 `00-overview.md` 5장.

**이것이 아래 1번의 우선순위를 낮춘다.** `_curved.mp4` 를 LED 프로세서에 직접 넣으면
엔진을 거치지 않으므로 톤커브/색공간 문제가 영상 경로에서 사라진다.
1번은 이제 "엔진에서 프리뷰할 때의 색 정확도" 문제로 격하된다.

---

## 1. 영상 색 패스스루 마무리 (프리뷰 정확도용, 우선순위 낮춤)

### 지금까지

영상 전용 맵에서 영상이 1:1 로 안 나가는 문제. 기본 파이프라인이 자동노출 + ACES 톤커브를
거치기 때문이다. `flat.py` / `curved.py` 에 노브와 포스트프로세스 볼륨을 넣었다.

```python
VIDEO_PASSTHROUGH = True   # 자동노출/톤커브/감마확장 끔. 3D 섞는 맵이면 False
EXPOSURE_BIAS = 0.0        # 노출 보정 EV
```

볼륨 설정: Metering Mode = Manual, Apply Physical Camera Exposure = false,
Tone Curve Amount = 0, Expand Gamut = 0, Blue Correction = 0.

### 측정 결과 (TestPattern_wall.mp4 컬러바, 실행 화면 픽셀 직접 비교)

| 바 | 원본 | 패스스루 이전 | 패스스루 적용 |
|---|---|---|---|
| 빨강 | (252, 0, 0) | (255, 58, 32) | (207, 71, 18) |
| 초록 | (0, 254, 0) | (33, 241, 37) | (6, 192, 18) |
| 노랑 | (253, 254, 0) | (246, 246, 91) | (245, 231, 18) |
| 파랑 | (0, 0, 253) | (82, 121, 244) | (6, 21, 246) |
| 자홍 | (253, 0, 252) | (255, 136, 241) | (226, 37, 227) |
| 청록 | (0, 254, 254) | (105, 230, 234) | (6, 187, 207) |

**최대 채널 오차 136 -> 71.** 0 이어야 할 채널의 누출(탈색)은 거의 잡혔다.

### 남은 문제

주 채널이 어두워진다. 선형 광량 비율(1.000 이면 완벽):

```
빨강 R  0.641      노랑 R  0.930      파랑 B  0.938
초록 G  0.532      노랑 G  0.806      청록 G  0.501
자홍 R  0.774      자홍 B  0.789      청록 B  0.630
```

**채널마다 비율이 다르다.** 노출 문제라면 세 채널이 같은 비율로 줄어야 하는데 0.50 ~ 0.94 로
흩어져 있다. 즉 `EXPOSURE_BIAS` 같은 스칼라로는 못 잡는다. 3x3 색공간 행렬이 아직 끼어 있다.
초록이 가장 많이 깎이는 것도 색역 변환의 전형적인 패턴이다.

### 다음에 확인할 것

- Working Color Space 프로젝트 설정 (UE5 기본이 sRGB/Rec709 왕복이면 항등이어야 함)
- `M_MediaPlate_Opaque` 가 Lit 인지 Unlit 인지. Lit 이면 템플릿의 태양광/스카이라이트 색이
  곱해진다. 이게 원인이면 머티리얼 교체가 답
- `r.TonemapperOutputDevice` 등 출력 디바이스 변환
- 포스트프로세스의 Color Grading 기본값(Saturation/Contrast/Gain)이 실제로 중립인지

### 판단 필요

1. **여기서 멈춤** - 탈색은 잡혔으니 최종 색은 LED 프로세서에서 캘리브레이션. 현장에서 흔한 방식
2. **끝까지 추적** - 위 항목을 하나씩. 몇 라운드 더 필요
3. **영상 전용 맵은 엔진을 안 거침** - 전개 파일을 LED 프로세서에 직접 넣으면 색 문제 자체가
   없어진다. 이 경우 패스스루 볼륨은 프리뷰 정확도용으로만 의미

재측정 방법: `VIDEO` 를 `TestPattern_wall.mp4` 로 두고 빌드 -> 실행 -> 화면 캡처 ->
원본 프레임과 같은 좌표의 컬러바 픽셀 비교. 컬러바 x 좌표 210/640/1065/1490/1920/2350, y=120.

---

## 2. curved.py 의 FILLET_R_CM = 0 (진짜 직각) 지원

지금은 ZeroDivisionError 로 죽는다. 네 군데에 R=0 가드가 필요하다.

- `plan_point` - `phi = d / R` 에서 0 나눗셈
- `plan_normal` - 같음
- `column_us` - 호 분할 루프가 같은 값을 ARC_SEG 개 만들어 퇴화 삼각형이 생김
- `demo` - 화소 밀도 계산에서 `arc_deg` 0 나눗셈

우회로: `FILLET_R_CM = 1.0` (호 1.6 cm, 사실상 직각). 실행 확인됨.

---

## 3. 도면/현장 확인 대기

- `curved.py` 의 `FILLET_R_CM = 250` (지름 5 m) 은 협의로 정한 기준값이지 도면 확정값이 아님
- `curved.py` 의 `CONVEX = True` (코너가 관람자 쪽으로 볼록) 는 평면도 스케치를 읽은 결과.
  실제 설치가 오목이면 `CONVEX = False` 로 뒤집되, 화각이 48도에서 **146도**로 폭증하므로
  단일 뷰포트로는 감당이 안 된다. 면/호를 뷰포트 3개로 쪼개는 설계가 따로 필요
- `EYE_HEIGHT_CM = 160` 은 일반값. 실제 설치 조건에 맞춰 조정
- `RES_W = 2560` 은 데스크톱 모니터 1대용 **테스트 창** 크기. 실제 LED 벽 해상도와
  멀티 노드 클러스터 구성은 아직 반영 안 됨

---

## 4. 정리 대상 (파일 삭제는 안 했음)

- `_deprecated/` 폴더 전체 (구 round / round_video / square 일체)
- 언리얼 에디터에서: `Content/VprodProject/Maps/{Round, RoundVideo, Square}.umap`
- 언리얼 에디터에서: `Content/Round/` (구 `NDC_Round_1Screen`)
- `Content/Movies/*_wall_round.mp4` 와 `*_mask.png` (삭제된 외곽 마스크와 짝이던 파일)
- 이 저장소의 `CLAUDE.md` 는 다른 프로젝트(web2d) 템플릿이 그대로 남아 있어 내용이 맞지 않음

---

## 5. 현재 파일 상태 (다음 세션 인수인계)

색 측정을 하느라 바꿔 둔 값이 있다. 원래대로 돌릴지 결정 필요.

```python
# Scripts/curved.py
VIDEO = "Content/Movies/TestPattern_wall.mp4"   # 측정용. 원래는 MediaExample_wall.mp4
VIDEO_PASSTHROUGH = True
DEMO = False
```

`Curved.umap` 도 이 설정으로 빌드돼 있다. `flat.py` 는 `MediaExample_wall.mp4` 상태.

주의: `MediaExample` 계열 영상은 **평균 휘도 0.0 인 거의 완전 검정**이다. 원본부터 그렇다.
재생은 되는데 화면에 아무것도 없어 보인다. 눈으로 확인할 때는 반드시 `TestPattern` 쪽을 쓸 것.

