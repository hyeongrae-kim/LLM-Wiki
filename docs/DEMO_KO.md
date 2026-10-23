# 시연 대본 — LLM-Wiki (22대 국회 특별검사법)

목표: 논문의 LLM-Wiki가 한국어 raw 데이터를 위키로 **구축**하고, 에이전트가 위키를 **탐색해 답하고**,
새 데이터를 **추가**하면 기존 페이지가 갱신되며, **Error Book**이 결함을 기록하고 → 주입하고 → 수리하고 → 종료하는
전 과정을 보여준다.

## 소요 시간 (2026-10-24 리허설 실측, gpt-6-luna)

| 단계 | 시간 |
|---|---|
| 전체 구축 `make build` (154개 문서) | 약 80분 (사전 실행) |
| `make demo-errorbook` (결함 심기, lint, 제약 표시) | 1초 미만 |
| `make demo-add` (문서 5개, light finalize) | 약 4분 |
| 검증 lint 1회 | 1초 미만 |
| `make ask` 질문 1개 | 8~15초 (도구 호출 2~5회) |
| `make demo-reset` | 1초 미만 |

## 0. 사전 준비 (시연 전날)

```bash
make setup                         # .venv + .env (OPENAI_API_KEY 입력)
make prepare PRESET=full           # 예제 문서 154개 → raw/assembly_spc/articles
make build                         # 위키 구축 + "built" 스냅샷 저장
make site                          # (별도 터미널) Quartz → http://localhost:8080 (포트가 사용 중이면 make site PORT=8090)
```

- Obsidian에서 `wiki_output/assembly_spc/wiki`를 vault로 열고, 그래프 뷰를 띄워 둔다.
- 터미널을 2개 준비한다: ① 명령 실행용, ② `tail -f wiki_output/assembly_spc/wiki/log.md`.
- 시연이 끝날 때마다 `make demo-reset`으로 "built" 상태로 되돌린다.

## 1. 도입

- **논문:** 검색을 한 번의 조회가 아니라 *추론 과정*으로 본다 (Retrieval-as-Reasoning).
  - 문서를 링크된 위키로 컴파일한다.
  - 에이전트가 `wiki_search`와 `wiki_read`를 조합해 탐색한다.
  - Error Book으로 위키 품질을 스스로 교정한다.
- **카파시 LLM Wiki와의 관계:** 3층 구조(raw → wiki → schema)와 ingest·query·lint라는 뼈대는 같다.
  차이는 사람이 아니라 에이전트가 읽도록 설계했고, 코드로 자동화했으며, 벤치마크로 검증했다는 점이다.

## 2. raw → 문서

```bash
ls raw/bills raw/votes raw/members raw/minutes      # 원천 테이블 (법안 2.2만, 표결 1,911, 발언 217만 줄 …)
sed -n 1,45p examples/assembly_spc/articles/vote-1627.md
```

- 정형 테이블을 "문서 1개 = md 1개"로 변환했다 (`corpora/assembly/convert.py`).
- 표결 문서에는 정당별 찬반표와 **정당 내 소수 의견 투표자**(안철수 찬성, 김재섭 반대)가 들어 있다.

## 3. 구축 결과

```bash
make status
sed -n 1,40p wiki_output/assembly_spc/wiki/index.md
```

- 구축 로그에서 `🔍 Selected N pages`(Step 1)와 `📄 Written …`(Step 2), `📔 Error Book: injecting …`을 보여준다.
- Quartz에서 `bills/의안-2200038-…` 페이지를 열어 Key Facts, Related Pages(링크), Related Sources(digest)를 보여준다.
- Obsidian 그래프 뷰에서 의원 · 법안 · 표결 · 사건 페이지가 서로 연결된 구조를 보여준다.

## 4. 검색 (라이브)

```bash
make search Q="순직 해병"           # LLM 없이 이름·별칭·태그 우선 점수 + 한글 BM25
make ask Q="순직 해병 특검법 첫 본회의 표결에서 국민의힘 소속으로 찬성한 의원은?"
```

