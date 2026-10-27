"""The one-time backlog labelling adds windows_macos where stored notes prove it, and touches nothing else.

WHY IT EXISTS. AUX-050 labels records whose notes list the product's own installers for both
platforms, on create and on refresh. Records created before that change and older than the Zendesk
refresh window are never re-observed, so on a product flagged official_notes_by_platform their
readers would see PLATFORM APPLICABILITY UNKNOWN forever.

WHAT IS PINNED HERE.
  [K] a dry run changes no byte; a write appends exactly two lines to each record its stored notes
      prove, and leaves every other file byte-identical; nothing a fresh vendor check would move is
      moved; a record whose notes establish nothing is reported with its reason, never labelled; an
      unflagged product is never in scope; a second run is a no-op; it makes no network request; it
      decides with the SHIPPED classifier; and its own scope proof refuses a write that touched any
      other file.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_official_notes_platform_backlog.py
"""
from __future__ import annotations

import difflib
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

import yaml  # noqa: E402

from adapters import zendesk_help_center as zendesk  # noqa: E402
from lib import write_update_record as writer  # noqa: E402
import migrate_official_notes_platform_backlog as migration  # noqa: E402

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


HOST = "help.elgato.com"
PRODUCTS = {"elgato-stream-deck": ("Stream Deck", ["stream deck"]),
            "elgato-camera-hub": ("Camera Hub", ["camera hub"]),
            "elgato-wave-link": ("Wave Link", ["wave link"]),
            "elgato-4k-capture-utility": ("4K Capture Utility", ["4k capture utility", "4k capture"])}
FLAGGED = ("elgato-stream-deck", "elgato-camera-hub", "elgato-wave-link")


def joint(software: str, version: str) -> str:
    return (f"Release Date: 1 July 2026 Download Links macOS Elgato {software} {version}.pkg Windows Elgato "
            f"{software} {version}.msi What's new in {software} {version}? Fixes and improvements.")


# (product, version, published, stored platform, notes) -- the expected decision is in EXPECT.
FIXTURES = [
    ("elgato-stream-deck", "7.5.0", "2026-07-01", "", joint("Stream Deck", "7.5.0")),
    ("elgato-camera-hub", "2.2", "2025-10-09", "", joint("Camera Hub", "2.2")),
    ("elgato-stream-deck", "7.6", "2026-09-22", "windows_macos", joint("Stream Deck", "7.6")),
    ("elgato-wave-link", "3.2.10", "2026-08-05", "windows",
     "Download Links Windows Elgato Wave Link 3.2.10.msix (x64) Elgato Wave Link 3.2.10.msix (arm64)"),
    ("elgato-camera-hub", "2.1", "2025-07-29", "", "Download Links Windows Elgato Camera Hub 2.1.msi only."),
    ("elgato-stream-deck", "7.4.2", "2026-05-18", "",
     "Troubleshooting note: DemoPlugin 7.4.2.pkg and DemoTool 7.4.2.msi both fail to launch."),
    ("elgato-wave-link", "3.1", "2026-03-01", "", "What's new in Wave Link 3.1? Fixes for Windows and macOS."),
    ("elgato-4k-capture-utility", "1.7.13", "2024-07-16", "", joint("4K Capture Utility", "1.7.13")),
]
EXPECT_LABELLED = {"elgato-stream-deck 7.5.0", "elgato-camera-hub 2.2"}
EXPECT_REASONS = {"elgato-camera-hub 2.1: unverified", "elgato-stream-deck 7.4.2: no_installers",
                  "elgato-wave-link 3.1: no_installers"}
# What a FRESH vendor check would move. The migration reads stored evidence, so none of these may.
CHECK_FIELDS = ("source_last_checked", "official_body_last_checked", "official_source_attempts",
                "update_published_at", "official_patch_notes_body", "official_patch_notes_capture_status")


def build(root: Path) -> tuple[Path, Path, Path]:
    records = root / "generated"
    records.mkdir()
    for product_id, version, published, platform, notes in FIXTURES:
        software, _terms = PRODUCTS[product_id]
        rec = {"record_id": f"zendesk:{product_id}:{version}:x", "company_id": "elgato",
               "product_id": product_id, "company": "Elgato", "software": software, "category": "Audio",
               "version": version, "title": f"Elgato {software} {version} Release Notes",
               "published_at": f"{published}T10:00:00Z",
               "source_url": f"https://{HOST}/hc/en-us/articles/1-{product_id}-{version}",
               "official_url": f"https://{HOST}/hc/en-us/sections/1", "download_url": "", "body": notes,
               "source_type": "help_center_release_notes", "source_last_checked": "2026-10-01T00:00:00Z"}
        if platform:
            rec["official_notes_platform"] = platform
            rec["official_notes_platform_basis"] = ("title_token" if platform in ("windows", "macos")
                                                    else "installer_downloads")
        writer.write_record(records, rec)
    products = root / "patch_products.yml"
    products.write_text(yaml.safe_dump([dict({"id": pid}, **({"official_notes_by_platform": True}
                                                               if pid in FLAGGED else {}))
                                        for pid in PRODUCTS]), encoding="utf-8")
    sources = root / "patch_ingestion_sources.yml"
    sources.write_text(yaml.safe_dump([{"product_id": pid, "company": "Elgato", "software": software,
                                        "ingestion": {"product_terms": terms}}
                                       for pid, (software, terms) in PRODUCTS.items()]), encoding="utf-8")
    return records, products, sources


