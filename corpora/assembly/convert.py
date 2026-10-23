#!/usr/bin/env python3
"""Convert Korean National Assembly (22대 국회) tables into LLM-Wiki articles.

The LLM-Wiki pipeline ingests *documents* (one Markdown file per source). This
script turns the structured tables under ``raw/`` into such documents for one
topic (default: bills whose name contains "특별검사"):

    bill-<billcode>.md        의안: 발의자, 공동발의 정당 분포, 처리 결과, 제안이유, 주요내용
    vote-<rollcall_id>.md     본회의 표결: 정당별 찬반, 정당 내 소수 의견 투표자
    member-<member_id>.md     국회의원: 인적 사항, 정당·위원회 이력, 이 주제의 대표발의 법안
    meeting-<minute_id>-N.md  본회의 회의록: 안건, 관련 표결, 관련 발언 발췌

Output (``--out``, default ``examples/assembly_spc``):

    articles/        initial build set
    add/             live "add data" set: the cluster matching --add-keyword that
                     reached a plenary vote, plus the meeting where it was voted
    add_extra/       the rest of that cluster (proposals that never reached a vote)
    manifest.json    file lists per set, plus a small preset for a quick build
    questions.jsonl  questions with gold answers computed from the tables

Expected input (CSV, UTF-8 with or without BOM):

    raw/bills/bills.csv, raw/bills/bill_sponsors.csv
    raw/votes/rollcalls.csv, raw/votes/rollcall_records.csv
    raw/members/members.csv, member_party_timeline.csv, member_committees.csv
    raw/minutes/minutes.csv, raw/minutes/speeches.jsonl

Usage:

    python corpora/assembly/convert.py --raw raw --keyword 특별검사 --add-keyword 지방선거
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

csv.field_size_limit(sys.maxsize)

MAX_DOC_CHARS = 6000          # per article; the ingest prompt truncates longer ones
MAX_REASON_CHARS = 1500
MAX_DETAIL_CHARS = 2500
MAX_CAREER_CHARS = 800
MAX_SPEECH_CHARS = 500
MAX_SPEECHES_PER_MEETING = 12
MAX_AGENDA_ITEMS = 40
CHAIR_POSITIONS = {"의장", "부의장", "의장직무대행", "사무총장", "의사국장"}


# ─── helpers ──────────────────────────────────────────────────────────────

def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "").replace("﻿", "")


def clip(text: str, limit: int) -> str:
    text = nfc(text).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + " …(이하 생략)"


def rows(path: Path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            yield {k: nfc(v) for k, v in row.items()}


def yaml_str(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def doc(source_id: str, source_type: str, title: str, doc_date: str, body: str) -> str:
    fm = [
        "---",
        f"source_id: {source_id}",
        f"source_type: {source_type}",
        f"title: {yaml_str(title)}",
    ]
    if doc_date:
        fm.append(f"date: {doc_date}")
    fm.append("---")
    return "\n".join(fm) + "\n\n" + body.strip() + "\n"


def split_doc(source_id: str, source_type: str, title: str, doc_date: str,
              header: str, blocks: list[str]) -> list[tuple[str, str]]:
    """Split a long document into parts of at most MAX_DOC_CHARS characters."""
    parts: list[list[str]] = [[]]
    size = len(header)
    for block in blocks:
        if parts[-1] and size + len(block) > MAX_DOC_CHARS - 300:
            parts.append([])
            size = len(header)
        parts[-1].append(block)
        size += len(block) + 2
    out = []
    for i, chunk in enumerate(parts, 1):
        suffix = f" ({i}/{len(parts)})" if len(parts) > 1 else ""
        out.append((f"{source_id}-{i}",
                    doc(f"{source_id}-{i}", source_type, title + suffix, doc_date,
                        header + "\n\n" + "\n\n".join(chunk))))
    return out


def party_breakdown(items: list[str]) -> str:
    c = Counter(p or "정당 정보 없음" for p in items)
    return ", ".join(f"{p} {n}명" for p, n in c.most_common())


def short_bill_name(name: str) -> str:
    """Drop the trailing '(…의원 등 N인)' sponsor note."""
    return re.sub(r"\s*\([^()]*(의원|위원장|정부)[^()]*\)\s*$", "", name).strip() or name


# ─── loading ──────────────────────────────────────────────────────────────

def load(raw: Path, keyword: str) -> dict:
    print(f"Loading bills matching '{keyword}' ...")
    bills = {r["billcode"]: r for r in rows(raw / "bills/bills.csv") if keyword in r["bill_name"]}
    codes = set(bills)

    sponsors = defaultdict(list)
    for r in rows(raw / "bills/bill_sponsors.csv"):
        if r["billcode"] in codes:
            sponsors[r["billcode"]].append(r)

    rollcalls = {r["rollcall_id"]: r for r in rows(raw / "votes/rollcalls.csv") if r["billcode"] in codes}
    print(f"  bills={len(bills)} rollcalls={len(rollcalls)}")

    records = defaultdict(list)
    for r in rows(raw / "votes/rollcall_records.csv"):
        if r["rollcall_id"] in rollcalls:
            records[r["rollcall_id"]].append(r)

    members = {}
    for r in rows(raw / "members/members.csv"):
        members.setdefault(r["member_id"], r)
        if r["is_primary_code"] == "True":
            members[r["member_id"]] = r
    timeline = defaultdict(list)
    for r in rows(raw / "members/member_party_timeline.csv"):
        timeline[r["member_id"]].append(r)
    committees = defaultdict(list)
    for r in rows(raw / "members/member_committees.csv"):
        committees[r["member_id"]].append(r)

    plenary = [r for r in rows(raw / "minutes/minutes.csv") if r["meeting_kind"] == "본회의"]
    return dict(bills=bills, sponsors=sponsors, rollcalls=rollcalls, records=records,
                members=members, timeline=timeline, committees=committees, plenary=plenary)


def load_speeches(raw: Path, minute_ids: set[str], keyword: str) -> dict[str, list[dict]]:
    """Topic-related, non-procedural utterances for the given meetings."""
    print("Scanning speeches.jsonl (large file) ...")
    out = defaultdict(list)
    with open(raw / "minutes/speeches.jsonl", encoding="utf-8") as f:
        for line in f:
            if not any(mid in line[:40] for mid in minute_ids):
                continue
            s = json.loads(line)
            if s["minute_id"] not in minute_ids or s.get("position") in CHAIR_POSITIONS:
                continue
            text = nfc(s.get("line", ""))
            if keyword in text or "특검" in text:
                out[s["minute_id"]].append(s)
    return out


# ─── document builders ────────────────────────────────────────────────────

def lead_sponsors(data: dict, code: str) -> list[dict]:
    leads = [s for s in data["sponsors"][code] if s["role"] != "공동"]
    return sorted(leads, key=lambda s: int(s["seq"] or 0))


def bill_votes(data: dict, code: str) -> list[dict]:
    return sorted((r for r in data["rollcalls"].values() if r["billcode"] == code),
                  key=lambda r: r["process_date"])


def _val(d: dict, key: str) -> str:
    """A field value, ignoring header text that leaked into the data (e.g. "상정일": "상정일")."""
    v = d.get(key) if isinstance(d, dict) else None
    v = nfc(str(v)) if v not in (None, "") else ""
    return "" if v == key else v


def _dates(d: dict, *keys: str) -> str:
    return ", ".join(f"{k} {_val(d, k)}" for k in keys if _val(d, k))


def bill_detail(b: dict) -> dict:
    try:
        d = json.loads(b["detail"])
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def veto(b: dict) -> dict | None:
    """The presidential re-deliberation request (재의요구) record, if any."""
    plenary = bill_detail(b).get("본회의 심의") or {}
    items = plenary.get("정부재의안") or []
    return items[0] if items else None


def process_lines(b: dict) -> list[str]:
    """Committee / plenary / veto / promulgation history from the bill's detail JSON."""
    d = bill_detail(b)
    out = []
    committee = d.get("위원회 심사") or {}
    for r in committee.get("소관위 심사정보") or []:
        info = _dates(r, "회부일", "상정일", "처리일")
        out.append(f"- 소관위 심사: {_val(r, '소관위원회') or '-'}" + (f" ({info})" if info else "") +
                   (f" → {_val(r, '처리결과')}" if _val(r, "처리결과") else ""))
    for r in committee.get("소위 심사정보") or []:
        info = _dates(r, "회부일", "상정일", "처리일")
        out.append(f"- 소위원회 심사: {_val(r, '소위원회') or '-'}" + (f" ({info})" if info else "") +
                   (f" → {_val(r, '처리결과')}" if _val(r, "처리결과") else ""))
    plenary = d.get("본회의 심의") or {}
    for r in plenary.get("본회의 심의정보") or []:
        info = _dates(r, "상정일", "의결일")
        name = _val(r, "회의명")
        out.append(f"- 본회의 심의: {name or '-'}" + (f" ({info})" if info else "") +
                   (f" → {_val(r, '회의결과')}" if _val(r, "회의결과") else ""))
    for r in (d.get("정부이송") or {}).get("정부이송정보") or []:
        if _val(r, "정부이송일"):
            out.append(f"- 정부 이송: {_val(r, '정부이송일')}")
    for r in plenary.get("정부재의안") or []:
        info = _dates(r, "접수일", "상정일", "재의결일")
        out.append("- 대통령 재의요구(거부권): 정부재의안" + (f" ({info})" if info else "") +
                   (f" → 재의결 결과 {_val(r, '재의처리결과')}" if _val(r, "재의처리결과") else ""))
    for r in (d.get("공포") or {}).get("공포정보") or []:
        out.append(f"- 공포: 법률 제{_val(r, '공포번호')}호 「{_val(r, '공포법률')}」 ({_val(r, '공포일자')})")
    alt = d.get("대안정보") or {}
    main = alt.get("대안") or {}
    folded = [x for k, v in alt.items() if k.startswith("대안반영폐기") for x in (v or [])]
    if main and main.get("billcode") != b["billcode"]:
        out.append(f"- 대안 반영: 이 법안은 의안 {main.get('billcode')} 「{nfc(main.get('bill_name', ''))}」에 반영되어 폐기됨")
    elif main and folded:
        out.append("- 이 대안에 반영되어 폐기된 법안: " + "; ".join(
            f"의안 {x.get('billcode')} 「{nfc(x.get('bill_name', ''))}」" for x in folded))
    note = _val(d.get("부가정보") or {}, "비고")
    if note:
        out.append(f"- 비고: {note}")
    return out


