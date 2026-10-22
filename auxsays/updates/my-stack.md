---
layout: aux-base
title: My Patch Stack
description: The patch status of the software you actually use — watched products, their latest tracked patch, the AUXSAYS decision, and what needs attention.
permalink: /updates/my-stack/
---
{%- comment -%}
  MY PATCH STACK. A personal dashboard over the visitor's existing watchlist.

  It reads `auxsays.patchWatchlist.v1` — the SAME browser key the Watch controls write — and adds no
  second persistence contract, no account and no backend.

  DATA IS PRE-RENDERED, NOT FETCHED. Jekyll builds one compact entry per tracked product below and
  the client picks out the watched ones. Nothing here fetches the site at runtime, and the payload
  carries only the fields the dashboard shows rather than serialising 1,200 records.

  RECORD SELECTION mirrors `_includes/patch-latest-signals.html`: the newest DATED record per
  product, skipping archived ones. That include exists precisely so a "latest decision per product"
  view does not invent its own rule. It is deliberately NOT the homepage's meaningful-plus-score
  selection: the homepage is choosing what to feature out of everything, while this page already
  knows which products the reader cares about and only has to answer "what is the latest on this
  one". Where the two disagree, this page shows the newer record and the homepage shows the more
  eventful one; both link to the same product history.

  VERDICT AND EVIDENCE derivation mirrors `_includes/patch-table-row.html` exactly, including the
  official-only-at-zero-reports override, so a product shows the same decision here, on its history
  table and on the patch page. MONITORING comes from `_includes/monitoring-status.html`, which
  declares itself the single source of truth for that axis; it is captured and discarded so this
  page reuses the status without re-rendering the widget.
{%- endcomment -%}

