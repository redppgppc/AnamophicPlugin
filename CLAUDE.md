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

## 1. 세션 시작 시 (필수)

작업 전에 `Document/` 의 설계 문서를 먼저 읽고 현재 맥락을 파악한다.

- 모든 대화는 **한국어**로 진행한다.
- `Document/00-overview.md` — 프로젝트 목적·디자인 참조·전제
- `Document/01-platform-architecture.md` — 멀티플랫폼 아키텍처
- `Document/02-native-bridge.md` — 네이티브 브리지 설계

문서를 읽지 않고 작업을 진행하지 말 것. "그냥 시작해" 같은 말에도, 먼저 위 문서를 확인하고
1~2줄로 "현재 상태: ..." 요약한 뒤 진행한다.

## 2. 작업 진행 중 (필수)

의미 있는 진척이 있을 때마다 관련 문서를 즉시 갱신하고, **git commit** 한다.

"의미 있는 진척"의 기준:
- 한 단계의 코드 변경 (기능 추가, 버그 수정, 리팩터)
- 기술 결정의 변경 (스택 선택·교체, 라이브러리 등)
- 외부 협의 결과 반영 (앱 팀 브리지 스펙, 디자인 시안 등)

세션 중 여러 작업은 마지막에 몰아서 갱신하지 말고 단계별로 갱신·커밋한다.
중간에 세션이 끊겨도 다음 세션이 정확히 이어받을 수 있도록.

## 3. 산출물 저장 위치 + 형식

- 설계 문서·플랜·분석·회의록 등 **모든 사용자 산출물은 `Document/` 폴더에 Markdown(`.md`)** 으로 저장한다.
- `CLAUDE.md`(이 파일)·`README.md` 는 프로젝트 루트에 둔다.

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