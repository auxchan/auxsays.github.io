# frozen_string_literal: true

require "digest"

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
#
# ORDER (G36-02 follow-up). The layout used to sort the records itself, by `update_published_at`
# alone. Records published at the same moment then came out in whatever order the sort met them,
# which follows the order the files were read from disk: a CI build and a local build put tied
# records in different orders, and since every page is a slice of 100, a tied record could move to
# another page between two builds of the same records. The order is set here once instead, as
# `feed_rank` on every record: newest first, and records published at the same moment by permalink.
# The layout sorts by that rank, which no two records share.
#
# STAMP. Every feed page carries `feed_build`: the SHA-256 of the feed's card links, one line per card
# with the page it is on, in feed order. The feed controls read the other pages only when their stamp
# matches their own page's (assets/js/auxsays.js), so it has to change exactly when a page's cards
# would: a rebuild of the same records gives the same stamp; a record added, removed, re-dated,
# archived or hidden gives a new one. The deploy gate recomputes it from the built pages.
module Auxsays
  class PatchFeedPages < Jekyll::Generator
    safe true
    # Before jekyll-sitemap (:lowest), so the new pages are listed in sitemap.xml.
    priority :high

    FEED_URL = "/updates/"

    # Jekyll's `sort` filter on one property (filters.rb, sort_input), reversed for newest first: a
    # record with no date goes last; dates compare with <=>, or as text when they cannot.
    def self.newer_first(a, b)
      return 0 if a.nil? && b.nil?
      return 1 if a.nil?
      return -1 if b.nil?

      (b <=> a) || (b.to_s <=> a.to_s)
    end

    # Newest first; records published at the same moment by permalink.
    def self.feed_order(records)
      records.sort do |a, b|
        newer_first(a.data["update_published_at"], b.data["update_published_at"]).nonzero? || (a.url <=> b.url)
      end
    end

    # The cards the layout prints, in its order: the current records, then the archived ones, none
    # that is `feed_hidden: true`; one line per card, "<page> <link>".
    def self.feed_stamp(ordered, size)
      listed = ordered.reject { |page| page.data["feed_hidden"] == true }
      archived, current = listed.partition { |page| page.data["update_status"] == "archived" }
      lines = (current + archived).each_with_index.map { |page, at| "#{(at / size) + 1} #{page.url}\n" }
      Digest::SHA256.hexdigest(lines.join)
    end

    def generate(site)
      feed = site.pages.find { |page| page.url == FEED_URL && page.data["layout"] == "aux-updates" }
      return unless feed

      size = Integer(feed.data.fetch("feed_page_size"))
      raise ArgumentError, "feed_page_size must be positive, got #{size}" unless size.positive?

      records = self.class.feed_order(site.pages.select { |page| page.data["update_entry"].to_s == "true" })
      records.each_with_index { |page, rank| page.data["feed_rank"] = rank }
      listed = records.count { |page| page.data["feed_hidden"] != true }
      total = [(listed + size - 1) / size, 1].max

      feed.data["feed_page"] = 1
      feed.data["feed_build"] = self.class.feed_stamp(records, size)
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
