import pytest

from app.db.outfits import SupabaseOutfitStore
from conftest import RecordingClient


def test_creating_writes_the_outfit_for_the_user_then_its_items():
    client = RecordingClient()

    outfit_id = SupabaseOutfitStore(client).create("user-a", "Friday", [("p1", "top"), ("p2", "bottom")])

    outfit_insert, items_insert = client.queries
    assert outfit_insert.table == "outfits"
    assert outfit_insert.called("insert")[0][0] == {"user_id": "user-a", "name": "Friday"}
    assert items_insert.table == "outfit_items"
    assert items_insert.called("insert")[0][0] == [
        {"outfit_id": outfit_id, "product_id": "p1", "slot": "top"},
        {"outfit_id": outfit_id, "product_id": "p2", "slot": "bottom"},
    ]


def test_a_failed_item_insert_removes_the_half_made_outfit():
    client = RecordingClient()
    real_table = client.table

    def table(name):
        query = real_table(name)
        if name == "outfit_items":
            query.execute = lambda: (_ for _ in ()).throw(RuntimeError("insert failed"))
        return query

    client.table = table

    with pytest.raises(RuntimeError):
        SupabaseOutfitStore(client).create("user-a", "Friday", [("p1", "top"), ("p2", "bottom")])

    cleanup = client.queries[-1]
    assert cleanup.table == "outfits" and cleanup.called("delete") == [()]
    assert ("user_id", "user-a") in cleanup.called("eq")


def test_listing_is_filtered_by_user_and_newest_first():
    client = RecordingClient({"outfits": [{"id": "o1"}]})

    SupabaseOutfitStore(client).list("user-a")

    query = client.queries[0]
    assert ("user_id", "user-a") in query.called("eq")
    assert query.calls[[c[0] for c in query.calls].index("order")][2] == {"desc": True}


def test_deleting_is_filtered_by_user_and_id():
    client = RecordingClient({"outfits": [{"id": "o1"}]})

    deleted = SupabaseOutfitStore(client).delete("user-a", "o1")

    query = client.queries[0]
    assert ("user_id", "user-a") in query.called("eq") and ("id", "o1") in query.called("eq")
    assert deleted is True