def split_reason(text: str) -> tuple[str, str]:
    """proposal_reason holds both 제안이유 and 주요내용."""
    text = nfc(text).replace("\r\n", "\n")
    m = re.search(r"\n\s*주요내용\s*\n", text)
    reason, main = (text[:m.start()], text[m.end():]) if m else (text, "")
    return re.sub(r"^\s*제안이유\s*", "", reason).strip(), main.strip()


def build_bill(data: dict, code: str) -> str:
    b = data["bills"][code]
    leads = lead_sponsors(data, code)
    co = [s for s in data["sponsors"][code] if s["role"] == "공동"]
    lead_txt = ", ".join(f"{s['name']} ({s['party_at_proposal'] or '정당 정보 없음'})" for s in leads)
    lines = [
        f"# {b['bill_name']}",
        "",
        "## 기본 정보",
        f"- 의안번호: {code}",
        f"- 의안명: {b['bill_name']}",
        f"- 대수: 제{b['daenum']}대 국회",
        f"- 발의일: {b['proposal_date']}",
        f"- 제안자 구분: {b['sponsor_type']}",
        f"- 대표발의자: {lead_txt or '(정보 없음)'}",
    ]
    if co:
        lines.append(f"- 공동발의자: {len(co)}명 ({party_breakdown([s['party_at_proposal'] for s in co])})")
    lines += [
        f"- 소관위원회: {b['committee'] or '(미정)'}",
        f"- 처리 단계: {b['stage'] or '-'} / 상태: {b['status'] or '-'}",
        f"- 처리 결과: {b['result'] or '계류 중'}" + (f" (의결일 {b['passed_date']})" if b['passed_date'] else ""),
    ]
    for v in bill_votes(data, code):
        lines.append(f"- 본회의 표결: 표결 {v['rollcall_id']} ({v['process_date']}, {v['result']}, "
                     f"찬성 {v['pros']}·반대 {v['cons']}·기권 {v['abst']})")
    history = process_lines(b)
    if history:
        lines += ["", "## 심사·처리 경과"] + history
    reason, main = split_reason(b["proposal_reason"])
    if reason:
        lines += ["", "## 제안이유", clip(reason, MAX_REASON_CHARS)]
    if main:
        lines += ["", "## 주요내용", clip(main, MAX_DETAIL_CHARS)]
    title = f"의안 {code} {short_bill_name(b['bill_name'])}"
    return doc(f"bill-{code}", "의안", title, b["proposal_date"], "\n".join(lines))


