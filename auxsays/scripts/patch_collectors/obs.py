"""OBS Studio evidence collector adapter.

This wraps the existing production OBS collector so the shared runner can own
workflow orchestration without changing OBS evidence semantics in Phase A.
"""
from __future__ import annotations

from typing import Any

import collect_obs_reports as legacy_obs

from .base import CollectorContext, ProductCollector, method_health_row, utc_now


class ObsCollector(ProductCollector):
    product_id = legacy_obs.PRODUCT_ID

    def collect(self, context: CollectorContext) -> list[dict[str, Any]]:
        records_by_version = {version: path for version, path in legacy_obs.active_obs_records()}
        if context.target_versions:
            versions = sorted(context.target_versions)
        else:
            versions = sorted(records_by_version)

        results: list[dict[str, Any]] = []
        for version in versions:
            if not legacy_obs.valid_update_version(version):
                results.append({
                    "product_id": self.product_id,
                    "version": version,
                    "status": "invalid_version",
                    "accepted_count": 0,
                    "rejected_count": 0,
                })
                continue
            status, result = legacy_obs.collect_one(
                version=version,
                record_path=records_by_version.get(version),
                since=context.since,
                max_pages=context.max_pages,
                write=context.write,
            )
            last_run = utc_now()
            accepted_count = int(result.get("accepted_count") or 0)
            rejected_count = int(result.get("rejected_count") or 0)
            candidates = int(result.get("candidates_reviewed") or accepted_count + rejected_count)
            method_status = "success" if status == 0 and accepted_count > 0 else ("no_results" if status == 0 else "broken")
            result["product_id"] = self.product_id
            result["collector_status"] = status
            result["method_health"] = [
                method_health_row(
                    product_id=self.product_id,
                    update_version=version,
                    method_id="github_issues",
                    source_type="github_issue",
                    status=method_status,
                    candidates_found=candidates,
                    accepted_reports=accepted_count,
                    rejected_reports=rejected_count,
                    blocked_reason=str(result.get("error") or "") if status != 0 else "",
                    last_run=last_run,
                    notes="Primary OBS evidence method. Uses obsproject/obs-studio GitHub Issues with exact version matching.",
                )
            ]
            if accepted_count == 0 or status != 0:
                result["method_health"].append(
                    method_health_row(
                        product_id=self.product_id,
                        update_version=version,
                        method_id="known_watchlist",
                        source_type="curated_watchlist",
                        status="disabled",
                        candidates_found=0,
                        accepted_reports=0,
                        rejected_reports=0,
                        blocked_reason="no_obs_watchlist_configured",
                        last_run=last_run,
                        notes="Reserved OBS secondary discovery slot. It does not discover candidates in Phase A.",
                    )
                )
            if records_by_version.get(version):
                result["record_path"] = str(records_by_version[version].relative_to(legacy_obs.ROOT))
            results.append(result)
        return results
