# LLM-Wiki 한국어 시연판 — 22대 국회 특별검사법

논문 **Retrieval as Reasoning: Self-Evolving Agent-Native Retrieval via LLM-Wiki**
([arXiv 2605.25480](https://arxiv.org/abs/2605.25480))의 공식 코드
([WeAgentAI/LLM-Wiki](https://github.com/WeAgentAI/LLM-Wiki))를 fork해서
**한국어 코퍼스**로 위키를 구축하고, 검색하고, 데이터를 추가하고, **Error Book**으로 스스로 교정하는 과정을
누구나 재현할 수 있게 만든 버전이다.

- **예제 데이터:** 제22대 국회(2024-05-30~)의 특별검사법 관련 의안·본회의 표결·대표발의 의원·본회의 회의록.
  원천 테이블에서 변환한 문서 154개가 [examples/assembly_spc](examples/assembly_spc)에 포함되어 있다.
- **LLM:** OpenAI 호환 API라면 무엇이든 쓸 수 있다. 시연은 `gpt-6-luna`로 했다.
- **완성된 위키 사이트:** https://hyeongrae-kim.github.io/LLM-Wiki/
- **원본 README:** 영어 설명과 원본 벤치마크(HotpotQA 등) 실행 방법은 [원본 레포의 README](https://github.com/WeAgentAI/LLM-Wiki#readme)에 있다.

## 문서 (`docs/`)

| 문서 | 내용 |
|---|---|
| [docs/DEMO_KO.md](docs/DEMO_KO.md) | **시연 가이드.** 원본 데이터에서 무엇을 어떻게, 왜 골랐는지, 시연 순서와 그 이유, 사전 준비와 화면 배치, 단계별 명령·예상 출력·짚을 말, 시간 조절, 문제 대응, 예상 질문과 정답 |
| [docs/CHANGES_KO.md](docs/CHANGES_KO.md) | **원본 코드 대비 변경 사항.** Error Book을 논문 설명대로 동작하게 고친 내용, 실행 경로·호환성 버그, 매칭 버그, 수리 품질 버그, 한국어 지원, 사용 편의(CLI·Makefile·Quartz) |
| [docs/logs/](docs/logs) | **실제 실행 로그.** 시연 가이드가 인용하는 v2 전체 구축 로그(`build-v2.log`)와 시연 리허설의 데이터 추가 로그(`rehearsal-demo-add.log`) |
| [docs/PROJECT_REPORT_KO.md](docs/PROJECT_REPORT_KO.md) | **프로젝트 전체 정리.** 계획을 세운 방법과 결정, 세팅, 진행 타임라인, v1·v2를 두 번 구축한 이유, 리허설 결과, Quartz·Pages 문제 해결, API 비용·시간 |

## 무엇을 하는가

```
raw 문서 ──ingest──▶ LLM-Wiki (Markdown, [[링크]]) ──wiki_search / wiki_read──▶ 에이전트 답변
   (Step 1: 갱신할 기존 페이지 선택 → Step 2: 페이지 생성·병합)
                          ▲                │
                          └── Error Book ◀─┘  lint → 기록 → 프롬프트 제약 주입 → 수리 → 재검증 → 종료
```

1. **구축 (offline compilation):** 문서마다 두 단계로 처리한다.
   - Step 1 (fast 모델): 위키의 디렉터리 인덱스를 보고, 이 문서로 갱신해야 할 기존 페이지를 고른다.
   - Step 2 (premium 모델): digest(원문 요약)와 지식 페이지를 생성하거나 기존 페이지에 병합한다.
2. **검색 (Retrieval-as-Reasoning):** 에이전트가 두 도구를 반복해서 조합해 근거를 모은다.
   - `wiki_search`: 이름·별칭·태그·설명을 우선 매칭하고, 그다음 본문(BM25)을 본다. 본문 대신 메타데이터만 돌려준다.
   - `wiki_read`: 페이지 본문과 `[[링크]]` 목록을 돌려준다.
   - 기본 설정: 도구 호출 최대 15회, 빈 검색 3회 연속이면 중단, 검색당 최대 5페이지.
3. **추가:** 새 문서만 ingest한다. Step 1이 관련된 기존 페이지(예: 같은 의원)를 골라 내용을 병합한다.
4. **Error Book:** 구조 오류(깨진 링크, 요약·섹션 누락, type·디렉터리 불일치 등)를 탐지해 기록한다.
   - 다음 생성 프롬프트에 "Known Issues"로 제약을 주입한다.
   - 코드와 LLM으로 수리한 뒤, lint를 2회 연속 통과하면 해당 항목을 닫는다.

## 빠른 시작

요구사항: Python 3.10 이상, OpenAI API 키. Quartz 사이트를 쓰려면 Node 22 이상과 npm 10.9.2 이상도 필요하다.

### 바로 시연하기 (구축 없이)

레포에 이미 구축된 시연 기준 위키(`.snapshots/assembly_spc/built/`)가 들어 있다. 클론한 뒤 복원만 하면 된다.

```bash
git clone https://github.com/hyeongrae-kim/LLM-Wiki.git && cd LLM-Wiki
make setup                 # .venv 생성, 패키지 설치(editable), .env 생성
# .env 의 OPENAI_API_KEY 입력 (모델·언어 기본값: gpt-6-luna, WIKI_LANG=ko)

make demo-reset            # 시연 기준 위키 복원 (지식 페이지 179개)
make ask Q="순직 해병 특검법 첫 본회의 표결에서 국민의힘 소속으로 찬성한 의원은?"
```

시연 순서와 단계별 명령은 [docs/DEMO_KO.md](docs/DEMO_KO.md)에 있다.

### 직접 구축하기

```bash
make quickstart            # 문서 27개(small preset)로 처음부터 구축 — 약 20분, "small" 스냅샷으로 저장
```

전체 154개 문서로 구축하려면 다음을 실행한다 (약 80분, API 비용 약 $0.7).

```bash
make clean-wiki            # 작업 중인 위키·입력 문서·캐시 삭제 (스냅샷은 남는다)
make prepare PRESET=full
make build                 # 끝나면 "built" 스냅샷을 새 위키로 덮어쓴다 (make demo-reset으로 복원)
```

`make help`로 전체 명령을 볼 수 있다. `make`를 쓰지 않는다면 `.venv/bin/llm-wiki <명령>`을 직접 실행하면 된다.

## 명령어 (`llm-wiki`)

| 명령 | 설명 |
|---|---|
| `prepare --source DIR --config-dir DIR [--preset small\|full]` | 문서를 `raw/<corpus>/articles`로 복사하고, purpose와 page_types를 배치한다 |
| `build [--batch-size 2] [--finalize full\|light\|none]` | 위키를 구축한다. finalize 기본값 `full`은 논문 기본(lint↔수리 3라운드)이다 |
| `add FILES… [--finalize light]` | 문서를 증분 추가한다 |
| `search "질의"` | `wiki_search`만 실행한다 (LLM 없음) |
| `ask "질문" [-v]` | 에이전트 탐색 trace와 답변을 출력한다 |
| `eval [--stage initial\|add] [--limit 10]` | 표 데이터에서 계산한 정답으로 채점한다 |
| `lint` / `fix [--llm] [--content]` | lint를 실행해 Error Book에 기록한다 / 코드·LLM으로 수리한 뒤 다시 lint한다 |
| `errorbook show\|export\|inject-demo` | Error Book과 주입될 제약을 보여 준다 / `wiki/error-book.md`를 만든다 / 시연용 결함 3개를 심는다 |
| `snapshot` / `restore [--name]` | 위키·입력 문서·캐시·purpose를 백업하고 복원한다 |
| `status` | 위키 통계 |

모든 명령은 `--corpus`(기본값 `$WIKI_CORPUS`)를 받는다. `--log-llm`을 붙이면 LLM 호출 로그도 출력된다.

## 내 데이터로 만들기

1. 문서 1개를 Markdown 파일 1개로 만들어 한 폴더에 모은다.
   frontmatter에 `title:`을 넣으면 그 값이 제목이 되고, 없으면 파일명이 제목이 된다.
   한국어 문서는 6,000~8,000자 이하로 나누는 것이 좋다.
2. 코퍼스 설정 폴더에 다음 두 파일을 만든다 (예: [corpora/assembly](corpora/assembly)).
   - `purpose.md`: 무엇을 중점적으로 추출할지 적는다.
   - `page_types.yaml`: 디렉터리 이름은 영어, 설명은 한국어로 쓴다.
   - 이 두 파일이 없으면 LLM이 샘플 문서를 보고 자동으로 만든다.
3. 다음을 실행한다.
   ```bash
   llm-wiki prepare --corpus my_docs --source path/to/docs --config-dir path/to/config
   llm-wiki build --corpus my_docs
   ```

**언어 규칙** (`WIKI_LANG=ko`): 섹션 제목(`## Key Facts` 등), frontmatter 키, 디렉터리 이름은 lint가 검사하므로 영어로 유지한다.
나머지 내용(페이지 이름, 요약, 사실, 별칭, 태그, 인덱스 섹션 이름)은 한국어로 쓴다.

### 국회 데이터 변환 (선택)

예제 문서는 레포에 포함되어 있다. 원천 테이블이 있다면 직접 다시 생성할 수 있다.

```bash
# raw/bills/{bills,bill_sponsors}.csv, raw/votes/{rollcalls,rollcall_records}.csv,
# raw/members/{members,member_party_timeline,member_committees}.csv,
# raw/minutes/minutes.csv, raw/minutes/speeches.jsonl
make convert               # 기본값: --keyword 특별검사 --add-keyword 지방선거
```

## 위키 보기: Obsidian · Quartz · GitHub Pages

- **Obsidian:** `wiki_output/<corpus>/wiki` 폴더를 vault로 연다. 그래프 뷰로 페이지 간 링크를 볼 수 있다.
- **Quartz:** `make site`를 실행하면 http://localhost:8080 에서 볼 수 있다. 포트가 사용 중이면 `make site PORT=8090`으로 바꾼다.
  처음 실행할 때 Quartz v5와 플러그인을 `.quartz/`에 설치한다. 고정 버전(`QUARTZ_REF`)이 바뀌면 자동으로 다시 설치한다.
- **GitHub Pages:** `make deploy-pages`를 실행하면 정적 사이트만 `gh-pages` 브랜치에 push하고 Pages를 활성화한다.
  작업 중인 위키(`wiki_output/`)는 커밋하지 않는다. 시연 기준 위키는 `.snapshots/assembly_spc/built/`에만 커밋돼 있다.

## 설정 (`.env`)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `OPENAI_API_KEY`, `OPENAI_BASE_URL` | — | OpenAI 호환 엔드포인트 |
| `LLM_PREMIUM_MODEL` / `LLM_FAST_MODEL` | `gpt-6-luna` | Step 2·페이지 생성용 / Step 1·lint 수리·답변용 |
| `LLM_REASONING_EFFORT` | `low` | 추론 모델의 텍스트 호출에 적용. 에이전트의 도구 호출은 항상 `none` |
| `WIKI_LANG` | `ko` | `en`이면 원본과 같은 동작 |
| `INGEST_STEP_PAUSE` | `0` | Step 1과 Step 2 사이 대기 시간(초) |
| `WIKI_DUMP_PROMPTS` | `0` | `1`이면 Step 1·2 프롬프트를 `wiki_output/<corpus>/logs/prompts/`에 저장 |
| `ABLATION_ERROR_BOOK` | `1` | `0`이면 Error Book을 끈다 (논문의 ablation) |
| `GROUNDING_SOURCE_CHARS` | `20000` | 사실 근거 검증에 쓰는 원문 분량 |

## 테스트

```bash
make test                  # API 호출 없는 오프라인 테스트
```

## 인용

```bibtex
@misc{ming2026retrievalreasoningselfevolvingagentnative,
      title={Retrieval as Reasoning: Self-Evolving Agent-Native Retrieval via LLM-Wiki},
      author={Haoliang Ming and Feifei Li and Xiaoqing Wu and Wenhui Que},
      year={2026},
      eprint={2605.25480},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2605.25480},
}
```

라이선스: MIT (원본과 동일).
