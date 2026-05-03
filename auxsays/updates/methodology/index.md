---
layout: aux-base
title: AUXSAYS Patch Feed Methodology
description: How AUXSAYS separates official-source patch ingestion from confirmed patch-specific community consensus.
permalink: /updates/methodology/
---
<section class="patch-shell methodology-page">
  <section class="panel patch-hero reveal-up">
    <div class="eyebrow">Methodology</div>
    <h1 class="patch-title">Patch Feed evidence standards</h1>
    <p class="patch-subtitle">AUXSAYS is being built as an official-first patch intelligence layer. This page explains what is live now, what is still scaffolding, and how patch-specific reports will be counted.</p>
  </section>

  <section class="panel methodology-grid reveal-up reveal-delay-1">
    <article class="methodology-card methodology-card--primary">
      <h2>What AUXSAYS currently tracks</h2>
      <p>AUXSAYS tracks creator-critical companies, their software/products, and specific patch or release records. Official vendor sources are treated as the factual baseline for what changed.</p>
      <ul>
        <li>Company pages organize software under the vendor or project.</li>
        <li>Software pages show release history and monitoring rules.</li>
        <li>Patch pages show official notes, evidence state, and any confirmed patch-specific report sample.</li>
      </ul>
    </article>

    <article class="methodology-card">
      <h2>Official-source ingestion</h2>
      <p>Official-source ingestion captures releases from vendor changelogs, RSS feeds, GitHub releases, or official release pages. This pipeline is active for selected sources and runs through GitHub Actions.</p>
      <p>Official ingestion does not prove a patch is safe. It only records that an official update exists and preserves the available release note details.</p>
      <p><strong>Official source checked</strong> means AUXSAYS contacted the vendor source or feed. It does not mean the page verdict, community evidence, or report count changed.</p>
    </article>

    <article class="methodology-card">
      <h2>Official source classification</h2>
      <p>Official vendor pages are classified before display. A release-notes page, fixed-issue list, security advisory, changelog, vendor blog, “What’s New” article, download portal, and official community announcement are not treated as the same evidence type.</p>
      <p>AUXSAYS should only label a section as <strong>Official Release Notes</strong> when the captured source is classified as release notes, fixed issues, a security advisory, or a changelog. Feature summaries and vendor announcements remain official, but they are labeled as summaries or announcements.</p>
      <p><strong>Official notes checked</strong> means AUXSAYS attempted to capture official body text. A linked source can still show a missing-body note when extraction fails or the source is not a structured changelog.</p>
    </article>

    <article class="methodology-card">
      <h2>Community consensus</h2>
      <p>Community consensus is separate from official ingestion. It is not treated as live unless the page explicitly says <strong>Live consensus</strong>. Verified reports are manually confirmed patch-specific reports or previously captured structured reports; they should not be read as continuous community scraping.</p>
      <p>When a live collector exists, every confirmed patch-specific report will count equally. Official forums, dedicated forums, Reddit, GitHub Issues, or other public sources may be labeled by source type for auditability, but source type does not multiply or discount the report.</p>
    </article>

    <article class="methodology-card">
      <h2>Manual tracking</h2>
      <p>Some priority products are watched manually while an adapter or collector is incomplete. Manual watch means AUXSAYS is tracking the source intentionally, but it does not mean automated official ingestion or live report scraping is active.</p>
    </article>

    <article class="methodology-card">
      <h2>Consensus audit</h2>
      <p>The consensus audit checks whether generated patch pages that show confirmed reports are backed by structured evidence rows. It can identify stale or manually encoded counts, but it does not collect new reports from public communities.</p>
      <p><strong>Evidence checked</strong> is separate from official-source checks. It should only move when structured community/report evidence is reviewed or collected. Live consensus is not active unless a real evidence collector is running.</p>
      <p>AUXSAYS may run narrow manual pilot collectors, such as a GitHub Issues pilot for a single OBS Studio patch. Those pilots are structured evidence collection, not live consensus.</p>
    </article>

    <article class="methodology-card">
      <h2>Record freshness</h2>
      <p><strong>Record updated</strong> means the generated patch page materially changed. Older records may show a legacy record date until the refreshed ingestion path writes the newer source and body-check fields.</p>
      <p>Source checked, official notes checked, record updated, and evidence checked are separate timestamps. One timestamp should not be read as proof that the others changed.</p>
    </article>

    <article class="methodology-card">
      <h2>What counts as a confirmed patch-specific report</h2>
      <ul>
        <li>The report/comment itself names the exact patch, version, or update.</li>
        <li>Or the parent thread/page title names the exact patch, version, or update.</li>
        <li>If the parent thread is patch-specific, replies inside that thread count unless the reply clearly shifts to another version or unrelated issue.</li>
      </ul>
    </article>

    <article class="methodology-card methodology-card--warning">
      <h2>What does not count</h2>
      <ul>
        <li>Generic complaints about the software.</li>
        <li>Posts that only say “after the update” without a patch-specific parent thread.</li>
        <li>Mentions that cannot be tied to the exact version being scored.</li>
        <li>Reports that explicitly refer to another version, driver, operating system update, or unrelated plug-in issue.</li>
      </ul>
      <p>Low-context reports are excluded entirely. They are not downweighted or used as weak signals.</p>
    </article>

    <article class="methodology-card">
      <h2>Evidence states</h2>
      <dl class="methodology-definition-list">
        <div><dt>Live consensus</dt><dd>Confirmed patch-specific reports are actively refreshed by a consensus pipeline.</dd></div>
        <div><dt>Official source only</dt><dd>An official source has been captured, but no confirmed patch-specific community reports are counted yet.</dd></div>
        <div><dt>Verified reports</dt><dd>The page contains manually encoded or previously captured confirmed patch-specific report data. Check the evidence freshness line before treating it as current.</dd></div>
        <div><dt>Insufficient data</dt><dd>AUXSAYS has not captured enough official or community evidence to support a verdict beyond a placeholder state.</dd></div>
      </dl>
    </article>
  </section>

  <section class="panel methodology-source-health reveal-up reveal-delay-2">
    <div class="eyebrow">Source audit</div>
    <h2>Current official-ingestion source health</h2>
    <p>This is a static audit snapshot produced from the ingestion config and the latest GitHub Actions state file. It is meant to show whether official-source monitoring is active, manual watch, needs an adapter, disabled, in error, or unknown. It is not a backend service and it does not represent live community consensus.</p>

    {% assign active_sources = site.data.source_health | where: "status", "Active" %}
    {% assign manual_watch_sources = site.data.source_health | where: "status", "Manual watch" %}
    {% assign needs_adapter_sources = site.data.source_health | where: "status", "Needs adapter" %}
    {% assign disabled_sources = site.data.source_health | where: "status", "Disabled" %}
    {% assign error_sources = site.data.source_health | where: "status", "Error" %}
    {% assign unknown_sources = site.data.source_health | where: "status", "Unknown" %}
    <div class="source-health-summary" aria-label="Source health totals">
      <div><strong>{{ active_sources.size }}</strong><span>Active</span></div>
      <div><strong>{{ manual_watch_sources.size }}</strong><span>Manual watch</span></div>
      <div><strong>{{ needs_adapter_sources.size }}</strong><span>Needs adapter</span></div>
      <div><strong>{{ disabled_sources.size }}</strong><span>Disabled</span></div>
      <div><strong>{{ error_sources.size }}</strong><span>Error</span></div>
      <div><strong>{{ unknown_sources.size }}</strong><span>Unknown</span></div>
    </div>

    <div class="source-health-table" role="table" aria-label="AUXSAYS official ingestion source-health snapshot">
      <div class="source-health-row source-health-row--head" role="row">
        <span>Source</span><span>Software</span><span>Status</span><span>Last run</span><span>Records</span><span>Capabilities</span><span>Last error</span>
      </div>
      {% for item in site.data.source_health %}
      <div class="source-health-row source-health-row--{{ item.status | downcase | replace: ' ', '-' }}" role="row">
        <span class="source-health-id"><strong>{{ item.source_id }}</strong><em>{{ item.company }}</em></span>
        <span>{{ item.software }}<small>{{ item.adapter_type }}</small></span>
        <span><mark class="source-health-status source-health-status--{{ item.status | downcase | replace: ' ', '-' }}">{{ item.status }}</mark><small>{{ item.status_detail }}</small></span>
        <span>{% if item.last_checked != blank %}{{ item.last_checked }}{% else %}Not checked{% endif %}<small>{% if item.polling_frequency != blank %}Target: {{ item.polling_frequency }}{% endif %}</small></span>
        <span>{{ item.last_records_fetched }} fetched / {{ item.last_records_written }} written<small>{{ item.last_records_skipped }} skipped · {{ item.consecutive_failures }} failures</small></span>
        <span class="source-health-capabilities">
          {% if item.capabilities.release_notes %}<b>notes</b>{% endif %}
          {% if item.capabilities.version %}<b>version</b>{% endif %}
          {% if item.capabilities.download_url %}<b>download</b>{% endif %}
          {% if item.capabilities.file_size %}<b>size</b>{% endif %}
          {% if item.capabilities.checksum %}<b>checksum</b>{% endif %}
          {% if item.capabilities.known_issues %}<b>known issues</b>{% endif %}
        </span>
        <span>{% if item.last_error_display != blank and item.last_error_display != 'None' %}{{ item.last_error_display }}{% else %}None{% endif %}</span>
      </div>
      {% endfor %}
    </div>
  </section>
</section>
