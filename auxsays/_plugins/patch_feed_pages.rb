# frozen_string_literal: true

# PATCH FEED PAGES (G36-02).
#
# /updates/ used to print every tracked patch as a full card on one page: 1,535 cards, 4.3 MB of
# HTML, growing by a few hundred records a month. Googlebot reads the first 2 MB of an HTML
# response, so more than half of the feed (and all of its archive) was past what it reads.
#
# The feed is now paged. /updates/ is page 1 and this generator adds /updates/page/2/ onward. Each
# extra page is the feed page itself (same layout, same front matter, same body) with its own
# `feed_page` number, title and permalink, so jekyll-seo-tag gives it a self-canonical and
# jekyll-sitemap lists it (both read the page list after this runs). The layout
# (_layouts/aux-updates.html) slices the one ordered list of records with the same page size, and
# links every page from a plain <a href> list.
#
# The page count is computed here from the same predicate the layout lists: every record
# (`update_entry: true`) that is not `feed_hidden: true`. Archived records are on the feed too, after
# the current ones, so they count. scripts/ci/verify_feed_discovery.py checks the built result: every
# listed record linked from exactly the feed pages the pagination reaches, no page over budget.
#
# A static set of committed stub pages would have gone stale: the record count moves with every
# ingestion run, and a missing stub silently drops the newest-pushed records off the end of the feed.
module Auxsays
  class PatchFeedPages < Jekyll::Generator
    safe true
    # Before jekyll-sitemap (:lowest), so the new pages are listed in sitemap.xml.
    priority :high

    FEED_URL = "/updates/"

    def generate(site)
      feed = site.pages.find { |page| page.url == FEED_URL && page.data["layout"] == "aux-updates" }
      return unless feed

      size = Integer(feed.data.fetch("feed_page_size"))
      raise ArgumentError, "feed_page_size must be positive, got #{size}" unless size.positive?

      listed = site.pages.count do |page|
        page.data["update_entry"].to_s == "true" && page.data["feed_hidden"] != true
      end
      total = [(listed + size - 1) / size, 1].max

      feed.data["feed_page"] = 1
      (2..total).each do |number|
        page = Jekyll::PageWithoutAFile.new(site, site.source, "updates/page/#{number}", "index.html")
        page.data = feed.data.merge(
          "feed_page" => number,
          "title" => "Patch Feed, page #{number}",
          "permalink" => "/updates/page/#{number}/"
        )
        page.content = feed.content
        site.pages << page
      end
    end
  end
end