def build_vote(data: dict, rid: str, meeting_titles: dict[str, str]) -> str:
    v = data["rollcalls"][rid]
    recs = data["records"][rid]
    by_party = defaultdict(Counter)
    for r in recs:
        by_party[r["party_at_vote"] or "정당 정보 없음"][r["vote"]] += 1

    lines = [
        f"# 본회의 표결: {v['name']} ({v['process_date']})",
        "",
        "## 표결 개요",
        f"- 표결 ID: {rid}",
        f"- 안건: 의안 {v['billcode']} {v['name']}",
        f"- 표결일: {v['process_date']}",
        f"- 결과: {v['result']}",
        f"- 재적 {v['member']}명 중 찬성 {v['pros']}명, 반대 {v['cons']}명, 기권 {v['abst']}명, 불참 {v['nons']}명",
    ]
    if v.get("committee"):
        lines.append(f"- 소관위원회: {v['committee']}")
    if rid in meeting_titles:
        lines.append(f"- 표결이 이루어진 본회의: {meeting_titles[rid]}")

    lines += ["", "## 정당별 표결 (투표 참여자 기준)", "", "| 정당 | 찬성 | 반대 | 기권 |", "|---|---|---|---|"]
    for party, c in sorted(by_party.items(), key=lambda kv: -sum(kv[1].values())):
        lines.append(f"| {party} | {c.get('찬성', 0)} | {c.get('반대', 0)} | {c.get('기권', 0)} |")
    lines.append(f"\n불참 {v['nons']}명의 명단은 원자료에 없다.")

    # Members whose vote differs from the most common vote within their party.
    minority = []
    for party, c in by_party.items():
        if len(c) < 2:
            continue
        top = c.most_common()
        majority = top[0][0] if top[0][1] > top[1][1] else None
        for r in recs:
            if (r["party_at_vote"] or "정당 정보 없음") == party and r["vote"] != majority:
                minority.append(f"- {r['name']} ({party}): {r['vote']}")
    if minority:
        lines += ["", "## 정당 내 소수 의견 투표자", "(같은 정당 투표자 다수와 다르게 투표했거나, 정당 내 찬반이 같은 수로 갈린 경우)"]
        lines += sorted(minority)
    against = [r for r in recs if r["vote"] in ("반대", "기권")]
    if 0 < len(against) <= 40:
        lines += ["", "## 반대·기권 의원 명단"]
        lines += [f"- {r['name']} ({r['party_at_vote'] or '정당 정보 없음'}): {r['vote']}"
                  for r in sorted(against, key=lambda r: (r["vote"], r["name"]))]
    title = f"표결 {rid} {v['process_date']} {short_bill_name(v['name'])}"
    return doc(f"vote-{rid}", "본회의 표결", title, v["process_date"], "\n".join(lines))