{%- assign stack_updates = site.pages | where: "update_entry", true | sort: "update_published_at" | reverse -%}
{%- assign stack_seen = '|' -%}
{%- capture stack_payload -%}
[
{%- for product in site.data.patch_products -%}
  {%- assign p_id = product.id | default: product.product_id -%}
  {%- if p_id and p_id != '' -%}
    {%- assign chosen = nil -%}
    {%- for item in stack_updates -%}
      {%- if chosen == nil and item.product_id == p_id and item.update_published_at and item.update_status != 'archived' -%}
        {%- assign chosen = item -%}
      {%- endif -%}
    {%- endfor -%}

    {%- if stack_seen != '|' -%},{%- endif -%}
    {%- assign stack_seen = stack_seen | append: p_id | append: '|' -%}
    {
    "id": {{ p_id | jsonify }},
    "name": {{ product.product_name | default: p_id | jsonify }},
    "hist": {{ product.product_url | default: '' | jsonify }}
    {%- if chosen -%}
      {%- comment -%} Same fallback chain as patch-table-row.html, in the same order. {%- endcomment -%}
      {%- assign verdict_text = chosen.quick_verdict -%}
      {%- assign decision_label = chosen.update_decision_label | default: '' | strip -%}
      {%- if decision_label == '' and chosen.update_consensus_summary contains ':' -%}
        {%- assign decision_label = chosen.update_consensus_summary | split: ':' | first | strip -%}
      {%- elsif decision_label == '' and verdict_text contains ':' -%}
        {%- assign decision_label = verdict_text | split: ':' | first | strip -%}
      {%- elsif decision_label == '' -%}
        {%- assign decision_label = 'INSUFFICIENT DATA' -%}
      {%- endif -%}
      {%- assign report_count_num = chosen.update_report_count | default: 0 | plus: 0 -%}
      {%- assign is_official_only = false -%}
      {%- if chosen.evidence_state == 'official_only' or chosen.evidence_state_label == 'Official source only' -%}{%- assign is_official_only = true -%}{%- endif -%}
      {%- if is_official_only and report_count_num == 0 -%}{%- assign decision_label = 'INSUFFICIENT DATA' -%}{%- endif -%}
      {%- assign vkey = decision_label | upcase -%}
      {%- assign verdict_rank = 99 -%}
      {%- if vkey contains 'AVOID' -%}{%- assign verdict_rank = 0 -%}
      {%- elsif vkey contains 'WAIT' -%}{%- assign verdict_rank = 1 -%}
      {%- elsif vkey contains 'TEST FIRST' -%}{%- assign verdict_rank = 2 -%}
      {%- elsif vkey contains 'SECURITY UPDATE' -%}{%- assign verdict_rank = 3 -%}
      {%- elsif vkey contains 'SAFE ENOUGH' -%}{%- assign verdict_rank = 4 -%}
      {%- elsif vkey contains 'OFFICIAL ONLY' -%}{%- assign verdict_rank = 5 -%}
      {%- elsif vkey contains 'INSUFFICIENT DATA' -%}{%- assign verdict_rank = 6 -%}
      {%- elsif vkey contains 'MANUAL WATCH' -%}{%- assign verdict_rank = 7 -%}
      {%- endif -%}
      {%- assign ev_state = chosen.evidence_state | default: 'insufficient_data' | downcase | replace: '-', '_' -%}
      {%- assign ev_label = chosen.evidence_state_label | default: ev_state | replace: '_', ' ' | capitalize -%}
      {%- if ev_state == 'pilot_sample' or ev_state == 'static_sample' or ev_state == 'pilot_initial_sample' or ev_state == 'static_initial_sample' -%}{%- assign ev_label = 'Verified reports' -%}
      {%- elsif ev_state == 'official_only' -%}{%- assign ev_label = 'Official source only' -%}
      {%- elsif ev_state == 'consensus_live' -%}{%- assign ev_label = 'Live consensus' -%}
      {%- elsif ev_state == 'insufficient_data' -%}{%- assign ev_label = 'Insufficient data' -%}
      {%- endif -%}
      {%- capture mon_discard -%}{%- include monitoring-status.html mode='cell' product_id=chosen.product_id version=chosen.update_version target_build=chosen.target_build published_at=chosen.update_published_at report_count=chosen.update_report_count -%}{%- endcapture -%}
      ,"href": {{ chosen.url | jsonify }}
      ,"ver": {{ chosen.update_version | default: '' | jsonify }}
      ,"date": {{ chosen.update_published_at | date: "%b %d, %Y" | jsonify }}
      ,"verdict": {{ decision_label | jsonify }}
      ,"rank": {{ verdict_rank }}
      ,"ev": {{ ev_label | jsonify }}
      ,"n": {{ report_count_num }}
      ,"checked": {{ chosen.evidence_last_checked | default: '' | date: "%b %d, %Y" | jsonify }}
      ,"mon": {{ mon_status | default: '' | jsonify }}
      ,"oa": {{ chosen.official_active_issue_count | default: 0 | plus: 0 }}
      ,"os": {{ chosen.official_safeguard_hold_count | default: 0 | plus: 0 }}
    {%- endif -%}
    {%- comment -%}
      The version picker offers records AUXSAYS already tracks, newest first, so what a reader
      saves is a real patch identity -- version plus build where the product has one -- rather than
      free text a parser would have to guess at.

      Bounded on purpose: the newest 24 per product, with a count of what lies beyond and a link to
      the full history, where any older record can still be claimed from its own patch page. GitHub
      alone has 284 records; serialising every one of them onto this page to populate a dropdown
      nobody scrolls would be the wrong trade.

      `beta` carries the only channel signal this repo has. Three records in 1,200 set a channel
      label, so the version string is it -- the same textual signal lib/patch_decision.version_is_beta
      uses. It exists so a stable reader is never told a newer BETA is an update.

      Tuple shape, fixed at 11 and pinned exactly by the suite:
        [0] version  [1] build  [2] date  [3] url  [4] beta
        [5] verdict  [6] rank   [7] reports  [8] evidence label
        [9] official active issue count      [10] official notes captured (0/1)
      0-4 drive the version picker; 5-10 exist so an upgrade path can show what AUXSAYS already
      says about each release it lists, WITHOUT a second verdict computation on the client.
    {%- endcomment -%}
    {%- assign p_count = 0 -%}
    {%- capture p_recs -%}
      {%- for rec in stack_updates -%}
        {%- if rec.product_id == p_id and rec.update_published_at and rec.update_status != 'archived' -%}
          {%- assign p_count = p_count | plus: 1 -%}
          {%- if p_count <= 24 -%}
            {%- if p_count > 1 -%},{%- endif -%}
            {%- assign rec_ver_key = rec.update_version | downcase -%}
            {%- assign rec_ver_first = rec.update_version | slice: 0 -%}
            {%- assign rec_is_beta = 0 -%}
            {%- comment -%}
              Only read the version string as a channel signal when it actually looks like a
              version. For Figma and GitHub `update_version` is a changelog HEADLINE, so
              "Preview what's inside folders" and "See AI credit usage in betas" were being
              flagged as betas -- which then suppressed UPDATE AVAILABLE for everything below
              them. "21 Public Beta 1" still matches; a sentence does not.
            {%- endcomment -%}
            {%- if rec_ver_first contains '0' or rec_ver_first contains '1' or rec_ver_first contains '2' or rec_ver_first contains '3' or rec_ver_first contains '4' or rec_ver_first contains '5' or rec_ver_first contains '6' or rec_ver_first contains '7' or rec_ver_first contains '8' or rec_ver_first contains '9' -%}
              {%- if rec_ver_key contains 'beta' or rec_ver_key contains 'preview' or rec_ver_key contains 'insider' -%}
                {%- assign rec_is_beta = 1 -%}
              {%- endif -%}
            {%- endif -%}
            {%- if rec.release_channel_label -%}{%- assign rec_is_beta = 1 -%}{%- endif -%}
            {%- comment -%}
              PER-RELEASE DECISION DATA, so an upgrade path can show what AUXSAYS already says about
              each release between the reader's version and the target.

              Liquid `assign` has NO loop scope -- every variable here is global and survives into
              the next iteration -- so each one is reset unconditionally before it is used. A
              conditional assignment alone would leak the previous record's verdict onto a record
              that has none.

              The derivation is the SAME fallback chain the `chosen` block above uses, which is
              itself the chain from `_includes/patch-table-row.html`. It is a second copy, which is
              a real cost; what stops the copies drifting is that the suite computes the expected
              verdict INDEPENDENTLY in Python from the corpus and applies it to EVERY record here,
              not just the one the card shows.
            {%- endcomment -%}
            {%- assign rec_verdict = rec.update_decision_label | default: '' | strip -%}
            {%- if rec_verdict == '' and rec.update_consensus_summary contains ':' -%}
              {%- assign rec_verdict = rec.update_consensus_summary | split: ':' | first | strip -%}
            {%- elsif rec_verdict == '' and rec.quick_verdict contains ':' -%}
              {%- assign rec_verdict = rec.quick_verdict | split: ':' | first | strip -%}
            {%- elsif rec_verdict == '' -%}
              {%- assign rec_verdict = 'INSUFFICIENT DATA' -%}
            {%- endif -%}
            {%- assign rec_n = rec.update_report_count | default: 0 | plus: 0 -%}
            {%- assign rec_official_only = false -%}
            {%- if rec.evidence_state == 'official_only' or rec.evidence_state_label == 'Official source only' -%}{%- assign rec_official_only = true -%}{%- endif -%}
            {%- if rec_official_only and rec_n == 0 -%}{%- assign rec_verdict = 'INSUFFICIENT DATA' -%}{%- endif -%}
            {%- assign rec_vkey = rec_verdict | upcase -%}
            {%- assign rec_rank = 99 -%}
            {%- if rec_vkey contains 'AVOID' -%}{%- assign rec_rank = 0 -%}
            {%- elsif rec_vkey contains 'WAIT' -%}{%- assign rec_rank = 1 -%}
            {%- elsif rec_vkey contains 'TEST FIRST' -%}{%- assign rec_rank = 2 -%}
            {%- elsif rec_vkey contains 'SECURITY UPDATE' -%}{%- assign rec_rank = 3 -%}
            {%- elsif rec_vkey contains 'SAFE ENOUGH' -%}{%- assign rec_rank = 4 -%}
            {%- elsif rec_vkey contains 'OFFICIAL ONLY' -%}{%- assign rec_rank = 5 -%}
            {%- elsif rec_vkey contains 'INSUFFICIENT DATA' -%}{%- assign rec_rank = 6 -%}
            {%- elsif rec_vkey contains 'MANUAL WATCH' -%}{%- assign rec_rank = 7 -%}
            {%- endif -%}
            {%- assign rec_ev_state = rec.evidence_state | default: 'insufficient_data' | downcase | replace: '-', '_' -%}
            {%- assign rec_ev = rec.evidence_state_label | default: rec_ev_state | replace: '_', ' ' | capitalize -%}
            {%- if rec_ev_state == 'pilot_sample' or rec_ev_state == 'static_sample' or rec_ev_state == 'pilot_initial_sample' or rec_ev_state == 'static_initial_sample' -%}{%- assign rec_ev = 'Verified reports' -%}
            {%- elsif rec_ev_state == 'official_only' -%}{%- assign rec_ev = 'Official source only' -%}
            {%- elsif rec_ev_state == 'consensus_live' -%}{%- assign rec_ev = 'Live consensus' -%}
            {%- elsif rec_ev_state == 'insufficient_data' -%}{%- assign rec_ev = 'Insufficient data' -%}
            {%- endif -%}
            {%- comment -%}
              OFFICIAL NOTES: a FLAG, never the prose.

              `official_patch_notes_body` is raw vendor markdown, not a structured change list. Of
              the 213 records this payload carries, 201 have a body that passes the pollution gate
              but only 43 contain any bullet lines at all -- and those carry a median of 44 bullets,
              some of which are the vendor's KNOWN ISSUES rather than changes, with markdown links
              embedded in the text. Sampling two of them under a heading saying "official changes"
              would be asserting a summary the record does not make.

              So this carries only what the record structurally states: that official notes were
              captured and are renderable, by the SAME `official_body_polluted` gate `aux-update.html`
              uses to decide whether to render them at all. The notes themselves stay on the patch
              page, one link away.
            {%- endcomment -%}
            {%- assign rec_body = rec.official_patch_notes_body | default: '' | strip -%}
            {%- assign rec_notes = 0 -%}
            {%- if rec_body != '' -%}
              {%- assign rec_body_key = rec_body | downcase -%}
              {%- assign rec_polluted = false -%}
              {%- if rec_body_key contains 'showvotefeedback' or rec_body_key contains 'function(' or rec_body_key contains 'document.' or rec_body_key contains 'window.' or rec_body_key contains 'queryselector' or rec_body_key contains 'content-rating-buttons' -%}
                {%- assign rec_polluted = true -%}
              {%- endif -%}
              {%- if rec_polluted == false -%}{%- assign rec_notes = 1 -%}{%- endif -%}
            {%- endif -%}
            [{{ rec.update_version | default: '' | jsonify }},{{ rec.target_build | default: '' | jsonify }},{{ rec.update_published_at | date: "%Y-%m-%d" | jsonify }},{{ rec.url | jsonify }},{{ rec_is_beta }},{{ rec_verdict | jsonify }},{{ rec_rank }},{{ rec_n }},{{ rec_ev | jsonify }},{{ rec.official_active_issue_count | default: 0 | plus: 0 }},{{ rec_notes }}]
          {%- endif -%}
        {%- endif -%}
      {%- endfor -%}
    {%- endcapture -%}
    ,"recs": [{{ p_recs }}]
    {%- assign p_more = p_count | minus: 24 -%}
    ,"more": {% if p_more > 0 %}{{ p_more }}{% else %}0{% endif %}
    }
  {%- endif -%}
{%- endfor -%}
]
{%- endcapture -%}

