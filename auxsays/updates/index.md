---
layout: aux-updates
title: "Patch Feed: every tracked software update, newest first"
# The search description of /updates/ (and, through _plugins/patch_feed_pages.rb, of every later feed
# page, whose titles the plugin numbers). Without it the feed printed the site-wide creator tagline.
description: >-
  Every software update AUXSAYS tracks, by exact version or build, current releases newest first.
  Each entry opens that release's page: the official notes and user reports on record for it, and a
  verdict when the evidence supports one. Search by product or version.
permalink: /updates/
# Cards per feed page. /updates/ is page 1; _plugins/patch_feed_pages.rb builds /updates/page/2/ onward
# from this number, and the layout slices the same ordered list with it, so it is set here only.
# scripts/ci/verify_feed_discovery.py fails the deploy if any feed page passes its byte budget.
feed_page_size: 100
---
