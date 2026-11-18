"""The one-time transcoding repair restores exactly the text a cp1252 misreading damaged, and nothing else (G39).

WHY IT EXISTS. A local pass on 2026-05-02 (a02573fd) read UTF-8 generated records as cp1252 and wrote
them back, so "agent’s" was stored as "agentâ€™s" in a Figma record's title, version and feed titles,
and two other records' summaries. A refresh never rewrites those fields and the ingestion lane never
re-observes those records, so migrate_repair_transcoded_text.py repairs them once, through the
writer's serializer.

WHAT IS PINNED HERE.
  [M] the repair undoes exactly the misreading of curly quotes, dashes, accented letters, the euro and
      trade-mark signs and the no-break space; correct UTF-8 text, ASCII and a field that mixes correct
      and damaged text are never changed (the last is reported, not guessed), nor is text misread twice
      (M10: one undo would leave it damaged); a dry run writes nothing
      and plans exactly the damaged records and fields; a write repairs those fields, leaves every other
      field and every other file as it was, and touches no nested evidence copy; a second run is a
      no-op; no socket is used; the scope proof refuses a write during which another file changed.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_transcoded_text_repair.py
"""
from __future__ import annotations

import io
import json
import socket
import sys
import tempfile
import traceback
from contextlib import redirect_stdout
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "auxsays" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lib import write_update_record as writer  # noqa: E402
import migrate_repair_transcoded_text as migration  # noqa: E402

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print("  PASS  " + label)
    else:
        _FAIL += 1
        print("  FAIL  " + label)
        if detail:
            print("        " + detail)
        _ERRORS.append(label)


def misread(text: str) -> str:
    """What the 2026-05-02 pass did to a UTF-8 string."""
    return text.encode("utf-8").decode("cp1252")


TITLE = "FigJam is your coding agent’s whiteboard now"
SUMMARY = "With new MCP tool updates, you can now generate diagrams — including into files you’re in."
CORRECT = "Café “quoted” – fine… 5 € and ™, déjà vu — naïve"
EVIDENCE_TITLE = "mac-capture crashes OBS — mach_vm_allocate_kernel failed"


def record(slug: str, **fields) -> dict:
    base = {"layout": "aux-update", "title": f"Figma {slug} official update breakdown", "product_id": "figma",
            "update_product": "Figma", "update_version": slug, "update_report_count": 0}
    base.update(fields)
    return base


def build(root: Path) -> Path:
    records = root / "generated"
    records.mkdir()
    files = {
        # The damaged record: title-bearing fields damaged, its official body re-captured correctly later.
        "2026-04-28-figma-damaged.md": record(
            misread(TITLE), title=f"Figma {misread(TITLE)} official update breakdown",
            update_feed_title=f"Figma {misread(TITLE)}", quick_verdict=f"Figma {misread(TITLE)} has an official record.",
            release_summary=misread(SUMMARY), official_patch_notes_body=SUMMARY),
        # Correct UTF-8 throughout: never touched.
        "2026-04-29-figma-correct.md": record("Correct", release_summary=CORRECT, official_patch_notes_body=CORRECT),
        # ASCII only.
        "2026-04-30-figma-ascii.md": record("Plain", release_summary="Nothing unusual here."),
        # Damage only inside a nested evidence copy: out of scope, never touched.
        "2026-04-02-obs-studio-32-1-1.md": {
            "layout": "aux-update", "product_id": "obs-studio", "update_version": "32.1.1",
            "accepted_report_sources": [{"source_title": misread(EVIDENCE_TITLE), "source_url": "https://x.test/1"}]},
        # One field mixing correct and damaged text: reported, never guessed.
        "2026-05-01-figma-mixed.md": record("Mixed", release_summary="Already right — " + misread("but this isn’t")),
    }
    for name, front in files.items():
        (records / name).write_bytes(writer._dump_record(front).encode("utf-8"))
    return records


def run(records: Path, *, write: bool) -> tuple[int, dict]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = migration.main(["--records", str(records)] + (["--write"] if write else []))
    try:
        return code, json.loads(buf.getvalue())
    except ValueError:
        return code, {"unparsed": buf.getvalue()}


def snapshot(records: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(records.glob("*.md"))}


DAMAGED_FIELDS = sorted(["update_version", "title", "update_feed_title", "quick_verdict", "release_summary"])


