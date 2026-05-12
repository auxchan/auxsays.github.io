# Phase 1G DaVinci Promotion Decision Log

Generated from `auxsays/scripts/collect_davinci_candidates.py --dry-run --target both`.

## Summary

- Total candidates staged: 14
- Promote now: 0
- Needs user verification: 7
- Duplicate existing evidence: 2
- Future update not current record: 1
- Ambiguous version: 4
- Rejected: 0

No candidate is promotion-ready in Phase 1G. No new rows should be added to `auxsays/_data/consensus_evidence.yml` from this run.

## Decisions

| Source | Target | Decision | Reason |
|---|---|---|---|
| `https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235117` | ambiguous | needs_user_verification | Blackmagic forum returned `http_403_blocked_or_inaccessible`; no body/version can be verified without user review. |
| `https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235536` | ambiguous | needs_user_verification | Blackmagic forum returned `http_403_blocked_or_inaccessible`; no body/version can be verified without user review. |
| `https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235458` | ambiguous | needs_user_verification | Blackmagic forum returned `http_403_blocked_or_inaccessible`; no body/version can be verified without user review. |
| `https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235208` | ambiguous | needs_user_verification | Blackmagic forum returned `http_403_blocked_or_inaccessible`; no body/version can be verified without user review. |
| `https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=234870` | ambiguous | needs_user_verification | Blackmagic forum returned `http_403_blocked_or_inaccessible`; no body/version can be verified without user review. |
| `https://forum.blackmagicdesign.com/viewtopic.php?f=42&t=235179` | beta | duplicate_existing_evidence | Existing Phase 1F evidence row already counts this Public Beta 1 Magic Mask crash report. |
| `https://www.reddit.com/r/davinciresolve/comments/1sl3sqn/davinci_resolve_21_crashes_instantly_on_macbook/` | stable | needs_user_verification | Candidate maps to stable 21, but fetched body was too short for verification; do not count snippet/shell content. |
| `https://www.reddit.com/r/davinciresolve/comments/1skz03l/davinci_resolve_21_problem/` | stable | needs_user_verification | Candidate maps to stable 21, but fetched body was too short for verification; do not count snippet/shell content. |
| `https://www.reddit.com/r/davinciresolve/comments/1sn39qf/davinci_resolve_failed_to_decode_video_frame_when/` | beta | duplicate_existing_evidence | Existing Phase 1F evidence row already counts this Public Beta 1 decode/render failure report. |
| `https://www.reddit.com/r/davinciresolve/comments/1sy9fi3/release_of_davinci_resolve_210b2/` | future | future_update_not_current_record | Candidate is for `21 Public Beta 2`; no Phase 1G current generated record should receive it. |
| `https://www.liftgammagain.com/forum/index.php?forums/davinci-resolve.36/` | ambiguous | ambiguous_version | Discovery source only; no specific body-reviewed issue thread or exact stable/Beta 1 version match. |
| `https://creativecow.net/forums/forum/davinci-resolve/` | ambiguous | ambiguous_version | Discovery source only; no specific body-reviewed issue thread or exact stable/Beta 1 version match. |
| `https://www.dpreview.com/forums` | ambiguous | ambiguous_version | Discovery source only; no specific body-reviewed issue thread or exact stable/Beta 1 version match. |
| `https://www.videohelp.com/software/DaVinci-Resolve/version-history` | ambiguous | ambiguous_version | Release metadata only; not user issue report evidence. |

## Cross-Match Check

- Stable candidates are not eligible for the Beta 1 record.
- Beta 1 duplicates are not eligible for the stable record.
- Beta 2 is marked `future_update_not_current_record`.
- Ambiguous/discovery sources are not eligible for either current record until a specific body-reviewed thread maps exactly to `21` or `21 Public Beta 1`.
