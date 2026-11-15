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


# --- Editing ------------------------------------------------------------------

def _saved(name="Old name", items=(("p1", "top"), ("p2", "bottom"))):
    return {"outfits": [{"id": "o1", "name": name,
                         "outfit_items": [{"product_id": p, "slot": s} for p, s in items]}]}


def test_editing_checks_ownership_then_renames_and_swaps_the_items():
    client = RecordingClient(_saved())

    changed = SupabaseOutfitStore(client).replace("user-a", "o1", "New name", [("p3", "top"), ("p4", "shoes")])

    assert changed is True
    lookup, rename, remove, insert = client.queries
    assert lookup.table == "outfits"
    assert ("user_id", "user-a") in lookup.called("eq") and ("id", "o1") in lookup.called("eq")
    assert rename.table == "outfits" and rename.called("update")[0][0] == {"name": "New name"}
    assert ("user_id", "user-a") in rename.called("eq")
    assert remove.table == "outfit_items" and remove.called("delete") == [()]
    assert ("outfit_id", "o1") in remove.called("eq")
    assert insert.called("insert")[0][0] == [
        {"outfit_id": "o1", "product_id": "p3", "slot": "top"},
        {"outfit_id": "o1", "product_id": "p4", "slot": "shoes"},
    ]


def test_editing_someone_elses_or_a_missing_outfit_changes_nothing():
    client = RecordingClient({"outfits": []})

    assert SupabaseOutfitStore(client).replace("user-a", "o1", "New", [("p3", "top")]) is False
    assert len(client.queries) == 1  # only the lookup


def test_a_failed_edit_puts_the_old_name_and_items_back():
    """Three separate requests, so not atomic: never leave a set emptied."""
    client = RecordingClient(_saved())
    real_table = client.table
    inserts = {"n": 0}

    def table(name):
        query = real_table(name)
        if name == "outfit_items":
            real_execute = query.execute

            def execute():
                if query.called("insert"):
                    inserts["n"] += 1
                    if inserts["n"] == 1:  # the new items fail; the restore succeeds
                        raise RuntimeError("insert failed")
                return real_execute()

            query.execute = execute
        return query

    client.table = table

    with pytest.raises(RuntimeError):
        SupabaseOutfitStore(client).replace("user-a", "o1", "New name", [("p3", "top"), ("p4", "shoes")])

    restore_items, restore_name = client.queries[-2], client.queries[-1]
    assert restore_items.called("insert")[0][0] == [
        {"outfit_id": "o1", "product_id": "p1", "slot": "top"},
        {"outfit_id": "o1", "product_id": "p2", "slot": "bottom"},
    ]
    assert restore_name.called("update")[0][0] == {"name": "Old name"}
