---
layout: aux-base
title: AUXSAYS Patch Feed Methodology
description: What AUXSAYS counts as evidence for a patch update, how official vendor information is kept separate from user reports, and when coverage is limited or out of date.
permalink: /updates/methodology/
---
<section class="patch-shell methodology-page">
  <section class="panel patch-hero reveal-up">
    <div class="eyebrow">Methodology</div>
    <h1 class="patch-title">Patch Feed evidence standards</h1>
    <p class="patch-subtitle">AUXSAYS separates vendor release information from user-reported experiences. Patch pages identify the available evidence, link to relevant sources, and indicate when coverage is limited or outdated. An absence of user reports does not establish that an update is safe. Recommendations are based on the available information and may change as new reports emerge.</p>
  </section>

  <section class="panel methodology-grid reveal-up reveal-delay-1">
    <article class="methodology-card methodology-card--primary">
      <h2>Two kinds of evidence</h2>
      <p>A patch page can carry two different things, and they are never merged into one number:</p>
      <ul>
        <li><strong>Vendor release information</strong> &mdash; what the publisher says changed. This is the factual baseline for what an update contains. It does not establish that the update is safe to install.</li>
        <li><strong>User-reported experiences</strong> &mdash; individual public reports that name the exact release. Every counted report is linked, so you can read the original and judge it yourself.</li>
      </ul>
      <p>A page that carries vendor information and no user reports is labelled as such. That combination is not a safety finding.</p>
    </article>

    <article class="methodology-card">
      <h2>What a patch page shows</h2>
      <ul>
        <li>The exact release identity, including the build where a product ships several builds under one version.</li>
        <li>Links to the vendor source and to every counted report.</li>
        <li>How many confirmed patch-specific reports were counted, including when that number is zero.</li>
        <li>The evidence state, and the dates on which the vendor source and the user-report evidence were last checked.</li>
        <li>Whether coverage for that exact release is limited, incomplete or out of date.</li>
      </ul>
    </article>

    <article class="methodology-card">
      <h2>How official sources are labelled</h2>
      <p>Official vendor pages are not all the same kind of document, and they are not recorded as though they were. Release notes, a fixed-issue list, a security advisory and a changelog are release documentation. A feature summary, a &ldquo;what&rsquo;s new&rdquo; article, a download page, a release-status page and an official announcement are still official, but they are a different kind of document.</p>
      <p>Each official citation on a patch page carries the kind of document it is, next to the link. <strong>That label, not the section heading, is what tells you what the source actually is:</strong> the Official Patch Notes heading is shown for any captured official body text, so a page whose official source is a download page or a release-status page still appears under that heading. Read the citation label.</p>
      <p>An official source can also be linked with a missing-detail note. That means the page was reached but its body text could not be captured, and it is recorded rather than hidden.</p>
    </article>

    <article class="methodology-card">
      <h2>What counts as a confirmed report</h2>
      <ul>
        <li>The report or comment names the exact patch, version or update.</li>
        <li>Or the parent thread or page title names the exact patch, version or update.</li>
        <li>Where the parent thread is specific to one release, replies inside that thread count, unless a reply clearly moves to another version or an unrelated issue.</li>
      </ul>
      <p>Every confirmed report carries equal weight. Where a report was published does not multiply it and does not discount it.</p>
    </article>

    <article class="methodology-card methodology-card--warning">
      <h2>What does not count</h2>
      <ul>
        <li>General complaints about the software.</li>
        <li>Posts that only say &ldquo;after the update&rdquo; with no release-specific parent thread.</li>
        <li>Mentions that cannot be tied to the exact version on the page.</li>
        <li>Reports that clearly refer to a different version, a driver, an operating-system update or an unrelated add-on.</li>
      </ul>
      <p>Reports with too little context are excluded completely. They are not counted at reduced weight and they are not used as a weak signal.</p>
    </article>

    <article class="methodology-card">
      <h2>Evidence states</h2>
      <dl class="methodology-definition-list">
        <div><dt>Official source only</dt><dd>A vendor source has been captured. No confirmed patch-specific user reports are counted for this release. This is the most common state on the site, and it is not a safety finding.</dd></div>
        <div><dt>Verified reports</dt><dd>The page carries confirmed patch-specific reports that were captured earlier. Check the evidence date on the page before treating them as current.</dd></div>
        <div><dt>Live consensus</dt><dd>The release&rsquo;s confirmed patch-specific user reports have reached the High evidence-strength level, and the community collection for that exact release is running and healthy. It is withdrawn automatically when that collection stops, fails or goes stale. A vendor&rsquo;s own release notes never count toward it.</dd></div>
        <div><dt>Insufficient data</dt><dd>There is not enough vendor or user evidence to support anything beyond a placeholder state.</dd></div>
      </dl>
      <p>No state means an update is safe. &ldquo;Official source only&rdquo; and &ldquo;Insufficient data&rdquo; both mean the user-report picture for that release is empty or thin, not that it is clear.</p>
    </article>

    <article class="methodology-card">
      <h2>When coverage is limited or outdated</h2>
      <p>Report collection is not exhaustive and it is not continuous. For any given release it may be incomplete, out of date, or not running at all. Each patch page states the collection position for that exact release. Where there is collection history for that exact release, the page also names each source family it checked and the result of each check; where there is none, the page is labelled Official source only and names no sources.</p>
      <p>A check can complete, complete and find nothing, complete only partly, return a low-confidence result, be refused by the source, fail with an error, be out of date, need manual review, or not be running at all. Some sources are no longer called: where a source refused request after request over a sustained period, AUXSAYS stopped calling it rather than spending every cycle timing out against it, and the patch page says so for that source. Those sources are kept and can be restored if the source starts answering again.</p>
      <p><strong>None of those outcomes is evidence about the update itself.</strong> A refused, stopped or failed check means AUXSAYS does not know. It does not mean users reported problems, and it does not mean they reported none.</p>
      <p>Each page also states how many of its sources returned a usable, recent result, and says when that number is below the minimum AUXSAYS treats as adequate coverage. Where coverage for a release is thin or stale, the page says so rather than presenting the result as settled.</p>
    </article>

    <article class="methodology-card">
      <h2>Dates mean different things</h2>
      <p>A patch page can carry several dates: when the vendor source was last checked, when vendor detail was last captured, when the record itself last changed, and when user-report evidence was last checked. They move independently. One recent date is not proof that the others are recent, and a vendor check moving does not mean the recommendation, the report count or the evidence state changed.</p>
    </article>

    <article class="methodology-card">
      <h2>Limits of these notes</h2>
      <p>These notes describe what AUXSAYS counts and what it shows. They are not a claim that every public report has been found, that a listed release has been tested, or that a recommendation will hold. Recommendations are based on the available information and may change as new reports emerge.</p>
      <p>Where the evidence for a release is absent, limited or stale, prefer the page&rsquo;s own stated caveats over the recommendation on its own.</p>
    </article>
  </section>
</section>
