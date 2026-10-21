"""Every query on a per-user table must filter by that user.

The server uses Supabase's admin key, which bypasses Row Level Security, so
nothing in the database stops a query from returning everyone's rows. The
filter in our code is the only protection — these tests prove it is there.
"""

from app.db.interactions import SupabaseInteractionStore
from conftest import RecordingClient


def _rows(n):
    return [{"product_id": f"p{i}", "type": "like", "created_at": i} for i in range(n)]


def test_history_is_filtered_by_user_ordered_oldest_first_and_paged():
    client = RecordingClient({"interactions": _rows(2500)})

    rows = SupabaseInteractionStore(client).history_rows("user-a")

    assert len(rows) == 2500
    for query in client.queries:
        assert ("user_id", "user-a") in query.called("eq")
        assert query.called("order") == [("created_at",)]
    assert len(client.queries) == 3  # 1,000 + 1,000 + 500


def test_adding_writes_the_user_id_on_the_row():
    client = RecordingClient()

    SupabaseInteractionStore(client).add("user-a", "p1", "like", source="feed", dwell_time_ms=1200)

    (payload,) = client.queries[0].called("insert")[0]
    assert payload == {
        "user_id": "user-a", "product_id": "p1", "type": "like",
        "source": "feed", "dwell_time_ms": 1200,
    }


def test_clearing_deletes_only_this_users_rows():
    client = RecordingClient({"interactions": _rows(3)})

    deleted = SupabaseInteractionStore(client).clear("user-a")

    query = client.queries[0]
    assert query.called("delete") == [()]
    assert ("user_id", "user-a") in query.called("eq")
    assert deleted == 3
