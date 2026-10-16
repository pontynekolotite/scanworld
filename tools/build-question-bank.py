#!/usr/bin/env python3
"""Build the Scanworld question bank from a Wiktextract Russian dump.

Input is the JSONL.GZ published at
https://kaikki.org/ruwiktionary/raw-wiktextract-data.jsonl.gz
The generated data is derived from Russian Wiktionary and is distributed under
the same CC BY-SA terms. See ATTRIBUTION.md.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import re
from collections import Counter
from pathlib import Path

WORD_RE = re.compile(r"^[а-яё]{3,18}$")
BASE_VERB_RE = re.compile(r"(?:ть|ти|чь|ться|тись|чься)$")
BASE_ADJ_RE = re.compile(r"(?:ый|ий|ой)$")
FORM_RE = re.compile(
    r"^(?:форма|вариант|падеж|множественное|единственное|действ\.\s*прич\.|"
    r"страд\.\s*прич\.|прич\.\s*от|деепр\.\s*от|будущее время|прошедшее "
    r"время|настоящее время|повелительное наклонение)", re.I
)
BAD_CATEGORIES = (
    "имена собственные", "фамилии", "топонимы", "имена/ru",
    "аббревиатуры", "обсценная лексика",
)
LABELS = {
    "авиац.": "В авиации:", "анат.": "В анатомии:", "архит.": "В архитектуре:",
    "астрон.": "В астрономии:", "биол.": "В биологии:", "ботан.": "В ботанике:",
    "воен.": "В военном деле:", "геогр.": "В географии:", "геол.": "В геологии:",
    "лингв.": "В языкознании:", "матем.": "В математике:", "мед.": "В медицине:",
    "муз.": "В музыке:", "морск.": "В морском деле:", "спорт.": "В спорте:",
    "техн.": "В технике:", "физ.": "В физике:", "филос.": "В философии:",
    "хим.": "В химии:", "экон.": "В экономике:", "юр.": "В праве:",
    "зоол.": "В зоологии:", "истор.": "Историческое:", "устар.": "Устаревшее:",
    "разг.": "Разговорное:", "книжн.": "Книжное:", "поэт.": "Поэтическое:",
    "прост.": "Просторечное:", "жарг.": "Жаргонное:", "спец.": "Специальное:",
    "перен.": "Переносное значение:", "высок.": "Высокий стиль:",
    "бран.": "Бранное:", "неодобр.": "Неодобрительное:", "ирон.": "Ироническое:",
    "неол.": "Новое слово:", "рег.": "Региональное:", "религ.": "В религии:",
    "геометр.": "В геометрии:", "фарм.": "В фармакологии:",
}
DROP_LABELS = ("мн. ч.", "ед. ч.", "безл.", "обычно", "преим.", "часто")


def normalise_answer(word: str) -> str:
    return word.upper().replace("Ё", "Е")


def clean_gloss(gloss: str) -> str | None:
    gloss = re.sub(r"\s+", " ", gloss).strip(" .;—")
    gloss = gloss.split(" ‖ ", 1)[0].rstrip(" .;—")
    lowered_raw = gloss.lower()
    if re.match(r"^бран\.", lowered_raw) or any(x in lowered_raw for x in (
        "пассивный гомосексуалист", "педераст", "обсценн", "ненормативн",
    )):
        return None
    if not 10 <= len(gloss) <= 160 or FORM_RE.match(gloss):
        return None
    labels = []
    for _ in range(8):
        lowered = gloss.lower()
        found = False
        for raw in DROP_LABELS:
            if lowered.startswith(raw):
                gloss = gloss[len(raw):].lstrip(" ,.;—")
                found = True
                break
        if found:
            continue
        for raw, label in LABELS.items():
            if lowered.startswith(raw):
                labels.append(label)
                gloss = gloss[len(raw):].lstrip(" ,.;—")
                found = True
                break
        if not found:
            unknown = re.match(r"^[А-Яа-яЁё]{2,14}\.\s*", gloss)
            if unknown:
                labels.append("Специальное:")
                gloss = gloss[unknown.end():].lstrip(" ,.;—")
                found = True
        if not found:
            break
    if labels:
        # One readable register/domain label is enough for a crossword clue.
        label = next((x for x in labels if x.startswith("В ")), labels[-1])
        gloss = label + " " + gloss
    gloss = re.sub(r"([:])\s*[,;]+\s*", r"\1 ", gloss)
    gloss = re.sub(r"^(?:то же, что|то же что)\s+", "", gloss, flags=re.I)
    if any(mark in gloss for mark in ("{{", "}}", "[[", "]]", "<ref")):
        return None
    return gloss[0].upper() + gloss[1:]


def frequency_map(openrussian: Path | None) -> dict[str, int]:
    if not openrussian:
        return {}
    result: dict[str, int] = {}
    rank = 0
    for name in ("nouns.csv", "verbs.csv", "adjectives.csv", "others.csv"):
        path = openrussian / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                word = (row.get("bare") or "").lower().replace("ё", "е")
                if word and word not in result:
                    rank += 1
                    result[word] = rank
    return result


def raw_difficulty(word: str, clue: str, pos: str, rank: int | None) -> float:
    if rank is None:
        score = 7.2
    elif rank <= 1000:
        score = 1.0
    elif rank <= 3000:
        score = 2.0
    elif rank <= 7000:
        score = 3.0
    elif rank <= 15000:
        score = 4.0
    elif rank <= 30000:
        score = 5.0
    else:
        score = 6.0
    score += max(0, len(word) - 7) * .22
    score += max(0, len(clue) - 80) / 90
    if pos in {"adj", "adv"}:
        score += .35
    if re.match(r"^(?:В |Историческое|Книжное|Поэтическое|Специальное)", clue):
        score += .75
    if re.match(r"^(?:Устаревшее|Жаргонное|Просторечное|Бранное|Региональное|Новое слово)", clue):
        score += 1.5
    if any(x in clue.lower() for x in ("редкое", "древн", "устар", "термин", "мифолог")):
        score += .5
    return score


def quality(word: str, clue: str, pos: str, rank: int | None) -> float:
    value = 100.0
    value -= max(0, len(clue) - 115) * .2
    value -= clue.count(";") * 2
    value -= clue.count("(") * 1.5
    if rank is not None:
        value += max(0, 18 - math.log2(rank + 1))
    if pos == "noun":
        value += 5
    if re.search(r"\b(?:кто-либо|что-либо|какой-либо)\b", clue, re.I):
        value -= 2
    return value


def extract(dump: Path, ranks: dict[str, int]) -> list[dict]:
    unique: dict[tuple[str, str], dict] = {}
    with gzip.open(dump, "rt", encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            word = (item.get("word") or "").lower()
            pos = item.get("pos") or ""
            if item.get("lang_code") != "ru" or pos not in {"noun", "verb", "adj", "adv"}:
                continue
            if not WORD_RE.fullmatch(word):
                continue
            if pos == "verb" and not BASE_VERB_RE.search(word):
                continue
            if pos == "adj" and not BASE_ADJ_RE.search(word):
                continue
            categories = " ".join(item.get("categories") or []).lower()
            if any(bad in categories for bad in BAD_CATEGORIES):
                continue
            answer = normalise_answer(word)
            rank = ranks.get(word.replace("ё", "е"))
            for sense in item.get("senses") or []:
                tags = set(sense.get("tags") or [])
                if tags & {"form-of", "alt-of", "no-gloss"}:
                    continue
                for raw in sense.get("glosses") or []:
                    clue = clean_gloss(raw)
                    if not clue:
                        continue
                    # A clue containing the answer gives the game away.
                    if re.search(rf"(?<![А-ЯЁ]){re.escape(answer)}(?![А-ЯЁ])", clue.upper().replace("Ё", "Е")):
                        continue
                    key = (answer, clue.casefold())
                    candidate = {
                        "a": answer, "q": clue, "pos": pos,
                        "rank": rank, "raw": raw_difficulty(word, clue, pos, rank),
                        "quality": quality(word, clue, pos, rank),
                    }
                    old = unique.get(key)
                    if old is None or candidate["quality"] > old["quality"]:
                        unique[key] = candidate
    return list(unique.values())


def write_bank(candidates: list[dict], output: Path, total: int) -> dict:
    candidates.sort(key=lambda x: (-x["quality"], x["raw"], x["a"], x["q"]))
    selected = candidates[:total]
    # Keep the editorial scale meaningful: levels follow frequency and linguistic
    # complexity, rather than forcing the same number of entries into each bucket.
    for row in selected:
        row["difficulty"] = max(1, min(10, round(row["raw"])))
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"version": 1, "total": len(selected), "levels": {}, "source": "ruwiktionary-2026-10-01"}
    chunks_per_level = 4
    for difficulty in range(1, 11):
        level = [row for row in selected if row["difficulty"] == difficulty]
        level.sort(key=lambda x: (x["raw"], -x["quality"], x["a"], x["q"]))
        chunk_size = max(1, math.ceil(len(level) / chunks_per_level))
        files = []
        for part in range(chunks_per_level):
            rows = level[part * chunk_size:(part + 1) * chunk_size]
            name = f"level-{difficulty:02d}-{part + 1:02d}.json"
            payload = [[row["a"], row["q"], difficulty] for row in rows]
            (output / name).write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            files.append({"file": name, "count": len(payload)})
        manifest["levels"][str(difficulty)] = {"count": len(level), "chunks": files}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dump", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--openrussian", type=Path)
    parser.add_argument("--total", type=int, default=210_000)
    args = parser.parse_args()
    if args.total % 10:
        raise SystemExit("--total must be divisible by 10")
    ranks = frequency_map(args.openrussian)
    candidates = extract(args.dump, ranks)
    if len(candidates) < args.total:
        raise SystemExit(f"Only {len(candidates)} candidates after validation; need {args.total}")
    manifest = write_bank(candidates, args.output, args.total)
    print(json.dumps({
        "candidates": len(candidates), "selected": manifest["total"],
        "levels": {k: v["count"] for k, v in manifest["levels"].items()},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