def build_member(data: dict, mid: str, led_bills: list[str], homonyms: set[str]) -> str | None:
    m = data["members"].get(mid)
    if m is None:
        return None
    name = m["name"]
    display = f"{name}({m['birthday'][:4]})" if name in homonyms and m["birthday"] else name
    other_names = [f"한자 {m['hanja']}"] if m["hanja"] else []
    other_names += [f"영문 {m['english']}"] if m["english"] else []
    lines = [
        f"# 국회의원 {display}",
        "",
        "## 기본 정보",
        f"- 이름: {name}" + (f" ({', '.join(other_names)})" if other_names else ""),
        f"- 생년월일: {m['birthday'] or '-'} / 성별: {m['sex'] or '-'}",
        f"- 소속 정당(최신): {m['party_latest'] or m['party'] or '-'}",
        f"- 선거구: {m['district'] or '-'} / 당선 유형: {m['elected'] or '-'} / 선수: {m['seniority'] or '-'}",
    ]
    if name in homonyms:
        lines.append(f"- 동명이인 구분: 이 문서의 {name}은 {m['birthday'][:4]}년생이다")
    tl = sorted(data["timeline"].get(mid, []), key=lambda r: r["observed_from"])
    if tl:
        lines += ["", "## 정당 이력"]
        lines += [f"- {r['observed_from']} ~ {r['observed_to'] or '현재'}: {r['party']} ({r['district']})" for r in tl]
    cm = sorted(data["committees"].get(mid, []), key=lambda r: r["from_date"], reverse=True)
    if cm:
        lines += ["", "## 위원회 경력"]
        lines += [f"- {r['committee']} ({r['from_date']} ~ {r['to_date'] or '현재'})" for r in cm[:15]]
    if m["career"]:
        career = m["career"]
        try:
            items = json.loads(career)
            if isinstance(items, list):
                career = "\n".join(str(x).strip() for x in items if str(x).strip())
        except json.JSONDecodeError:
            pass
        lines += ["", "## 주요 경력", clip(career, MAX_CAREER_CHARS)]
    if led_bills:
        lines += ["", "## 대표발의한 특별검사 관련 법안"]
        for code in led_bills:
            b = data["bills"][code]
            lines.append(f"- 의안 {code} {b['bill_name']} (발의 {b['proposal_date']}, {b['result'] or b['status'] or '계류 중'})")
    title = f"국회의원 {display}"
    return doc(f"member-{mid}", "국회의원", title, "", "\n".join(lines))


