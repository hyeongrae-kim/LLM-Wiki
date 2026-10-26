# 시연 가이드 — LLM-Wiki (22대 국회 특별검사법)

이 레포를 `git clone`한 뒤 이 문서만 따라 하면 시연을 준비하고 진행할 수 있다. 처음이라면 [§3 준비](#3-준비-git-clone부터-시연-직전까지)부터 시작한다.
- 명령은 모두 레포 루트에서 실행한다.
- 시연 기준 위키가 레포에 들어 있어서 다시 구축할 필요가 없다. OpenAI API 키만 있으면 된다.
- 예상 출력과 시간은 2026-10-24 리허설과 2026-10-26 새 클론 확인에서 실측한 값이다 (모델 gpt-6-luna). 새 클론 확인에서는 이 문서의 명령을 처음부터 끝까지 그대로 실행했다.
- 설치 방법은 [README.md](../README.md), 원본 코드 대비 수정 사항은 [CHANGES_KO.md](CHANGES_KO.md), 프로젝트 전체 경과와 비용은 [PROJECT_REPORT_KO.md](PROJECT_REPORT_KO.md)에 있다.

---

## 1. 시연 데이터: 무엇을, 어떻게, 왜 골랐나

### 원본 데이터

원본은 22대 국회 공개 데이터다. CSV/JSON 테이블로 약 2GB이며, 공개 레포에는 올리지 않았다.

| 테이블 | 규모 | 용량 |
|---|---|---|
| 법안 (`bills.csv`, `bill_sponsors.csv`) | 의안 21,988건, 발의자 기록 약 26만 건 | 516MB |
| 표결 (`rollcalls.csv`, `rollcall_records.csv`) | 본회의 표결 1,911건, 의원별 표결 기록 약 42만 건 | 115MB |
| 의원 (`members.csv`, 정당 이력, 위원회 이력) | 의원 321명 | 1.9MB |
| 회의록 (`minutes.csv`, `speeches.jsonl`) | 회의록 2,180건(본회의 134건), 발언 약 130만 건 | 1.3GB |

전체를 위키로 만들 수는 없다. 이번 구축은 문서 1개에 평균 약 31초가 걸렸다(154개에 약 80분). 이 속도라면 의안만 처리해도 약 190시간이 걸린다.

### 어떻게 골랐나

변환기는 `corpora/assembly/convert.py`이고, 실행 명령은 `make convert`다(raw 데이터가 있어야 한다). 주제 키워드 하나로 법안을 먼저 고르고, 그 법안에 연결된 표결·의원·회의록만 따라가며 잘랐다.

| 순서 | 대상 | 고르는 규칙 | 결과 |
|---|---|---|---|
| ① | 법안 | 의안명에 "특별검사"가 들어간 의안 | 21,988건 → **85건** (발의일 2024-05-30 ~ 2026-10-13) |
| ② | 표결 | ①의 법안에 대한 본회의 표결 | 1,911건 → **23건** |
| ③ | 의원 | ①의 대표발의자 | 321명 → **42명** |
| ④ | 회의록 | 안건에 ①의 의안번호가 있고, 표결 당일이나 전날 열린 본회의 | 2,180건 → **14건** |

- ④에서 전날까지 보는 이유는 자정을 넘겨 진행된 회의 때문이다. 예를 들어 7/4 표결이 7/3 회의록에 들어 있다.
- 발언은 "특별검사"나 "특검"을 언급한 것만 남겼다. 의장·사무총장 같은 진행 발언은 뺐고, 회의당 12개, 발언당 500자까지만 넣었다.

테이블의 행을 그대로 넣지 않고, 여러 테이블을 이어 붙여 사람이 읽는 문서로 만들었다. 문서 1개가 md 파일 1개다.

| 문서 | 내용 |
|---|---|
| 법안 `bill-<의안번호>.md` | 기본 정보, 심사·처리 경과, 대통령 재의요구, 제안이유(1,500자 이하), 주요내용(2,500자 이하). 공동발의자는 따로 문서를 만들지 않고 정당 분포로만 적었다 |
| 표결 `vote-<표결ID>.md` | 정당별 찬반, 소속 정당과 다르게 투표한 의원, 반대·기권 명단. 의원별 표결 기록을 집계해 만들었다 |
| 의원 `member-<의원ID>.md` | 인적 사항, 정당·위원회 이력, 이 주제에서 대표발의한 법안. 동명이인은 이름 옆에 생년을 적었다 |
| 회의록 `meeting-<회의록ID>-N.md` | 안건, 관련 표결, 관련 발언 발췌. 내용이 길면 여러 문서로 나눴다 |

- 모든 문서를 6,000자 이하로 맞췄다. 그보다 길면 ingest 프롬프트에서 잘리기 때문이다.
- 한글은 NFC로 정규화했고, BOM을 제거했다.

만든 문서는 쓰임에 따라 나눴다.

| 세트 | 골라낸 기준 | 문서 수 | 쓰임 |
|---|---|---|---|
| `articles/` | 아래 지방선거 클러스터를 뺀 전부 | 154 (법안 78, 표결 21, 의원 38, 회의록 17) | 사전 구축 |
| `add/` | 의안명에 "지방선거"도 들어가고 표결까지 간 법안, 그 표결, 표결이 있었던 본회의 | 5 (법안 2, 표결 2, 회의록 1) | 시연 5단계 라이브 추가 |
| `add_extra/` | 같은 클러스터에서 표결 없이 끝난 법안과 그 대표발의자 | 9 (법안 5, 의원 4) | 예비 |
| small preset | 2025-01-01 이전에 표결된 법안과 관련 문서 | 27 | 빠른 체험용 (구축 22분) |
| `questions.jsonl` | 테이블에서 정답을 계산한 질문 | 226 | 채점 |

- 추가 세트의 대표발의자 김용민은 초기 세트에 이미 들어 있다. 그래서 추가 세트에는 의원 문서를 다시 넣지 않았다.
- 이렇게 해 두면 데이터를 추가할 때 김용민 페이지를 새로 만들지 않고, 기존 페이지에 새 사실을 병합하게 된다.

### 왜 이 데이터인가

계획 단계에서 데이터를 자르는 방식 세 가지를 비교했다: 주제 하나, 위원회 하나, 의원 몇 명. 그중 **주제 하나("특별검사법")**를 골랐다. 이유는 다음과 같다.

1. **멀티홉 질문이 자연스럽게 생긴다.**
   - 법안 → 대표발의 의원 → 선거구·상임위원회
   - 표결 → 정당별 찬반 → 소속 정당과 다르게 투표한 의원

   답이 한 문서에 다 있지 않아서, 링크를 따라가야 찾을 수 있다. 논문이 말하는 "추론으로서의 검색(Retrieval as Reasoning)"을 보여주기에 맞다.
2. **같은 사건이 여러 문서에 반복해서 나온다.** 22대 국회의 특검법은 발의 → 가결 → 대통령 재의요구 → 재의결 부결 → 재발의를 되풀이했다.
   - 의안명 기준으로 김건희 관련 22건, 내란 관련 15건, 순직 해병 관련 9건이다.
   - 그래서 여러 문서가 같은 페이지를 갱신하게 되고, 위키의 병합(Step 1/Step 2)과 사건(cases) 페이지가 제 역할을 한다.
3. **정답을 테이블에서 계산할 수 있다.** 찬성 수, 찬성한 의원, 대표발의자, 선거구는 모두 원본 테이블에 있는 사실이다. 그래서 질문 226개의 정답을 사람이 쓰지 않고 계산으로 만들었고, 자동으로 채점할 수 있다.
4. **규모가 적당하다.** 문서 154개를 구축하는 데 약 80분, API 비용 약 $0.7(추정)이 든다. 시연 전날 준비할 수 있고, 다시 만드는 것도 부담이 없다.
5. **사건 하나를 통째로 "새 소식"으로 쓸 수 있다.** 최근 사건인 "2026년 7~9월 지방선거 투표용지 부족 사태 특검"을 초기 구축에서 통째로 빼 두었다가, 시연에서 추가한다. 운영 중인 위키에 새 소식이 들어오는 상황을 재현하는 것이다.
   - 날짜로 자른 것이 아니라 의안명의 "지방선거"로 골랐다. 그래서 초기 세트에도 같은 시기의 다른 특검법 문서가 있다. 예를 들어 2026-09-22와 10-13에 발의된 법안, 같은 날(9/17) 있었던 다른 표결이 그렇다.

   이 클러스터를 고른 이유는 세 가지다.
   - 다른 특검법과 겹치지 않는 독립된 사건이라, 초기 위키에는 이 내용이 전혀 없다. 그래서 추가하기 전에는 관련 질문에 답할 수 없다.
   - 법안, 표결, 본회의가 모두 있어서 한 번의 추가로 여러 종류의 페이지가 바뀐다.
   - 대표발의자가 기존 의원이라 "기존 페이지 갱신"을 보여줄 수 있다.

---

## 2. 시연 구성 한눈에

논문의 LLM-Wiki가 가진 네 가지 기능을 차례로 보여준다: **구축 → 검색 → 데이터 추가 → Error Book(자기교정)**.

| 순서 | 단계 | 보여줄 것 | 방식 | 시간 |
|---|---|---|---|---|
| 0 | 도입 | 논문의 아이디어, 시연 데이터를 고른 방법과 이유 | 설명 | 3분 |
| 1 | raw → 문서 | 정형 테이블을 문서로 바꾼 결과 | 파일 보기 | 2분 |
| 2 | 구축 결과 | 위키 구조, Step 1/Step 2 로그, 그래프 | 미리 구축한 결과 | 4분 |
| 3 | 검색 | LLM 없는 검색과 에이전트 탐색 비교 | 라이브 | 4분 |
| 4 | Error Book ① | 결함 3개 심기 → 기록 → 주입될 제약 | 라이브 (1초 미만) | 2분 |
| 5 | 데이터 추가 | 새 문서 5개 → 기존 페이지 갱신, 제약 주입, 수리 | 라이브 (2분 30초~4분 대기) | 5분 |
| 6 | Error Book ② + 결합 질문 | 2회 연속 통과 → 종료, 새·기존 데이터를 잇는 질문 | 라이브 | 3분 |
| 7 | 정리 | 원래 상태로 복구 | 라이브 | 1분 |

- **합계:** 약 24분, 질의응답 제외.
- **API 비용:** 1회 시연에 약 $0.05~0.1로 추정한다. 리허설 1회가 약 $0.06이었다.

### 왜 이 순서인가

1. **논문의 흐름을 따른다.** 문서를 위키로 컴파일하고(구축), 에이전트가 위키를 탐색해 답하고(검색), 새 데이터가 들어오면 위키가 스스로 갱신되고 교정된다(추가와 Error Book).
2. **구축은 미리 해 둔다.** 문서 154개를 구축하는 데 약 80분이 걸린다. 현장에서는 결과와 로그만 보여준다.
3. **검색을 추가보다 먼저 한다.** 먼저 기존 데이터만으로 답하는 질문을 보여준다. 추가가 끝난 뒤에는 새 데이터와 기존 데이터를 이어야 답할 수 있는 질문을 던져서 차이를 보여준다.
4. **결함을 추가 전에 심는다.** Error Book의 핵심은 "기록한 오류를 다음 생성 프롬프트에 제약으로 넣는 것"이다. 결함을 먼저 기록해 두면 추가를 한 번(2분 30초~4분)만 돌려도 세 가지를 한꺼번에 보여줄 수 있다.
   - 제약이 프롬프트에 주입되는 장면
   - 기존 페이지가 갱신되는 장면
   - 결함이 수리되는 장면

   처음 계획은 "추가 → Error Book" 순서였다. 리허설 대본을 만들면서 이렇게 바꿨다.
5. **추가가 끝난 뒤 lint를 한 번 더 돌린다.** Error Book 항목은 lint를 2회 연속 깨끗하게 통과해야 닫힌다. 추가의 마지막 lint가 첫 번째 통과이고, 이 lint가 두 번째 통과다.
6. **결합 질문으로 끝낸다.** 새로 추가된 페이지에서 링크를 따라 기존 페이지까지 가야 답이 나오는 질문이다. 위키가 실제로 확장됐다는 증거로 시연을 마무리한다.
7. **라이브 단계는 모두 스냅샷으로 되돌릴 수 있다.** 같은 시연을 몇 번이든 반복할 수 있다.

---

## 3. 준비: git clone부터 시연 직전까지

레포에는 시연 기준 위키가 `built` 스냅샷으로 들어 있다(`.snapshots/assembly_spc/built/`). 스냅샷에는 위키, 입력 문서 154개, ingest 캐시, purpose 파일이 함께 들어 있다. 그래서 다시 구축하지 않고 클론만으로 시연할 수 있다.

### 3-1. 준비물

| 항목 | 쓰는 곳 |
|---|---|
| git, make, Python 3.10 이상 | 전부 |
| OpenAI API 키 (`gpt-6-luna`를 쓸 수 있는 키) | `ask`(에이전트 질의)와 데이터 추가. `search`, `lint`, Error Book 기록은 키 없이도 된다 |
| Node 22 이상, npm 10.9.2 이상 | (선택) 로컬 Quartz 사이트 |
| Obsidian | (선택) 위키 폴더를 그래프로 보기 |

### 3-2. 클론과 설치 (처음 한 번, 1분 안팎)

```bash
git clone https://github.com/hyeongrae-kim/LLM-Wiki.git
cd LLM-Wiki
make setup          # .venv 생성, 패키지 설치, .env 생성
```

- 편집기로 `.env`를 열어 `OPENAI_API_KEY=sk-replace-me`를 자기 키로 바꾼다.
- 나머지 설정(모델 `gpt-6-luna`, `WIKI_LANG=ko` 등)은 이 위키를 만들 때와 같다. 그대로 둔다.
- 시스템 `python3`가 3.10보다 낮으면 `make setup PY=python3.12`처럼 버전을 지정한다.

### 3-3. 시연 기준본 복원

```bash
make demo-reset     # built 스냅샷 → wiki_output/(위키), raw/(입력 문서), 캐시, purpose
make status
```

`make status`의 기대 출력은 다음과 같다.

```
   knowledge pages: 179 (bills 78, votes 21, members 38, parties 4, committees 3, cases 21, meetings 14)
   source digests : 154
   error book     : 0 open / 1 closed
```

- `wiki_output/`과 `raw/`는 git에서 제외된 작업 폴더다. 시연하면서 위키가 바뀌어도 git 상태는 깨끗하게 남는다.
- 시연을 시작하기 전과 끝난 뒤에 항상 `make demo-reset`을 실행한다.

### 3-4. 동작 확인 (시연 30분 전)

```bash
make search Q="순직 해병"   # LLM 없이 실행. 1위: cases/순직-해병-수사-방해-및-사건-은폐-의혹
make ask                   # API 키 확인. 답: 안철수 (10~20초)
```

- `make ask`에서 답이 나오면 키와 네트워크가 정상이다.
- `ask`는 위키를 바꾸지 않는다. 확인 후 따로 복구할 필요가 없다.
- `.env`는 화면에 띄우지 않는다. 키가 노출된다.

### 3-5. (선택) 로컬 사이트와 Obsidian

```bash
make site PORT=8090   # http://localhost:8090. 처음 실행할 때 Quartz를 .quartz/에 설치한다
```

- 처음 실행할 때 Quartz 설치와 첫 빌드에 2~3분이 걸린다. `Started a Quartz server listening at …`이 보이면 준비된 것이다.

- 기본 포트는 8080이다. 다른 프로그램이 쓰고 있으면 위처럼 다른 포트를 지정한다.
- 설치 없이 보려면 배포 사이트 https://hyeongrae-kim.github.io/LLM-Wiki/ 를 쓴다. 내용은 `built` 상태와 같다.
- **Obsidian:** "Open folder as vault"로 `wiki_output/assembly_spc/wiki`를 열고 그래프 뷰를 띄운다. 파일이 바뀌면 바로 반영된다.

### 3-6. 화면 배치

| 창 | 내용 |
|---|---|
| 터미널 ① | 명령 실행용. 글자를 크게 키운다 |
| 터미널 ② | `tail -F wiki_output/assembly_spc/wiki/log.md`: 추가·lint·Error Book 이벤트가 실시간으로 쌓인다. 복원하면 파일이 새로 만들어지므로 `-f`가 아니라 `-F`를 쓴다 |
| 터미널 ③ | (선택) `make site PORT=8090` |
| 브라우저 | 배포 사이트 또는 localhost:8090 |
| Obsidian | (선택) 위키 vault와 그래프 뷰 |

- **브라우저 탭:** 홈(그래프), `bills/의안-2206292`, `members/김용민`, `error-book`을 미리 열어 둔다.
- **사이트별 반영 범위:** 배포 사이트는 `built` 상태로 고정돼 있다. 로컬 사이트(`make site`)는 시작할 때 위키를 한 번만 복사한다. 그래서 추가 후의 변화는 **Obsidian**에서 보여주는 것이 가장 편하다.

### 3-7. (선택) 위키를 직접 다시 구축하기

시연에는 필요 없다. 같은 과정을 처음부터 돌려 보고 싶을 때만 한다. 약 80분이 걸리고 API 비용은 약 $0.7이다.

```bash
make clean-wiki             # 작업 중인 위키, 복사된 입력 문서, 캐시를 지운다 (스냅샷은 남는다)
make prepare PRESET=full    # 예제 문서 154개 → raw/assembly_spc/articles, purpose·page_types 배치
make build                  # 구축이 끝나면 built 스냅샷을 새 위키로 덮어쓴다
```

- 빨리 해 보려면 `make quickstart`를 쓴다. 문서 27개로 약 20분 걸리고, 결과는 `small` 스냅샷으로 저장한다. 레포의 `built` 기준본은 건드리지 않는다.
- LLM 출력은 매번 달라진다. 그래서 다시 구축한 위키로 시연하면 페이지 수나 결함을 심는 대상이 이 문서의 실측값과 다르게 나온다.
- 덮어쓴 스냅샷은 git에서 변경으로 보인다. 레포의 기준본으로 돌아가려면 다음을 실행한다.
  ```bash
  git checkout -- .snapshots/assembly_spc/built
  git clean -fdq .snapshots/assembly_spc/built
  make demo-reset
  ```
- 구축 로그는 터미널에만 출력된다. 이 문서가 인용하는 로그는 [docs/logs/build-v2.log](logs/build-v2.log)에 있다.

---

## 4. 진행 대본

### 0. 도입 (3분)

- **논문:** *Retrieval as Reasoning* (arXiv 2605.25480). 검색을 한 번의 조회가 아니라 **추론 과정**으로 본다.
  - 문서를 서로 링크된 위키로 컴파일한다.
  - 에이전트가 `wiki_search`와 `wiki_read`를 조합해 링크를 따라가며 답을 찾는다.
  - Error Book이 위키의 품질 문제를 기록하고, 다음 생성 때 제약으로 넣어 스스로 교정한다.
- **카파시 LLM Wiki와의 관계:** 3층 구조(raw → wiki → schema)와 ingest·query·lint라는 뼈대는 같다.
  - 다른 점은 세 가지다. 사람이 아니라 에이전트가 읽도록 설계했고, 코드로 자동화했고, 벤치마크로 검증했다.
- **이번 시연:** 원본 코드는 영어 벤치마크 전용이었다. 이를 한국어와 22대 국회 데이터(약 2GB)로 돌아가도록 고쳤다.
- **시연 데이터 (1분, §1 요약):**
  - 2GB를 전부 위키로 만들면 의안만 약 190시간이 걸린다. 그래서 주제 하나로 잘랐다.
  - 의안명에 "특별검사"가 들어간 법안 85건을 먼저 골랐다. 그 법안의 표결 23건, 대표발의자 42명, 표결이 있었던 본회의 14건을 따라가며 함께 골랐다.
  - 이것을 문서로 만들어 초기 구축에 154개를 썼다. 최근 사건인 "지방선거 투표용지 특검" 문서 5개는 시연 중에 추가하려고 남겨 두었다.
  - 이 주제를 고른 이유는 세 가지다. 링크를 따라가야 답이 나오는 질문이 많고, 같은 사건이 여러 법안·표결에 반복되고, 정답을 테이블에서 계산할 수 있다.

### 1. raw → 문서 (2분)

```bash
ls examples/assembly_spc/articles | head   # 변환된 문서: bill-, vote-, member-, meeting-
sed -n 1,45p examples/assembly_spc/articles/vote-1627.md
```

- **원천 데이터:** CSV/JSON 테이블이다. 규모는 §1의 표와 같다. 원본(약 2GB)은 레포에 없고, 변환된 문서만 `examples/`에 있다.
- **변환:** 표결 문서 하나는 표결 1건에 대한 의원별 기록 150~290건을 정당별 집계와 명단으로 묶은 것이다. 표가 문서로 바뀐 모습을 보여준다.
- **짚을 것:** 표결 문서의 `## 정당별 표결`과 `## 정당 내 소수 의견 투표자`(`- 안철수 (국민의힘): 찬성`). 이 줄이 3단계 질문의 정답 근거다.

### 2. 구축 결과 (4분)

```bash
make status
sed -n 1,40p wiki_output/assembly_spc/wiki/index.md
sed -n '/Batch 9\/77/,/Batch done/p' docs/logs/build-v2.log   # 구축 로그 중 배치 하나
```

- **구축 로그:** `docs/logs/build-v2.log`는 이 위키를 만들 때 남긴 로그다.
  - 처음 60개 문서를 처리하다 중단했고, 같은 명령으로 이어서 끝냈다.
  - 배치 9에는 Step 1이 고른 기존 법안 페이지 7개, Error Book 제약 주입, Step 2가 쓴 파일 6개가 차례로 나온다.
- **2단계 구축**
  - Step 1 `🔍 Selected N pages`: 새 문서와 관련된 기존 페이지를 고른다.
  - Step 2 `📄 Written …`: 고른 페이지를 새로 쓰거나 기존 내용과 병합한다.
  - 구축 중에도 Error Book 제약이 주입된다: `📔 Error Book: injecting 1 active constraint(s)`.
- **결과:** 지식 페이지 179개와 출처 요약(digest) 154개, lint 이슈 0건.
- **페이지 구조:** 브라우저에서 `bills/의안-2206292`를 열고 차례로 짚는다.
  - 한 줄 요약(`>`)
  - Key Facts
  - Related Pages(다른 페이지로 가는 링크)
  - Related Sources(근거 digest)
- **그래프:** 홈 그래프나 Obsidian 그래프에서 의원·법안·표결·사건 페이지가 서로 연결된 구조를 보여준다.
- **(질문이 나오면) 두 번 구축한 이유:** 원본 코드의 버그 때문이다. v1에서는 페이지를 갱신할 때 기존 출처가 사라졌다. 그래서 근거 검증이 엉뚱한 문서와 사실을 대조했고, 정상 사실 250개를 지웠다. 이 버그를 고친 v2에서는 지워진 사실이 32개로 줄었다. 같은 38문항은 두 버전 모두 정답을 냈다.

### 3. 검색 (4분, 라이브)

```bash
make search Q="순직 해병"
```

- LLM 없이 점수만으로 검색한다. 이름·별칭·태그가 맞는 페이지를 앞에 놓고, 그다음 한글 BM25로 점수를 매긴다.
- 1위는 `cases/순직-해병-수사-방해-및-사건-은폐-의혹`이다. 그 아래는 관련 법안과 표결의 digest가 차지한다.
- 이 검색만으로는 "누가 찬성했는가"를 알 수 없다. 에이전트가 필요한 이유가 여기에 있다.

```bash
make ask     # 기본 질문: 순직 해병 특검법 첫 본회의 표결에서 국민의힘 소속으로 찬성한 의원은?
```

2026-10-26 새 클론에서 실행한 출력은 다음과 같다 (16초, 도구 호출 3회). trace는 실행할 때마다 조금씩 달라진다.

```
🧭 Retrieval trace
    1. search "순직 해병 특검법 첫 본회의 표결" → 5 results (top: 표결-957, 표결-1590, …)
    2. read: 표결-1627, 표결-1590, 표결-957
    3. read: 표결-1627-2024-07-04-…, 표결-957-2025-06-05-…
🔧 Tool calls: 3
💬 안철수
```

- **짚을 것:** 에이전트는 순직 해병 특검법 표결 세 건(2024-07-04, 2024-09-19, 2025-06-05)을 함께 읽고 날짜를 비교한다. 그래서 "첫" 표결을 골라낸다. 검색 자체가 추론 과정이라는 논문의 주장을 보여주는 장면이다.

```bash
make ask Q="의안번호 2206292 김건희 특검법을 대표발의한 의원의 선거구는?"
```

```
    1. search "2206292" → 5 results (top: 의안-2206292-…, 의안-2206292, 표결-1345)
    2. read: 의안-2206292
    3. search "김용민" → 5 results (top: 김용민, …)
    4. read: 김용민
🔧 Tool calls: 4
💬 경기 남양주시병
```

- 두 페이지를 거쳐야 하는 질문이다: 법안 페이지 → 대표발의자 김용민 → 의원 페이지.
- 정답은 **경기 남양주시병**이다. 10~25초가 걸리고, 도구는 2~5회 호출한다 (위 출력은 24초).

### 4. Error Book ① 결함 심기와 기록 (2분, 라이브)

```bash
make demo-errorbook   # 결함 심기 → lint로 기록 → 주입될 제약 보기
```

2026-10-26 실측 출력을 요약하면 다음과 같다 (1초 미만).

```
  ① broken link   : [[members/한지아]] added to bills/의안-2206292.md (no such page yet)
  ② missing summary: removed the '> …' line of members/강득구.md
  ③ wrong directory: moved bills/의안-2200005.md → votes/ (type: bills)
  📔 Error E01 reappeared, reopened
  📔 New error E02: Type-path mismatch: frontmatter type field doesn't match directory name (1 issues)
  📔 New error E03: Knowledge page missing one-sentence summary: no > blockquote after # title (1 issues)
  📔 Error Book (3 active / 0 closed)
...
Constraints injected into the next Step 2 prompt:

## Known Issues (must avoid)

- [E01] 1 broken links still active (e.g., 의안-2206292 → [[members/한지아]])
- [E02] Each page's frontmatter `type` field must match its directory name exactly
- [E03] Every knowledge page must have a > one-sentence summary (blockquote) immediately after the # title line
```

- **결함 3개**
  - ① 깨진 링크: 실제 의원이지만 아직 페이지가 없는 한지아에게 링크를 건다.
  - ② 한 줄 요약 누락: 의원 페이지의 요약 줄을 지운다.
  - ③ 잘못된 디렉터리: 법안 페이지를 votes/로 옮긴다. frontmatter의 `type`은 bills 그대로 둔다.
- **E01이 "reopened"로 나오는 이유:** 구축 중에 깨진 링크가 이미 E01로 기록됐다가 닫혔다. 같은 유형이 다시 나타나면 새 항목을 만들지 않고 기존 항목을 다시 연다.
- **짚을 것:** 마지막 `## Known Issues` 블록이 다음 Step 2 프롬프트에 그대로 들어간다.
- 실행하기 전에 `before-inject` 스냅샷이 자동으로 저장된다.

### 5. 데이터 추가 (5분, 라이브)

```bash
make demo-add   # 2026년 7~9월 '지방선거 투표용지 부족 사태' 특검 문서 5개
```

- **추가 문서:** `examples/assembly_spc/add/`의 5개다.
  - 법안 2개: 2220309 대안, 2221376 개정안
  - 표결 2개: 2026-07-30, 2026-09-17
  - 회의록 1개: 제439회 정기회 제9차 본회의
- **진행:** 2개씩 3배치로 처리한다. 전체는 2분 30초~4분이다 (리허설 4분 11초, 2026-10-26 새 클론 2분 30초).
- **(선택) 프롬프트 증거 남기기:** `WIKI_DUMP_PROMPTS=1 make demo-add`로 실행하면 실제 프롬프트가 `wiki_output/assembly_spc/logs/prompts/`에 저장된다.

화면에 나오는 순서와 짚을 내용은 다음과 같다 (리허설 로그 기준).

| 로그 | 짚을 내용 |
|---|---|
| `📋 Batch ingestion \| Total: 5 \| Batch size: 2` | 문서 5개를 3배치로 처리한다 |
| `🔍 Selected 3 pages: ['김용민', '법제사법위원회', '제439회-국회-정기회-제9차-본회의']` | Step 1이 **기존** 페이지를 고른다. 김용민은 새 법안의 대표발의자다 |
| `📔 Error Book: injecting 3 active constraint(s) into the Step 2 prompt` | 4단계에서 기록한 제약 3개가 새 페이지를 쓰는 프롬프트에 들어간다 |
| `📄 Written wiki/bills/의안-2221376.md`, `📄 Written wiki/members/김용민.md` | 새 법안 페이지를 만들고, 기존 의원 페이지에 새 사실을 병합한다 |
| `📔 Error E02 (type_path_mismatch) not seen for 2 checks, closed` | 배치 사이의 lint에서 코드가 디렉터리를 바로잡았다. 이후 2회 연속 통과해서 E02가 닫혔다 |
| `🏁 Light finalization` → `✅ Created members/한지아`, `📔 Marked 1 missing_summary sample(s) as fixed` | LLM 수리 단계다. 깨진 링크가 가리키던 의원 페이지를 새로 만들고, 지워진 요약을 다시 쓴다 |
| `📔 Error Book (2 active / 1 closed)`, `knowledge pages: 184 (bills 80, votes 23, members 39, …)` | E01과 E03은 `clean checks 1/2` 상태다. 한 번 더 통과하면 닫힌다 |

- **실행마다 달라지는 부분:** 페이지 수는 리허설에서 184개, 2026-10-26 새 클론에서 188개였다.
  - 새 클론에서는 Step 2가 아직 페이지가 없는 같은 사건의 법안 4건(`add_extra`)에 링크를 걸었다.
  - 배치 사이의 lint가 이것을 깨진 링크로 E01에 기록했고, 다음 배치 프롬프트에는 `[E01] 5 broken links still active …`가 주입됐다.
  - 마지막 수리 단계에서 그 법안 페이지 4개와 한지아 페이지를 만들었다.
  - 이렇게 차이가 나면 오히려 좋은 설명거리가 된다. 시연 중에 Error Book이 실제로 일하는 장면이기 때문이다.

**기다리는 동안 (2~4분) 할 이야기**
- **Step 1/Step 2를 나눈 이유:** 위키 전체를 프롬프트에 넣을 수는 없다. 그래서 먼저 관련 페이지만 고르고, 그 페이지들만 넣어 갱신한다.
- **터미널 ②:** `log.md`에 ingest 이벤트가 쌓이는 모습을 보여준다.
- **Error Book 생명주기:** 탐지 → 기록 → 프롬프트 주입 → 수리 → 2회 연속 통과 → 종료.
- **Obsidian:** `members/김용민`이 갱신되는 순간을 보여준다.

추가가 끝나면 갱신 전후를 비교한다.

```bash
diff .snapshots/assembly_spc/built/wiki/members/김용민.md wiki_output/assembly_spc/wiki/members/김용민.md
tail -20 wiki_output/assembly_spc/wiki/log.md
# 프롬프트를 저장했다면: 주입된 제약이 실제 프롬프트에 들어 있는지 확인
grep -A4 "Known Issues" "$(ls -t wiki_output/assembly_spc/logs/prompts/*step2* | head -1)"
```

### 6. Error Book ② 종료 확인과 결합 질문 (3분, 라이브)

```bash
.venv/bin/llm-wiki lint --corpus assembly_spc
.venv/bin/llm-wiki errorbook --corpus assembly_spc export
```

- **기대 출력:**
  - `📔 Error E01 (broken_link) not seen for 2 checks, closed`
  - `📔 Error E03 (missing_summary) not seen for 2 checks, closed`
  - 최종 상태: `Error Book (0 active / 3 closed)`
- **Error Book 열어 보기:** Obsidian에서 `error-book.md`를 연다. 활성·종료 항목, 남은 제약, 수리 이력(`lint_ledger.jsonl`)을 차례로 보여준다.

```bash
make ask Q="의안번호 2221376 투표용지 부족 사태 특검법 개정안을 대표발의한 의원이 현재 소속된 상임위원회는?"
```

리허설과 2026-10-26 새 클론 모두 같은 경로로 답했다. 도구 호출은 3회였고, 시간은 8.5초와 12.6초였다.
1. `search "2221376"`
2. `read 의안-2221376`: 방금 추가된 페이지
3. `read 김용민`: 링크를 따라간 기존 페이지
4. 답: **법제사법위원회**

- **짚을 것:** 2221376은 방금 추가한 데이터에만 있다. 상임위원회 정보는 기존 의원 페이지에만 있다. 두 데이터가 링크로 이어져 있어서 답이 나온다.

### 7. 정리 (1분)

```bash
make demo-reset   # "built" 스냅샷으로 복원
make status       # 179 pages, error book 0 open / 1 closed 확인
```

- 터미널 ②의 `tail -F`는 복원된 `log.md`를 자동으로 다시 따라간다.
- 로컬 사이트를 계속 쓸 거라면 터미널 ③에서 `make site PORT=8090`을 다시 실행한다.
- `git status`를 보면 변경이 없다. 시연은 git에서 제외된 `wiki_output/`과 `raw/`만 바꾼다.

---

## 5. 시간 조절

**10분 버전:** 0 도입 → 2 구축 결과(사이트만) → 3 검색(`make ask` 1개) → 4 → 5 → 6.

**시간이 남을 때**

| 명령 | 내용 | 시간 |
|---|---|---|
| `make eval` | 기존 데이터 질문(`stage: initial`) 10개를 풀고, 테이블에서 계산한 정답과 비교해 채점한다 | 약 2분. 2026-10-26 새 클론에서 10/10 |
| `.venv/bin/llm-wiki add --corpus assembly_spc examples/assembly_spc/add_extra/*.md` | 같은 사건의 문서를 더 추가한다. 표결까지 가지 않은 법안 5개, 의원 4명이다 | 리허설 안 함. 5배치라 약 4~7분 예상 |
| `make demo-errorbook` → `make demo-fix` | 데이터를 추가하지 않고 Error Book만 보여준다: 결함 심기 → 코드 수리 + LLM 수리 → lint 2회 → E01~E03 모두 closed | 약 10초 (2026-10-26 새 클론) |

---

## 6. 문제가 생겼을 때

| 상황 | 대응 |
|---|---|
| `make setup` 실패 | `python3 --version`이 3.10 이상인지 확인한다. 낮으면 `make setup PY=python3.12`처럼 지정한다 |
| `❌ No snapshot at …/built` | 레포 루트에서 실행했는지 확인한다. `ls .snapshots/assembly_spc/built`에 `wiki/`가 보여야 한다 |
| `make demo-add` 중 API 오류가 나거나 멈춤 | Ctrl-C → `make demo-reset` → `make demo-errorbook` → `make demo-add` 순으로 다시 한다. 시간이 없으면 리허설 로그로 설명한다: `sed -n 1,110p docs/logs/rehearsal-demo-add.log` |
| 4xx 오류 (키·모델 문제) | 재시도하지 않고 즉시 원인 메시지를 낸다. `status=401`이면 키가 틀린 것이고, 모델 오류면 키가 `gpt-6-luna`를 쓸 수 있는지 확인한다. `.env`는 화면 밖에서 연다 |
| `ask`가 틀리거나 느림 | `-v` trace로 어디서 빗나갔는지 설명한다. 그다음 같은 질문을 다시 하거나, `make search`로 근거 페이지를 보여준다 |
| 심은 결함만 되돌리기 | `.venv/bin/llm-wiki restore --corpus assembly_spc --name before-inject` |
| 처음 상태로 되돌리기 | `make demo-reset` |
| 포트가 이미 사용 중 | `make site PORT=8090`처럼 다른 포트를 지정한다 |
| `make site`에서 Node·npm 버전 오류 | Node 22 이상, npm 10.9.2 이상이 필요하다 (`npm install -g npm@latest`). 설치가 어렵다면 배포 사이트를 쓴다 |
| 로컬 사이트에 추가 결과가 안 보임 | 정상이다. `make site`는 시작할 때만 위키를 복사한다. 다시 실행하거나 Obsidian으로 보여준다 |
| 배포 사이트에 추가 결과가 없음 | 정상이다. 배포 사이트는 `built` 상태로 고정돼 있다. 갱신하려면 `make deploy-pages`를 실행해야 하는데, 외부에 공개되는 작업이니 시연 중에는 하지 않는다 |
| `tail`이 더 이상 갱신되지 않음 | `tail -f`로 띄운 경우다. 복원이 파일을 새로 만들기 때문이다. `tail -F`로 다시 띄운다 |

---

## 7. 참고

### 예상 질문과 정답

정답은 `examples/assembly_spc/questions.jsonl`(226문항)에서 가져왔다. 이 파일의 정답은 원천 테이블에서 계산한 값이다.

| 질문 | 정답 | 필요한 데이터 |
|---|---|---|
| 순직 해병 특검법 첫 본회의 표결(2024-07-04)에서 국민의힘 소속으로 찬성한 의원은? | 안철수 | 기존 |
| 내란·외환 특검법 본회의 표결(2025-01-17)에서 국민의힘 소속으로 찬성한 의원은? | 안철수 | 기존 |
| 의안번호 2206292 김건희 특검법을 대표발의한 의원과 소속 정당은? | 김용민, 더불어민주당 | 기존 |
| 의안번호 2206292를 대표발의한 의원의 선거구는? (2단계) | 경기 남양주시병 | 기존 |
| 의안번호 2206292에 대한 대통령 재의요구 이후 재의결 결과는? | 부결 | 기존 |
| 의안번호 2220309 대안의 본회의 표결(2026-07-30)에서 찬성한 의원 수는? | 226명 | 추가 후 |
| 의안번호 2221376 개정안의 본회의 표결(2026-09-17)에서 찬성한 의원 수는? | 151명 | 추가 후 |
| 의안번호 2221376을 대표발의한 의원이 현재 소속된 상임위원회는? (2단계) | 법제사법위원회 | 추가 후 + 기존 |

### 파일 위치

| 무엇 | 경로 |
|---|---|
| 추가용 문서 | `examples/assembly_spc/add/` (5개), `examples/assembly_spc/add_extra/` (9개) |
| 위키 (Obsidian vault) | `wiki_output/assembly_spc/wiki/` |
| Error Book 원본 / 표 | `wiki/error_book.yaml` / `wiki/error-book.md` |
| 수리 이력 / 이벤트 로그 | `wiki/lint_ledger.jsonl` / `wiki/log.md` |
| 시연 기준본 (git에 포함) | `.snapshots/assembly_spc/built/`: `wiki/`, `articles/`, `cache.json`, `purpose.md` |
| 결함 심기 직전 상태 (로컬에서 생성) | `.snapshots/assembly_spc/before-inject/` |
| 구축 로그 / 리허설 로그 | [docs/logs/build-v2.log](logs/build-v2.log) / [docs/logs/rehearsal-demo-add.log](logs/rehearsal-demo-add.log) |
| 저장된 프롬프트 | `wiki_output/assembly_spc/logs/prompts/` |
