from src.menu_planner.api.routes import admin_catalog


class _FakeRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def preview_dish_cost(self, items, servings=1.0):
        return {"items": items, "servings": servings, "ok": True}

    def list_dish_cost_preview(self):
        return [{"dish_id": "dish-1", "per_serving_cost": 12.3, "warning_count": 1, "warnings": []}]

    def list_inventory_summary(self, q=None, only_in_stock=False):
        return [{"ingredient_id": "ing-1", "q": q, "only_in_stock": only_in_stock}]

    def list_dishes(self, q=None, role=None, ingredient_id=None, page=1, page_size=50):
        return {
            "items": [{"id": "dish-1", "name": "炒飯", "role": "main"}],
            "q": q,
            "role": role,
            "ingredient_id": ingredient_id,
            "page": page,
            "page_size": page_size,
        }


def test_dish_cost_preview_passthrough(monkeypatch):
    monkeypatch.setattr(admin_catalog, "SQLiteAdminRepo", _FakeRepo)

    body = admin_catalog.DishCostPreviewIn(
        items=[admin_catalog.DishIngredientIn(ingredient_id="ing-1", qty=10, unit="g")],
        servings=2,
    )
    resp = admin_catalog.dish_cost_preview(body, db_path="/tmp/menu.db")

    assert resp["ok"] is True
    assert resp["servings"] == 2
    assert resp["items"] == [{"ingredient_id": "ing-1", "qty": 10.0, "unit": "g"}]


def test_list_dish_cost_preview_passthrough(monkeypatch):
    monkeypatch.setattr(admin_catalog, "SQLiteAdminRepo", _FakeRepo)

    resp = admin_catalog.list_dish_cost_preview(db_path="/tmp/menu.db")

    assert resp == [{"dish_id": "dish-1", "per_serving_cost": 12.3, "warning_count": 1, "warnings": []}]


def test_list_inventory_summary_passthrough(monkeypatch):
    monkeypatch.setattr(admin_catalog, "SQLiteAdminRepo", _FakeRepo)

    resp = admin_catalog.list_inventory_summary(q="rice", only_in_stock=True, db_path="/tmp/menu.db")

    assert resp == [{"ingredient_id": "ing-1", "q": "rice", "only_in_stock": True}]


def test_list_dishes_passthrough_with_ingredient_filter(monkeypatch):
    monkeypatch.setattr(admin_catalog, "SQLiteAdminRepo", _FakeRepo)

    resp = admin_catalog.list_dishes(
        q="炒",
        role="main",
        ingredient_id="ing-carrot",
        page=2,
        page_size=30,
        db_path="/tmp/menu.db",
    )

    assert resp["ingredient_id"] == "ing-carrot"
    assert resp["q"] == "炒"
    assert resp["role"] == "main"
    assert resp["page"] == 2
    assert resp["page_size"] == 30