def match_meetings(data: dict) -> dict[str, dict]:
    """rollcall_id → plenary minutes row (agenda lists the bill number; ±1 day)."""
    out = {}
    for rid, v in data["rollcalls"].items():
        d = date.fromisoformat(v["process_date"])
        days = {d.isoformat(), (d - timedelta(days=1)).isoformat()}
        tag = f"의안번호 {v['billcode']}"
        hits = [m for m in data["plenary"] if tag in m["agenda"] and m["meeting_date"] in days]
        if hits:
            out[rid] = sorted(hits, key=lambda m: m["minute_id"])[0]
    return out


def build_meeting(data: dict, minute: dict, votes: list[dict], speeches: list[dict]) -> list[tuple[str, str]]:
    title_raw = minute["shortinfo"].strip('"') or minute["title"]
    try:
        agenda = json.loads(minute["agenda"])
    except json.JSONDecodeError:
        agenda = []
    header_lines = [
        f"# {title_raw} ({minute['meeting_date']})",
        "",
        "## 회의 정보",
        f"- 회의록 ID: {minute['minute_id']}",
        f"- 회의: {title_raw}",
        f"- 일자: {minute['meeting_date']}",
        f"- 회기: 제{minute['session']}회 {minute['type']} 제{minute['period']}차",
    ]
    blocks = []
    if votes:
        blocks.append("## 이 회의에서 표결된 특별검사 관련 안건\n" + "\n".join(
            f"- 표결 {v['rollcall_id']} ({v['process_date']}): 의안 {v['billcode']} {v['name']} → "
            f"{v['result']} (찬성 {v['pros']}·반대 {v['cons']}·기권 {v['abst']})" for v in votes))
    topical = [a for a in agenda if "특별검사" in a or "무제한토론" in a]
    if agenda:
        shown = topical + [a for a in agenda if a not in topical]
        blocks.append("## 안건 (특별검사 관련 우선)\n" + "\n".join(f"- {a}" for a in shown[:MAX_AGENDA_ITEMS]) +
                      (f"\n- …외 {len(agenda) - MAX_AGENDA_ITEMS}건" if len(agenda) > MAX_AGENDA_ITEMS else ""))
    picked = sorted(speeches, key=lambda s: int(s.get("seq") or 0))[:MAX_SPEECHES_PER_MEETING]
    for s in picked:
        who = f"{s['speaker_name']} ({s.get('position') or '-'}" + (f", {s['party']}" if s.get("party") else "") + ")"
        blocks.append(f"## 발언: {who}\n{clip(s['line'], MAX_SPEECH_CHARS)}")
    title = f"회의록 {minute['minute_id']} {title_raw}"
    return split_doc(f"meeting-{minute['minute_id']}", "본회의 회의록", title, minute["meeting_date"],
                     "\n".join(header_lines), blocks)


