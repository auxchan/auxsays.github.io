# DOL Initial Claims freshness and fallback report

Forensic date: 2026-09-14

Status: **official fallback succeeded; primary structured XML remains stale.**

The primary `r539cyNational` XML still contains blank claims cells after
2026-08-15 and remains `STALE` under the unchanged 336-hour threshold. Its
health warning was not disabled or relabeled. Report-run time remains separate
from semantic observation identity.

Because the primary was stale, the collector triggered the bounded official
DOL release fallback. The official USDOL distribution release had deterministic
HTML text, a publication timestamp, and the exact seasonally adjusted Initial
Claims sentence; no OCR, LLM extraction, news article, FRED, or third-party
substitute was used.

The same failover boundary also covers a bounded-retrieval or primary-parser
failure. In that case the primary method remains explicitly `BROKEN`; a current,
fully validated official release may supply the canonical Initial Claims rows
without changing that primary-method diagnosis. Regression coverage exercises
this path through collection and the later repair pass.

| Method | Status | Newest period | Result |
|---|---|---|---|
| Primary official XML | `STALE` | 2026-08-15 | History lane retained; warning active |
| Official weekly release fallback | `CURRENT` | 2026-09-05 | 206,000 advance; 207,000 revised for 2026-08-29 |
| Official archive | `NOT_NEEDED` | n/a | Third governed method when required |
| Overall | `SUCCESS_WITH_PRIMARY_STALE` | 2026-09-05 | Current observation available without hiding primary degradation |

The fallback stores the official URL, content hash, semantic release identity,
publication time, retrieval time, parser version, and method. Semantic
observation identity is based on series, period, and value, so retrieval URL,
method, or transport time does not manufacture a revision. The accepted
209,000 -> 212,000 chain for 2026-08-08 remains intact.
