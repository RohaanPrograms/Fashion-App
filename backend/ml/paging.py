"""Paging through Supabase query results.

Supabase returns at most 1,000 rows per request, so a single select over 5,000
products quietly returns only the first 1,000 — no error, just missing rows.

Kept free of heavy imports on purpose: the live API uses this, and the API
never installs the training libraries.
"""

from __future__ import annotations

from collections.abc import Callable


def fetch_all_pages(
    fetch_page: Callable[[int, int], list], page_size: int = 1000
) -> list:
    """Collect every row from a paged query.

    `fetch_page(start, end)` must return rows start..end inclusive, as
    Supabase's range() does. A page shorter than page_size means there is
    nothing left.
    """
    rows: list = []
    start = 0
    while True:
        page = fetch_page(start, start + page_size - 1)
        rows.extend(page)
        if len(page) < page_size:
            return rows
        start += page_size