# ─── questions with gold answers ──────────────────────────────────────────

def build_questions(data: dict, initial_codes: set[str], add_codes: set[str]) -> list[dict]:
    qs = []
    for code in sorted(initial_codes | add_codes):
        b = data["bills"][code]
        stage = "add" if code in add_codes else "initial"
        name = short_bill_name(b["bill_name"])
        leads = [s for s in lead_sponsors(data, code) if s["role"] == "대표"]
        votes = bill_votes(data, code)
        if votes:
            v = votes[0]
            qs.append({"id": f"pros-{code}", "stage": stage, "hops": 1,
                       "question": f"의안번호 {code} 「{name}」의 본회의 표결({v['process_date']})에서 찬성한 의원은 몇 명인가?",
                       "answer": f"{v['pros']}명"})
        if len(leads) == 1 and leads[0]["party_at_proposal"]:
            lead = leads[0]
            m = data["members"].get(lead["member_id"])
            qs.append({"id": f"lead-party-{code}", "stage": stage, "hops": 1,
                       "question": f"의안번호 {code} 「{name}」을 대표발의한 의원과 그 소속 정당은?",
                       "answer": f"{lead['name']}, {lead['party_at_proposal']}"})
            if m and m["district"]:
                qs.append({"id": f"lead-district-{code}", "stage": stage, "hops": 2,
                           "question": f"의안번호 {code} 「{name}」을 대표발의한 의원의 선거구는?",
                           "answer": m["district"]})
            current = sorted({r["committee"] for r in data["committees"].get(lead["member_id"], [])
                              if not r["to_date"] and "특별위원회" not in r["committee"]})
            if current and len(current) <= 2:
                qs.append({"id": f"lead-committee-{code}", "stage": stage, "hops": 2,
                           "question": f"의안번호 {code} 「{name}」을 대표발의한 의원이 현재 소속된 상임위원회는?",
                           "answer": ", ".join(current)})
        v_info = veto(b)
        if v_info and _val(v_info, "재의처리결과"):
            qs.append({"id": f"veto-{code}", "stage": stage, "hops": 1,
                       "question": f"의안번호 {code} 「{name}」에 대한 대통령 재의요구 이후 본회의 재의결 결과는?",
                       "answer": _val(v_info, "재의처리결과")})
    for rid, v in sorted(data["rollcalls"].items()):
        stage = "add" if v["billcode"] in add_codes else "initial"
        by_party = defaultdict(list)
        for r in data["records"][rid]:
            by_party[r["party_at_vote"]].append(r)
        ppp = by_party.get("국민의힘", [])
        yes = [r["name"] for r in ppp if r["vote"] == "찬성"]
        if ppp and 0 < len(yes) <= 3 and len(yes) < len(ppp):
            qs.append({"id": f"ppp-yes-{rid}", "stage": stage, "hops": 1,
                       "question": f"「{short_bill_name(v['name'])}」 본회의 표결({v['process_date']})에서 국민의힘 소속으로 찬성한 의원은?",
                       "answer": ", ".join(sorted(yes))})
    return qs


