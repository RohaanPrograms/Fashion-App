from ml.paging import fetch_all_pages


def test_fetch_all_pages_collects_past_the_first_page():
    """Supabase returns at most 1,000 rows per request; one request is not enough."""
    data = list(range(2345))
    calls = []

    def fetch_page(start: int, end: int) -> list[int]:
        calls.append((start, end))
        return data[start : end + 1]  # end is inclusive, as in Supabase's range()

    result = fetch_all_pages(fetch_page, page_size=1000)

    assert result == data
    assert calls == [(0, 999), (1000, 1999), (2000, 2999)]


def test_fetch_all_pages_stops_after_an_exactly_full_last_page():
    data = list(range(2000))

    result = fetch_all_pages(lambda s, e: data[s : e + 1], page_size=1000)

    assert result == data
