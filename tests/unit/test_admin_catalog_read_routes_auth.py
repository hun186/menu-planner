from src.menu_planner.api.main import app


READ_ROUTES = {
    ("GET", "/admin/catalog/ingredients"),
    ("GET", "/admin/catalog/dishes"),
    ("GET", "/admin/catalog/ingredients/{ingredient_id}/prices"),
    ("GET", "/admin/catalog/ingredients/{ingredient_id}/inventory"),
    ("GET", "/admin/catalog/inventory/summary"),
    ("GET", "/admin/catalog/inventory/summary/export"),
    ("GET", "/admin/catalog/unit-conversions"),
    ("GET", "/admin/catalog/backups"),
    ("GET", "/admin/catalog/backups/stats"),
    ("GET", "/admin/catalog/ingredients/export"),
    ("GET", "/admin/catalog/dishes/export"),
    ("GET", "/admin/catalog/dishes/{dish_id}/ingredients"),
    ("POST", "/admin/catalog/dishes/cost-preview"),
    ("GET", "/admin/catalog/dishes/cost-preview"),
}


WRITE_ROUTES = {
    ("PUT", "/admin/catalog/unit-conversions/{from_unit}/{to_unit}"),
    ("DELETE", "/admin/catalog/unit-conversions/{from_unit}/{to_unit}"),
    ("POST", "/admin/catalog/backups/create"),
    ("POST", "/admin/catalog/backups/restore"),
    ("DELETE", "/admin/catalog/backups/{backup_name}"),
    ("POST", "/admin/catalog/backups/batch-delete"),
    ("PATCH", "/admin/catalog/backups/{backup_name}/comment"),
    ("PUT", "/admin/catalog/ingredients/{ingredient_id}"),
    ("DELETE", "/admin/catalog/ingredients/{ingredient_id}"),
    ("PUT", "/admin/catalog/dishes/{dish_id}"),
    ("DELETE", "/admin/catalog/dishes/{dish_id}"),
}


def _has_admin_key_dependency(route) -> bool:
    names = [getattr(dep.call, "__name__", "") for dep in route.dependant.dependencies]
    return "require_admin_key" in names


def test_read_routes_do_not_require_admin_key_dependency():
    for route in app.router.routes:
        path = getattr(route, "path", None)
        methods = set(getattr(route, "methods", set()) or set())
        for method in methods:
            if (method, path) in READ_ROUTES:
                assert _has_admin_key_dependency(route) is False, f"{method} {path} should stay readable without admin key"


def test_write_routes_still_require_admin_key_dependency():
    for route in app.router.routes:
        path = getattr(route, "path", None)
        methods = set(getattr(route, "methods", set()) or set())
        for method in methods:
            if (method, path) in WRITE_ROUTES:
                assert _has_admin_key_dependency(route) is True, f"{method} {path} must require admin key"
