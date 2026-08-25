#!/usr/bin/env python3
"""CI adapter: parallelize first-party release-history retrieval without changing benchmark semantics."""
from concurrent.futures import ThreadPoolExecutor, as_completed

import build_package as bp

_original = bp.stable_releases


def parallel_eligible_histories():
    result = {}
    with ThreadPoolExecutor(max_workers=16) as ex:
        future_to_repo = {ex.submit(_original, repo): repo for repo in bp.REPOSITORIES}
        for fut in as_completed(future_to_repo):
            repo = future_to_repo[fut]
            try:
                history = fut.result()
            except Exception:
                history = []
            if len(history) >= 2 and history[0]["published_at"] >= bp.RECENCY_FLOOR:
                result[repo] = history
    return result


bp.eligible_histories = parallel_eligible_histories

if __name__ == "__main__":
    bp.main()
