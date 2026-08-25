#!/usr/bin/env python3
"""CI adapter: prefetch selected release histories concurrently, then run the unchanged validator."""
from concurrent.futures import ThreadPoolExecutor, as_completed

import validate_package as vp


gold = vp.decode_gold()
selected = sorted({repo for row in gold for repo in row["official_repos"]})
_original = vp.bp.stable_releases
cache = {}
with ThreadPoolExecutor(max_workers=16) as ex:
    future_to_repo = {ex.submit(_original, repo): repo for repo in selected}
    for fut in as_completed(future_to_repo):
        repo = future_to_repo[fut]
        cache[repo] = fut.result()

vp.bp.stable_releases = lambda repo: cache[repo]

if __name__ == "__main__":
    vp.main()
