
---

## 작업 모드 (Working Mode)

- 기본적으로 분석 → 제안 → 승인 → 수정 순서로 진행한다.
- Default flow: Analyze → Propose → Confirm → Modify

- 사용자가 명시적으로 요청하기 전에는 파일을 수정하지 않는다.
- Do NOT modify files without explicit user request.

---


## 금지 (Forbidden)

- 민감 파일 접근 금지:
  - `.env`, `.pem`, `.key`, `.p12`
  - `service-account*.json`
  - `Secrets/**`

- Do NOT access secrets or credentials

- Git 변경 금지:
  - `git push`
  - `git reset`
  - `git clean`

- 파일 삭제 금지:
  - `rm`, `del`, `rmdir`

- Unity 실행/빌드 금지:
  - Do NOT run Unity Editor
  - Do NOT build project
  - Do NOT run Addressables build

---

## 허용 작업 (Allowed)

- 코드 분석 (Code analysis)
- 오류 분석 (Error debugging)
- 최소 수정 제안 (Minimal patch suggestion)
- 문서 생성 저장은 작업 경로에 Document 폴더를 기본으로 하고 물어본다
- read-only 명령:
  - `git diff`
  - `git status`
  - `grep`, `rg`

---

## 오류 처리 (Error Handling)

예: `NullReferenceException`

- null 체크 확인
- Check object reference
- `GetComponent` 결과 확인
- 초기화 순서 확인

---

## 응답 방식 (Response Format)

1. 원인 (Cause)
2. 해결 방법 (Fix)
3. 주의사항 (Caution)

---

## 중요 원칙 (Important)

- 최소 변경 (Minimal change)
- 안전 우선 (Safety first)
- 명확한 설명 (Clear explanation)
- CS 파일 또는 텍스트 파일 수정 할 때 원래 포멧 유지 할 것.

---

## 파일 인코딩 (File Encoding)

- 텍스트 파일(`.cs`, `.csv`, `.md`, `.json` 등)은 SportyAndRich 프로젝트와 동일하게
  UTF-8 with BOM + CRLF 로 작성/저장한다.
- Text files must be saved as UTF-8 with BOM and CRLF line endings (same as SportyAndRich).

- 파일 전체를 다시 쓸 때 BOM 이 빠지거나 개행이 LF 로 바뀌지 않도록 주의한다.
- Do NOT drop the BOM or convert line endings to LF when rewriting a whole file.

- 예외: 유니티가 생성/관리하는 파일(`.prefab`, `.unity`, `.asset`, `.meta`)은
  유니티가 저장한 형식(BOM 없음)을 그대로 둔다.
- Exception: Unity-generated files keep the format Unity writes (no BOM).