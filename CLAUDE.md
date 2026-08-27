"상세한 에이전트 역할 및 워크플로우는 agents.md를 참고하여 작업할 것."
# CLAUDE.md 운영 규칙

이 파일은 Claude Code가 매 세션 시작 시 자동으로 읽는 프로젝트 지침이다.
이 프로젝트에서 Claude는 다음 규칙을 **반드시** 따른다.

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.


---

## 0. 스킬(gstack) 실행 전 사전 조건 (최우선 필수)
사용자가 `/office-hours`, `/investigate` 등 어떠한 스킬을 호출하거나 명령을 내리더라도 **가장 먼저 `Document/todo.html`을 Read 도구로 읽어야 한다.**
읽은 후에는 반드시 **"현재 상태: [완료된 작업 1줄 요약] / [다음 진행할 작업 1줄 요약]"**을 출력한 뒤, 요청받은 작업을 수행한다.

## 1. 세션 시작 시 (필수)

작업을 시작하기 전에 무조건 `Document/todo.html` 파일을 읽고 다음을 확인한다.

- 모든 대화는 한국어로 진행 한다
- 마지막 세션까지 완료된 작업
- 진행 중이거나 다음에 해야 할 작업
- 미해결 / 차후 고려 항목
- 결정 이력 (왜 지금 이 스택·방식으로 가고 있는지)

todo.html을 읽지 않고 작업을 진행하지 말 것. 사용자가 "그냥 시작해" 같이 말해도, 먼저 todo.html을 읽고 1~2줄로 "현재 상태: ..." 요약한 뒤 진행한다.

## 2. 작업 진행 중 (필수)

작업이 의미 있게 진척될 때마다 `Document/todo.html`을 즉시 갱신한다.

"의미 있는 진척"의 기준:
- 한 단계의 코드 변경 (기능 추가, 버그 수정, 리팩터링)
- 기술 결정의 변경 (스택 교체, 라이브러리 선택 등)
- 외부 협의 결과 반영 (PM·영업·모델러와의 결정)
- 검증 결과 (스파이크 통과/실패)

갱신 규칙:
- **완료 항목**: "완료된 작업" 섹션으로 이동, 날짜 표시.
- **새 발견 작업**: "진행 중 / 다음 작업"에 추가.
- **부수적 항목**: "미해결 / 차후 고려"에 기록.
- **결정 변경**: "결정 이력" 표에 한 줄 추가 (날짜 / 결정 / 이유).

여러 작업을 한 세션에 처리할 경우 마지막에 한꺼번에 갱신하지 말고 단계별로 갱신한다. 중간에 세션이 끊겨도 다음 세션이 정확히 이어받을 수 있도록.

## 3. 산출물 저장 위치 + 파일 형식

새 디자인 문서, 플랜, 회고, 분석 리포트, 스키마 계약서, 협의 가이드 등 **모든 사용자 산출물은 `Document/` 폴더에 `.html` 형식으로 저장**한다 (2026-05-18 결정). 기존 markdown은 일괄 변환 완료, 앞으로 새 산출물도 처음부터 `.html`로 작성한다.
- `CLAUDE.md`(이 파일)·`README.md` 는 프로젝트 루트에 둔다.

## 4. 문서 용어 설명 (필수)

문서를 쓰거나 고칠 때, **처음 보는 사람이 막힐 용어는 그 문서에서 처음 나오는 자리에만** 한 줄
설명을 붙인다 (2026-08-27 결정). 이 프로젝트는 그래픽스·언리얼·시공 용어가 섞여 있어서, 도면을
주는 쪽과 영상을 만드는 쪽이 같은 문서를 읽어도 서로 다른 곳에서 막힌다.

- **대상**: 아나모픽, 스위트스팟, 전개 길이/투영 길이, 워프 메시, 절두체, 오프액시스, 입사각,
  화소 밀도, 발광부, 픽셀 피치, 블렌딩·알파 램프, 뷰포트, 클러스터, 노드, DCRA, MRQ, PFM 등.
  일상어로 바꿔 쓸 수 있으면 애초에 용어를 안 쓰는 쪽이 낫다.
- **한 번만**: 두 번째부터는 붙이지 않는다. 반복되면 본문이 읽히지 않는다.
- **형식**: `<span class="g">...</span>`. `뜻` 접두어가 붙은 회색 문장으로 본문과 구분된다.
  CSS 는 `Document/02-guide.html`·`04-site-input.html` 의 `.g` 규칙을 그대로 복사한다.
- **길이**: 한두 문장. 자세한 설명이 뒤에 따로 있으면 그 절 번호를 가리킨다
  (예: "자세한 것은 9.7").
- **표 안**: 셀 끝에 `<br>` 로 이어 붙인다. 표에는 `word-break: keep-all` 을 걸어 한글이
  낱말 도중에 끊기지 않게 한다.

## 5. 코드·구현 가이드라인

- **한국어 주석**을 우선한다.
- WHY가 비자명한 곳에만 주석. WHAT은 코드명에 맡긴다.
- **em 대시(`—`)를 코드/주석에 쓰지 않는다.** 쉼표나 마침표로 대체. (문서 본문은 가독성 위해 허용)
- 환경 분기는 항상 **두 축을 분리**해서 쓴다: `env.isTouch`(디바이스) / `env.isWebView`(컨테이너). 하나로 뭉치지 말 것.
- 네이티브 기능은 호출부에서 환경 분기하지 말고 **`bridge.xxx()` 단일 API**로 호출한다(브라우저 폴백은 브리지가 처리).
- `store/platform/native-bridge.js`의 인터페이스 이름·메서드는 **플레이스홀더**다. 앱 팀 계약(`Document/02-native-bridge.md` §7) 확정 전까지 임의 변경 주의.
- 키보드 이벤트는 물리 키(`e.code`) 사용. 모바일은 호버 없음 전제(탭/롱프레스로 대체).

## 6. 작업 환경

- OS: Windows / PowerShell 기본. Bash(Git Bash)도 가능.
- 경로: `D:\trunk\web\web2d\` 또는 `/d/trunk/web/web2d/`.
- 한글 IME 사용 가능성 있음.

---

## 우선순위

규칙 1, 2가 가장 중요하다. Document를 읽지 않으면 컨텍스트 손실로 잘못된 결정을 내릴 위험이 크다.
갱신하지 않으면 다음 세션이 컨텍스트를 잃는다. 세션 종료 시점에 문서가 현재 상태를 정확히
반영하는지 한 번 더 확인한다.

## gstack

Use the `/browse` skill from gstack for all web browsing. Never use `mcp__claude-in-chrome__*` tools.

If gstack skills aren't working, run `cd .claude/skills/gstack && ./setup` to build the binary and register skills.

### Available skills

/office-hours, /plan-ceo-review, /plan-eng-review, /plan-design-review, /design-consultation,
/review, /ship, /land-and-deploy, /canary, /benchmark, /browse, /qa, /qa-only, /design-review,
/setup-browser-cookies, /setup-deploy, /retro, /investigate, /document-release, /codex, /cso,
/autoplan, /careful, /freeze, /guard, /unfreeze, /gstack-upgrade

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health