def run(records: Path, products: Path, sources: Path, *, write: bool) -> tuple[int, dict]:
    argv = ["--records", str(records), "--products", str(products), "--sources", str(sources)]
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = migration.main(argv + (["--write"] if write else []))
    try:
        report = json.loads(buf.getvalue())
    except ValueError:
        report = {"unparsed": buf.getvalue()}
    return code, report


def snapshot(records: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(records.glob("*.md"))}


def key_of(name: str, records: Path) -> str:
    front, _ = writer._front_matter(records / name)
    return f"{front.get('product_id')} {front.get('update_version')}"


def section_k() -> None:
    print("\n[K] the backlog labelling proves its scope")
    with tempfile.TemporaryDirectory() as td:
        records, products, sources = build(Path(td))
        original = snapshot(records)

        code, report = run(records, products, sources, write=False)
        check("K1 a dry run changes no byte and plans exactly the records the stored notes prove",
              code == 0 and snapshot(records) == original and set(report.get("labelled", [])) == EXPECT_LABELLED,
              json.dumps(report)[:300])

        real_connect = socket.socket.connect
        real_fetch = zendesk.fetch_text

        def refuse(*_a, **_k):
            raise AssertionError("network used")

        socket.socket.connect = refuse
        zendesk.fetch_text = refuse
        try:
            code, report = run(records, products, sources, write=True)
        finally:
            socket.socket.connect = real_connect
            zendesk.fetch_text = real_fetch
        after = snapshot(records)
        check("K2 the write runs with every socket and the adapter's fetch refused",
              code == 0 and set(report.get("labelled", [])) == EXPECT_LABELLED, json.dumps(report)[:300])

        changed = {n for n in after if after[n] != original.get(n)}
        changed_keys = {key_of(n, records) for n in changed}
        added_ok = True
        for name in changed:
            diff = [ln for ln in difflib.unified_diff(original[name].decode("utf-8").splitlines(),
                                                      after[name].decode("utf-8").splitlines(), lineterm="", n=0)
                    if not ln.startswith(("---", "+++", "@@"))]
            added_ok &= diff == ["+official_notes_platform: windows_macos",
                                 "+official_notes_platform_basis: installer_downloads"]
        check("K3 each labelled record gains exactly two lines, the value and its basis", added_ok and changed,
              str(sorted(changed)))
        check("K4 every other file is byte-identical: labelled already, unflagged, or unproven",
              changed_keys == EXPECT_LABELLED, str(sorted(changed_keys)))

        moved = []
        for name in changed:
            before_front = yaml.safe_load(writer.split_front_matter(original[name].decode("utf-8"))[0])
            after_front, _ = writer._front_matter(records / name)
            moved += [f"{name}:{f}" for f in CHECK_FIELDS if before_front.get(f) != after_front.get(f)]
        check("K5 nothing a fresh vendor check would move is moved", not moved, str(moved))

        check("K6 notes that establish nothing are reported with their reason, never labelled",
              set(report.get("not_labelled", [])) == EXPECT_REASONS, str(report.get("not_labelled")))
        check("K7 an unflagged product is never in scope, even with joint installers",
              not any("4k-capture" in item for item in report.get("labelled", []) + report.get("not_labelled", [])),
              str(report))

        code, again = run(records, products, sources, write=True)
        check("K8 a second run labels nothing and changes no byte",
              code == 0 and again.get("labelled") == [] and snapshot(records) == after, json.dumps(again)[:200])

    with tempfile.TemporaryDirectory() as td:
        records, products, sources = build(Path(td))
        original = snapshot(records)
        shipped = zendesk.joint_platform_downloads
        zendesk.joint_platform_downloads = lambda *_a, **_k: ("", True)
        try:
            code, report = run(records, products, sources, write=True)
        finally:
            zendesk.joint_platform_downloads = shipped
        check("K9 the decision is the SHIPPED classifier's: refusing it labels nothing",
              report.get("labelled") == [] and snapshot(records) == original, json.dumps(report)[:200])

    with tempfile.TemporaryDirectory() as td:
        records, products, sources = build(Path(td))
        bystander = next(p for p in sorted(records.glob("*.md")) if "wave-link-3-2-10" in p.name)
        real_digest = migration._digest
        seen: dict[str, int] = {}

        def concurrent_writer(path: Path) -> str:
            seen[path.name] = seen.get(path.name, 0) + 1
            if path.name == bystander.name and seen[path.name] == 2:
                return "changed-by-someone-else"
            return real_digest(path)

        migration._digest = concurrent_writer
        try:
            code, report = run(records, products, sources, write=True)
        finally:
            migration._digest = real_digest
        check("K10 the scope proof refuses a write during which any other file changed",
              code == 1 and report.get("error") == "scope_violation"
              and bystander.name in report.get("touched", []), json.dumps(report)[:300])


def main() -> int:
    section_k()
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
