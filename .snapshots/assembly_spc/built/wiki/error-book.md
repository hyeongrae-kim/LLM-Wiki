---
type: meta
tags: [error-book]
---
# Error Book
> 위키 품질 자기교정 기록: 탐지 → 기록 → 프롬프트 제약 주입 → 수리 → 재검증(2회) → 종료

갱신 2026-10-24 01:24 · 활성 0건 · 종료 1건

## 활성 항목

| ID | 유형 | 상태 | 남은 샘플 | 발견 | 최근 확인 | 연속 통과 |
|---|---|---|---|---|---|---|

## 종료된 항목

| ID | 유형 | 발견 | 종료 |
|---|---|---|---|
| E01 | 깨진 링크 | 2026-10-23 | 2026-10-24 |

## 다음 Step 2 프롬프트에 주입되는 제약

```text
(none)
```

## 최근 수리 이력 (lint_ledger.jsonl)

| 시각 | 유형 | 방식 | 파일 | 건수 | 메모 |
|---|---|---|---|---|---|
| 2026-10-24T01:24 | broken_link | 코드 · drop_invented_digest_link | committees/법제사법위원회 | 1 | Related Sources linked a digest that does not exist |
| 2026-10-24T01:23 | cross_page_contradiction | LLM · llm_detect_contradictions | votes/표결-1217 | 1 | Fixed contradiction: '제421회 국회 임시회 제1차 본회의에서 진행됐으며, 회의 안건표는 원안가결로 요약한다. 기존 의안 기록 |
| 2026-10-24T01:22 | unsupported_facts | LLM · llm_verify_source_grounding | cases/국정기획위원-차명계좌-불공정거래-의혹 | 1 | Removed 1 unsupported facts |
| 2026-10-24T01:22 | grounding_skipped | LLM · llm_verify_source_grounding | committees/국토교통위원회 | 0 | 3/4 facts flagged; evidence mismatch, kept |
| 2026-10-24T01:21 | grounding_skipped | LLM · llm_verify_source_grounding | bills/의안-2212283 | 0 | 4/5 facts flagged; evidence mismatch, kept |
| 2026-10-24T01:20 | unsupported_facts | LLM · llm_verify_source_grounding | committees/법제사법위원회 | 4 | Removed 4 unsupported facts |
| 2026-10-24T01:19 | unsupported_facts | LLM · llm_verify_source_grounding | members/김승원 | 1 | Removed 1 unsupported facts |
| 2026-10-24T01:19 | unsupported_facts | LLM · llm_verify_source_grounding | bills/의안-2212281 | 1 | Removed 1 unsupported facts |
| 2026-10-24T01:18 | cross_page_contradiction | LLM · llm_detect_contradictions | bills/의안-2217766 | 1 | Fixed contradiction: '파견공무원 상한을 130명에서 150명으로 확대하고, 변호사 자격 특별수사관과 파견 군검사의 공소유지 권 |
| 2026-10-24T01:18 | unsupported_facts | LLM · llm_verify_source_grounding | bills/의안-2215551 | 1 | Removed 1 unsupported facts |
| 2026-10-24T01:18 | unsupported_facts | LLM · llm_verify_source_grounding | members/전용기 | 1 | Removed 1 unsupported facts |
| 2026-10-24T01:18 | unsupported_facts | LLM · llm_verify_source_grounding | members/김병기 | 1 | Removed 1 unsupported facts |
| 2026-10-24T01:14 | unsupported_facts | LLM · llm_verify_source_grounding | members/박찬대 | 1 | Removed 1 unsupported facts |
| 2026-10-24T01:13 | unsupported_facts | LLM · llm_verify_source_grounding | bills/의안-2206291 | 1 | Removed 1 unsupported facts |
| 2026-10-24T01:12 | unsupported_facts | LLM · llm_verify_source_grounding | bills/의안-2204851 | 1 | Removed 1 unsupported facts |
| 2026-10-24T01:12 | unsupported_facts | LLM · llm_verify_source_grounding | members/박준태 | 2 | Removed 2 unsupported facts |
| 2026-10-24T01:11 | unsupported_facts | LLM · llm_verify_source_grounding | members/신동욱 | 1 | Removed 1 unsupported facts |
| 2026-10-24T01:11 | unsupported_facts | LLM · llm_verify_source_grounding | meetings/제421회-국회-임시회-제1차-본회의 | 1 | Removed 1 unsupported facts |
| 2026-10-24T01:11 | unsupported_facts | LLM · llm_verify_source_grounding | members/이성윤 | 1 | Removed 1 unsupported facts |
| 2026-10-24T01:10 | unsupported_facts | LLM · llm_verify_source_grounding | votes/표결-27492 | 1 | Removed 1 unsupported facts |
| 2026-10-24T01:09 | related_source_format | 코드 · auto_fix_related_source_text |  | 2 |  |
| 2026-10-24T01:02 | broken_link | 코드 · auto_fix_broken_links |  | 1 |  |
| 2026-10-24T01:01 | broken_link | 코드 · auto_fix_broken_links |  | 1 |  |
| 2026-10-24T00:59 | broken_link | 코드 · auto_fix_broken_links |  | 2 |  |
| 2026-10-24T00:58 | related_source_format | 코드 · auto_fix_related_source_text |  | 1 |  |
| 2026-10-24T00:58 | broken_link | 코드 · auto_fix_broken_links |  | 1 |  |
| 2026-10-24T00:57 | cross_page_contradiction | LLM · llm_detect_contradictions | parties/조국혁신당 | 1 | Fixed contradiction: '- 조국혁신당 소속 국회의원: [[members/김선민]], [[members/박은정]], [[membe |
| 2026-10-24T00:57 | unsupported_facts | LLM · llm_verify_source_grounding | cases/김건희-주가조작-및-가족-비위-의혹 | 3 | Removed 3 unsupported facts |
| 2026-10-24T00:55 | unsupported_facts | LLM · llm_verify_source_grounding | parties/조국혁신당 | 2 | Removed 2 unsupported facts |
| 2026-10-24T00:55 | unsupported_facts | LLM · llm_verify_source_grounding | bills/의안-2209631 | 1 | Removed 1 unsupported facts |
