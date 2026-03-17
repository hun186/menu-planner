from src.menu_planner.api.routes import admin_catalog


class _FakeRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def preview_dish_cost(self, items, servings=1.0):
        return {"items": items, "servings": servings, "ok": True}


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
