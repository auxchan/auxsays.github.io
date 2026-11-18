# Product-level issue signals: the contract

Status: **defined, not built** (AUX-102). No collector, workflow or data file produces a product-level
signal today, and the coverage projection reports this capability as not monitored for every product.
This file is the contract the first implementation must satisfy. Nothing here changes how patch evidence,
verdicts or consensus work.

## What a product-level signal is

An early, product-scoped indication that something may be wrong: for example many users of one driver
family reporting the same symptom before anyone has tied it to an exact release, or a vendor status
notice. It is the fourth coverage capability, separate from official release detection, community report
discovery and patch consensus. The NVIDIA case that prompted it (excessive background SSD writes reported
on NVIDIA's own forum about ten days before the first press story) is the shape it is for.

## Requirements

A product-level signal MUST:

1. **Identify the exact product, and the version when it is known.** A signal that names a version
   carries it; a signal that does not stays product-scoped. Products that share version numbers (for
   example NVIDIA Game Ready and Studio drivers) are different products: a shared number never moves a
   signal from one to the other, and an explicit mention of the other product vetoes the attribution.
2. **Distinguish reports from confirmed regressions.** "Users report X" and "X is a regression in this
   release" are different states and are stored as different states.
3. **Distinguish community allegations from vendor-confirmed issues.** A vendor's own known-issue or
   status text is recorded as vendor-confirmed; anything else is an allegation until the vendor or the
   existing acceptance authority says otherwise.
4. **Stay uncounted until the existing exact-patch acceptance authority validates it.** A signal is never
   a counted report. It reaches a patch's report count only through the same acceptance rules every
   other report passes.
5. **Not affect an installation verdict or consensus maturity without evidence.** A signal may be shown
   as context; it cannot move a verdict, an evidence state or a live-consensus decision by itself.
6. **Carry its original source links, source-native timestamps, a confidence and a freshness.**
   Timestamps come from the source itself, never from a later summary of it.
7. **Deduplicate automatically.** The same report seen twice, or through two routes, is one signal.
8. **Expire or resolve automatically when the evidence supports it.** A vendor fix, a release that
   supersedes the affected one, or the signal going quiet past its freshness window closes it, by rule.
9. **Never depend on daily manual approval.** Production runs without anyone reviewing it each day.

And one rule over all of them:

**A product-level signal with unknown patch attribution can never silently become a patch-specific
report.** Promotion to a patch requires the exact-patch acceptance authority, explicitly, every time.

## Preconditions

- An official release lane for the product. Signals need exact release identities to attach to; without
  official release records there is nothing for them to become evidence about.
- Lawful sources. A source whose terms or robots rules forbid automated access stays off, and the
  product's coverage label says community reports are not monitored.

## How success will be measured

Release-to-detection delay, first-public-report-to-signal delay, signal accuracy, and whether an issue was
identified before the first major news report. AUXSAYS cannot promise to be first; it can measure these.