{%- comment -%}
  `jsonify` escapes JSON, not HTML: a literal `</script>` inside any string would close this element
  early, JSON.parse would throw, and the client's fail-soft would confidently report an empty stack
  to someone who has products. Version strings are sometimes free-text vendor prose, so this is a
  real input, not a hypothetical one.

  Neutralising every `</` rather than the exact lowercase string `</script>`: the HTML tokenizer
  matches an end tag CASE-INSENSITIVELY, so `</SCRIPT>` or `</ScRiPt>` in vendor text would close
  this element while sailing past an exact-match replace. `\/` is a valid JSON escape for `/`, so
  JSON.parse returns the identical string and nothing downstream can tell the difference.
{%- endcomment -%}
<script type="application/json" id="patch-stack-data">{{ stack_payload | replace: '</', '<\/' }}</script>

<section class="patch-shell patch-stack-shell">
  <section class="panel patch-hero reveal-up">
    <div class="eyebrow">Personal patch intelligence</div>
    <h1>My Patch Stack</h1>
    <p>The patch status of the software you actually use. Your list is stored in this browser only —
      no account, no sign-in, nothing sent anywhere.</p>
    <p class="patch-stack-live visually-hidden" data-stack-live role="status" aria-live="polite"></p>
    <p class="patch-stack-strip" data-stack-strip hidden>
      <span><strong data-stack-count-watched>0</strong> watched products</span>
      <span><strong data-stack-count-attention>0</strong> need attention</span>
      <span><strong data-stack-count-evidence>0</strong> with report evidence</span>
      <span><strong data-stack-count-versions>0</strong> versions set</span>
      {%- comment -%}
        "have newer tracked releases", never "updates required": the current AUXSAYS verdict on
        several of those releases is WAIT, and a strip that counts them as required work would be
        telling the reader the opposite of the decision on the card below it.
      {%- endcomment -%}
      <span><strong data-stack-count-newer>0</strong> have newer tracked releases</span>
    </p>
  </section>

  <section class="panel patch-stack-empty" data-stack-empty hidden>
    <h2>Your Patch Stack is empty.</h2>
    <p>Watch the software you use and its latest patch status appears here — the current AUXSAYS
      decision, how much evidence sits behind it, and when it was last checked.</p>
    <p class="patch-card-links">
      <a class="patch-source-link patch-source-link--primary" href="{{ '/updates/' | relative_url }}">Browse the Patch Feed →</a>
    </p>
    <div class="patch-stack-chooser" data-stack-chooser>
      <h3>Or start from the software AUXSAYS tracks</h3>
      <div class="patch-stack-chooser-tags" data-stack-chooser-tags></div>
    </div>
  </section>

  <noscript>
    <p class="patch-stack-none">My Patch Stack reads your watched products from this browser, which
      needs JavaScript. The <a href="{{ '/updates/' | relative_url }}">Patch Feed</a> works without it.</p>
  </noscript>

  <section class="patch-stack-body" data-stack-body hidden>
    <section class="panel patch-stack-attention">
      <div class="section-head">
        <div class="eyebrow">Needs attention</div>
        <h2>Watched software with an elevated signal</h2>
      </div>
      <p class="patch-stack-none" data-stack-attention-none>Nothing in your watched stack currently
        requires elevated attention.</p>
      <div class="patch-stack-grid" data-stack-attention-grid></div>
    </section>

    <section class="panel patch-stack-all">
      <div class="section-head">
        <div class="eyebrow">Your products</div>
        <h2>Everything you watch</h2>
      </div>
      <div class="patch-stack-grid" data-stack-all-grid></div>
    </section>
  </section>
</section>