# ─── main ─────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--raw", default="raw", help="Directory with bills/ votes/ members/ minutes/ (default: raw)")
    ap.add_argument("--out", default="examples/assembly_spc", help="Output directory")
    ap.add_argument("--keyword", default="특별검사", help="Topic keyword matched against bill names")
    ap.add_argument("--add-keyword", default="지방선거",
                    help="Bills whose name also contains this go to the live 'add' sets")
    ap.add_argument("--small-before", default="2025-01-01",
                    help="Small preset: voted bills processed before this date")
    args = ap.parse_args()

    raw, out = Path(args.raw), Path(args.out)
    data = load(raw, args.keyword)

    add_cluster = {c for c, b in data["bills"].items() if args.add_keyword and args.add_keyword in b["bill_name"]}
    voted_codes = {v["billcode"] for v in data["rollcalls"].values()}
    add_codes = add_cluster & voted_codes
    extra_codes = add_cluster - voted_codes
    initial_codes = set(data["bills"]) - add_cluster

    meetings = match_meetings(data)
    minute_ids = {m["minute_id"] for m in meetings.values()}
    speeches = load_speeches(raw, minute_ids, args.keyword)
    meeting_titles = {rid: f"회의록 {m['minute_id']} {m['shortinfo'].strip(chr(34))}" for rid, m in meetings.items()}

    names = Counter(m["name"] for m in data["members"].values() if m["is_primary_code"] == "True")
    homonyms = {n for n, c in names.items() if c > 1}

    sets: dict[str, dict[str, str]] = {"articles": {}, "add": {}, "add_extra": {}}

    def target(code: str) -> str:
        return "add" if code in add_codes else ("add_extra" if code in extra_codes else "articles")

    for code in data["bills"]:
        sets[target(code)][f"bill-{code}.md"] = build_bill(data, code)
    for rid, v in data["rollcalls"].items():
        sets[target(v["billcode"])][f"vote-{rid}.md"] = build_vote(data, rid, meeting_titles)

    # Members: lead sponsors. A member already introduced by the initial set is
    # *not* re-emitted in the add sets, so adding data updates the existing page.
    led = defaultdict(list)
    for code in sorted(data["bills"]):
        for s in lead_sponsors(data, code):
            if s["role"] == "대표" and s["member_id"]:
                led[s["member_id"]].append(code)
    for mid, codes in led.items():
        initial_led = [c for c in codes if c in initial_codes]
        bucket = "articles" if initial_led else target(codes[0])
        text = build_member(data, mid, initial_led if initial_led else codes, homonyms)
        if text:
            sets[bucket][f"member-{mid}.md"] = text

    by_minute = defaultdict(list)
    for rid, m in meetings.items():
        by_minute[m["minute_id"]].append(data["rollcalls"][rid])
    minutes_by_id = {m["minute_id"]: m for m in meetings.values()}
    for mid, votes in by_minute.items():
        votes.sort(key=lambda v: v["rollcall_id"])
        bucket = "add" if any(v["billcode"] in add_codes for v in votes) else "articles"
        for part_id, text in build_meeting(data, minutes_by_id[mid], votes, speeches.get(mid, [])):
            sets[bucket][f"{part_id}.md"] = text

    # Small preset: voted bills before --small-before, their votes, leads, meetings.
    small_codes = {v["billcode"] for v in data["rollcalls"].values()
                   if v["process_date"] < args.small_before and v["billcode"] in initial_codes}
    small = {f"bill-{c}.md" for c in small_codes}
    small |= {f"vote-{rid}.md" for rid, v in data["rollcalls"].items() if v["billcode"] in small_codes}
    small |= {f"member-{s['member_id']}.md" for c in small_codes for s in lead_sponsors(data, c)
              if s["role"] == "대표" and f"member-{s['member_id']}.md" in sets["articles"]}
    small |= {f for f in sets["articles"] if f.startswith("meeting-") and any(
              meetings[rid]["minute_id"] in f for rid, v in data["rollcalls"].items()
              if v["billcode"] in small_codes and rid in meetings)}

    for sub in sets:
        d = out / sub
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        for fname, text in sorted(sets[sub].items()):
            (d / fname).write_text(text, encoding="utf-8")

    manifest = {
        "keyword": args.keyword,
        "add_keyword": args.add_keyword,
        "full": sorted(sets["articles"]),
        "small": sorted(small),
        "add": sorted(sets["add"]),
        "add_extra": sorted(sets["add_extra"]),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    questions = build_questions(data, initial_codes, add_codes)
    with open(out / "questions.jsonl", "w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    longest = max((len(t) for s in sets.values() for t in s.values()), default=0)
    print(f"Wrote {out}/: articles={len(sets['articles'])} add={len(sets['add'])} "
          f"add_extra={len(sets['add_extra'])} small={len(small)} questions={len(questions)} "
          f"(longest article {longest} chars)")


if __name__ == "__main__":
    main()