- trace에서 search → read → 링크 따라가기 순서를 짚어 준다. 정답은 **안철수**.
- 두 문서를 거쳐야 하는 질문 (법안 → 대표발의 의원 → 선거구):

```bash
make ask Q="의안번호 2206292 김건희 특검법을 대표발의한 의원의 선거구는?"
```

## 5. Error Book ① 결함 심기와 기록 (라이브)

```bash
make demo-errorbook     # 결함 3개를 심고 → lint로 기록 → 주입될 제약을 보여준다
```

`inject-demo`가 심는 결함은 다음 세 가지다 (실행 전에 스냅샷 `before-inject`가 저장된다).

1. **깨진 링크:** 페이지가 아직 없는 실제 의원에게 링크를 건다.
2. **한 줄 요약 누락:** 의원 페이지의 `>` 요약 줄을 지운다.
3. **잘못된 디렉터리:** 법안 페이지를 다른 디렉터리로 옮긴다. frontmatter의 `type`은 그대로 둔다.

`lint` 결과 각 유형이 `📔 New error E..`로 기록되고, `errorbook show` 출력에서
**다음 Step 2 프롬프트에 주입될 "Known Issues"** 를 확인할 수 있다.

## 6. 데이터 추가 (라이브) — 제약 주입과 수리를 함께 보여주기

```bash
make demo-add           # 2026년 7~9월 '지방선거 투표용지 부족 사태' 특검 문서 5개
```

- `📔 Error Book: injecting N active constraint(s) into the Step 2 prompt`: 앞에서 기록한 제약이 새 문서를 생성하는 프롬프트에 들어간다.
- `🔍 Selected 3 pages: ['김용민', '법제사법위원회', …]`: Step 1이 새 법안의 대표발의자인 **기존** 의원 페이지를 고른다.
  Step 2는 `📄 Written wiki/members/김용민.md`로 그 페이지에 새 법안 사실을 병합한다.
- 배치 사이 lint에서 E02(잘못된 디렉터리)는 코드가 수리한 뒤 2회 연속 통과해 **closed**된다.
- light finalize가 실행되면 다음이 수리된다.
  - **코드 수리:** 디렉터리가 잘못된 페이지를 원래 위치로 옮긴다.
  - **LLM 수리:** 한 줄 요약을 다시 생성하고, 깨진 링크의 대상 의원 페이지를 새로 만든다.
- 갱신 전후를 비교한다.

```bash
diff .snapshots/assembly_spc/built/wiki/members/김용민.md wiki_output/assembly_spc/wiki/members/김용민.md
tail -20 wiki_output/assembly_spc/wiki/log.md
```

- 새 데이터와 기존 데이터를 결합해야 하는 질문:

```bash
make ask Q="의안번호 2221376 투표용지 부족 사태 특검법 개정안을 대표발의한 의원이 현재 소속된 상임위원회는?"
```

## 7. Error Book ② 검증 후 종료 (라이브)

```bash
.venv/bin/llm-wiki lint --corpus assembly_spc   # 1회 더 통과하면 E01, E03 closed (light finalize의 lint가 첫 번째 통과)
.venv/bin/llm-wiki errorbook --corpus assembly_spc export
```

리허설 결과: `📔 Error E01 (broken_link) … closed`, `📔 Error E03 (missing_summary) … closed`
→ `Error Book (0 active / 3 closed)`.

새 데이터를 써야 답할 수 있는 질문(6절)은 다음 경로로 답했다 (도구 호출 3회, 8.5초).
1. `search "2221376"`
2. `read 의안-2221376`: 새로 추가된 페이지
3. `read 김용민`: 링크를 따라간 기존 페이지
4. 답: **법제사법위원회**

Quartz나 Obsidian에서 `error-book.md`를 연다. 활성·종료 항목, 남은 제약, 수리 이력(`lint_ledger.jsonl`)을 보여준다.

## 8. 정리

```bash
make demo-reset         # "built" 스냅샷으로 복원
```

## 참고: 예상 질문과 정답

`examples/assembly_spc/questions.jsonl`에는 표 데이터에서 계산한 질문과 정답이 들어 있다 (`stage: initial | add`).
`llm-wiki eval --limit 10`으로 채점할 수 있다.