def section_m() -> None:
    print("\n[M] the transcoding repair is exact and scoped")
    # (The closing double quote is absent on purpose: its last UTF-8 byte, 0x9D, has no cp1252 character,
    # so a strict cp1252 read cannot have produced it; such text fails the round trip and is reported.)
    samples = [TITLE, SUMMARY, "‘single’ and “open", "en – dash", "café", "Zürich", "5 €", "Brand™", "a" + chr(0xA0) + "b", "…"]
    wrong = [s for s in samples if migration.repair_text(misread(s)) != s]
    check("M1 the repair undoes exactly the misreading of quotes, dashes, accents, euro, trade mark, no-break space",
          not wrong, str(wrong))
    untouched = [s for s in (CORRECT, "SÃO PAULO", "plain ascii", "naïve", "Ångström", "€5")
                 if migration.repair_text(s) is not None]
    check("M2 correct UTF-8 text and ASCII are never changed", not untouched, str(untouched))
    # (Each sample must survive a second strict cp1252 read; a closing curly quote does not, see M1.)
    twice = [s for s in (TITLE, "en – dash", "café") if migration.repair_text(misread(misread(s))) is not None]
    check("M10 text misread twice is left alone, never half repaired (one undo still carries the signature)",
          not twice, str(twice))

    with tempfile.TemporaryDirectory() as td:
        records = build(Path(td))
        original = snapshot(records)
        code, report = run(records, write=False)
        check("M3 a dry run writes nothing and plans exactly the damaged record and fields",
              code == 0 and snapshot(records) == original
              and {k: sorted(v) for k, v in report.get("repaired", {}).items()}
              == {"2026-04-28-figma-damaged.md": DAMAGED_FIELDS}, json.dumps(report, ensure_ascii=False)[:400])
        check("M4 a field mixing correct and damaged text is reported, never guessed",
              report.get("not_repaired") == {"2026-05-01-figma-mixed.md": ["release_summary"]},
              json.dumps(report.get("not_repaired"), ensure_ascii=False))

        real_connect = socket.socket.connect

        def refuse(*_a, **_k):
            raise AssertionError("network used")

        socket.socket.connect = refuse
        try:
            code, report = run(records, write=True)
        finally:
            socket.socket.connect = real_connect
        after = snapshot(records)
        check("M5 the write runs with every socket refused", code == 0, json.dumps(report, ensure_ascii=False)[:300])
        front, _ = writer._front_matter(records / "2026-04-28-figma-damaged.md")
        expected = {"update_version": TITLE, "title": f"Figma {TITLE} official update breakdown",
                    "update_feed_title": f"Figma {TITLE}", "quick_verdict": f"Figma {TITLE} has an official record.",
                    "release_summary": SUMMARY, "official_patch_notes_body": SUMMARY, "layout": "aux-update",
                    "product_id": "figma", "update_product": "Figma", "update_report_count": 0}
        check("M6 the damaged fields read back as the original text, and every other field is unchanged",
              front == expected, json.dumps({k: front.get(k) for k in front if front.get(k) != expected.get(k)},
                                            ensure_ascii=False)[:400])
        changed = sorted(n for n in after if after[n] != original[n])
        check("M7 every other file is byte-identical, including the nested evidence copy and the mixed field",
              changed == ["2026-04-28-figma-damaged.md"], str(changed))

        code, again = run(records, write=True)
        check("M8 a second run repairs nothing and changes no byte",
              code == 0 and again.get("repaired") == {} and snapshot(records) == after,
              json.dumps(again, ensure_ascii=False)[:200])

    with tempfile.TemporaryDirectory() as td:
        records = build(Path(td))
        bystander = "2026-04-29-figma-correct.md"
        real_digest = migration._digest
        seen: dict[str, int] = {}

        def concurrent_writer(path: Path) -> str:
            seen[path.name] = seen.get(path.name, 0) + 1
            if path.name == bystander and seen[path.name] == 2:
                return "changed-by-someone-else"
            return real_digest(path)

        migration._digest = concurrent_writer
        try:
            code, report = run(records, write=True)
        finally:
            migration._digest = real_digest
        check("M9 the scope proof refuses a write during which any other file changed",
              code == 1 and report.get("error") == "scope_violation" and bystander in report.get("touched", []),
              json.dumps(report, ensure_ascii=False)[:300])


def main() -> int:
    section_m()
    print()
    print("=" * 78)
    print(f"Results: {_PASS}/{_PASS + _FAIL} passed, {_FAIL} failed")
    for e in _ERRORS:
        print(f"  - {e}")
    print("=" * 78)
    return 1 if _FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2) from None
