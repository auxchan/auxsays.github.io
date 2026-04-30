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
    </article>

    <article class="methodology-card">
      <h2>Official source classification</h2>
      <p>Official vendor pages are classified before display. A release-notes page, fixed-issue list, security advisory, changelog, vendor blog, “What’s New” article, download portal, and official community announcement are not treated as the same evidence type.</p>
      <p>AUXSAYS should only label a section as <strong>Official Release Notes</strong> when the captured source is classified as release notes, fixed issues, a security advisory, or a changelog. Feature summaries and vendor announcements remain official, but they are labeled as summaries or announcements.</p>
    </article>

    <article class="methodology-card">
      <h2>Community consensus</h2>
      <p>Community consensus is separate from official ingestion. It is not treated as live unless the page explicitly says <strong>Consensus live</strong>. Pilot samples are labeled as samples and should not be read as live telemetry.</p>
      <p>When consensus collection is implemented, every confirmed patch-specific report will count equally. Official forums, dedicated forums, Reddit, GitHub Issues, or other public sources may be labeled by source type for auditability, but source type does not multiply or discount the report.</p>
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
        <div><dt>Consensus live</dt><dd>Confirmed patch-specific reports are actively refreshed by a consensus pipeline.</dd></div>
        <div><dt>Official only</dt><dd>An official source has been captured, but no confirmed patch-specific community reports are counted yet.</dd></div>
        <div><dt>Pilot sample</dt><dd>The page contains manually encoded or previously captured confirmed patch-specific report data. It is not live telemetry.</dd></div>
        <div><dt>Insufficient data</dt><dd>AUXSAYS has not captured enough official or community evidence to support a verdict beyond a placeholder state.</dd></div>
      </dl>
    </article>
  </section>

  <section class="panel methodology-source-health reveal-up reveal-delay-2">
    <div class="eyebrow">Source audit</div>
    <h2>Current official-ingestion source health</h2>
    <p>This is a static audit snapshot produced from the ingestion config and the latest GitHub Actions state file. It is meant to show whether official-source monitoring is healthy, degraded, failing, staged, or disabled. It is not a backend service and it does not represent live community consensus.</p>

    {% assign healthy_sources = site.data.source_health | where: "status", "Healthy" %}
    {% assign degraded_sources = site.data.source_health | where: "status", "Degraded" %}
    {% assign idle_healthy_sources = site.data.source_health | where: "status", "Idle healthy" %}
    {% assign failing_sources = site.data.source_health | where: "status", "Failing" %}
    {% assign staged_sources = site.data.source_health | where: "status", "Staged" %}
    <div class="source-health-summary" aria-label="Source health totals">
      <div><strong>{{ healthy_sources.size }}</strong><span>Healthy</span></div>
      <div><strong>{{ idle_healthy_sources.size }}</strong><span>Idle healthy</span></div>
      <div><strong>{{ degraded_sources.size }}</strong><span>Degraded</span></div>
      <div><strong>{{ failing_sources.size }}</strong><span>Failing</span></div>
      <div><strong>{{ staged_sources.size }}</strong><span>Staged</span></div>
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
