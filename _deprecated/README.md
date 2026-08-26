# _deprecated

2026-08-24 에 정리한 구 파일들. **삭제해도 된다.** 확인 여유를 주려고 남겨 뒀을 뿐이다.

## 왜 없앴나

`round.py` 계열은 "라운드"를 **화면 외곽선 네 모서리를 둥글게 깎는 것**으로 구현했다.
실제 요구사항은 **벽이 평면도에서 90도로 꺾일 때 그 꺾임부가 필렛지는 것**이었다.
서로 다른 개념이고, 외곽 마스크는 아무도 요청한 적이 없다.

그 결과 리그가 3개 생겼는데 셋의 차이는 이 마스크의 on/off 조합뿐이었다.

| 구 리그 | ROUNDED | VIDEO | 실제로는 |
|---|---|---|---|
| Round | True | 없음 | 마스크 켜진 평면 벽 |
| RoundVideo | True | 있음 | 마스크 켜진 평면 벽 + 영상 |
| Square | False | 있음 | 그냥 평면 벽 + 영상 |

## 어디로 갔나

- 평면 벽 -> `Scripts/flat.py` (Square 와 동등, 마스크 코드 제거)
- 꺾인 벽 -> `Scripts/curved.py` (원래 요구사항)

`convert_video.py` 의 `--rounded` 옵션도 이 마스크와 짝이라 함께 제거했다.
`Content/Movies/*_wall_round.mp4` 도 쓸 데가 없다.

## 여기 있는 것

```
Scripts/round.py  round_video.py  square.py
nDisplay/Round_1Screen.ndisplay  RoundVideo_1Screen.ndisplay  Square_1Screen.ndisplay  Round_Mask.obj
Rebuild_Round.bat  Rebuild_RoundVideo.bat  Rebuild_Square.bat
Run_Round.bat  Run_RoundVideo.bat  Run_Square.bat
```

언리얼 에셋은 손대지 않았다. 에디터에서 지울 것:
`Content/VprodProject/Maps/{Round,RoundVideo,Square}.umap`, `Content/Round/`
