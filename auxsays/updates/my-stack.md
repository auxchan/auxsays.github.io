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
{%- endcomment -%}
<script type="application/json" id="patch-stack-data">{{ stack_payload | replace: '</script>', '<\/script>' }}</script>

<section class="patch-shell patch-stack-shell">
  <section class="panel patch-hero reveal-up">
    <div class="eyebrow">Personal patch intelligence</div>
    <h1>My Patch Stack</h1>
    <p>The patch status of the software you actually use. Your list is stored in this browser only —
      no account, no sign-in, nothing sent anywhere.</p>
    <p class="patch-stack-strip" data-stack-strip hidden>
      <span><strong data-stack-count-watched>0</strong> watched products</span>
      <span><strong data-stack-count-attention>0</strong> need attention</span>
      <span><strong data-stack-count-evidence>0</strong> with report evidence</span>
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
