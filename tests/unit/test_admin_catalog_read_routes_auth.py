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

DATA_EDITOR_ROUTES = {
    ("PUT", "/admin/catalog/unit-conversions/{from_unit}/{to_unit}"),
    ("DELETE", "/admin/catalog/unit-conversions/{from_unit}/{to_unit}"),
    ("POST", "/admin/catalog/backups/create"),
    ("PATCH", "/admin/catalog/backups/{backup_name}/comment"),
    ("PUT", "/admin/catalog/ingredients/{ingredient_id}"),
    ("DELETE", "/admin/catalog/ingredients/{ingredient_id}"),
    ("PUT", "/admin/catalog/dishes/{dish_id}"),
    ("DELETE", "/admin/catalog/dishes/{dish_id}"),
}

DB_OPERATOR_ROUTES = {
    ("POST", "/admin/catalog/backups/restore"),
    ("DELETE", "/admin/catalog/backups/{backup_name}"),
    ("POST", "/admin/catalog/backups/batch-delete"),
}


def _dependency_names(route) -> set[str]:
    return {getattr(dep.call, "__name__", "") for dep in route.dependant.dependencies}


def test_read_routes_do_not_require_write_dependency():
    for route in app.router.routes:
        path = getattr(route, "path", None)
        methods = set(getattr(route, "methods", set()) or set())
        for method in methods:
            if (method, path) in READ_ROUTES:
                deps = _dependency_names(route)
                assert "require_data_editor" not in deps, f"{method} {path} should stay readable without login"
                assert "require_superuser" not in deps, f"{method} {path} should stay readable without superuser"
                assert "require_db_operator" not in deps, f"{method} {path} should stay readable without db operator"


def test_data_editor_routes_require_active_user_dependency():
    for route in app.router.routes:
        path = getattr(route, "path", None)
        methods = set(getattr(route, "methods", set()) or set())
        for method in methods:
            if (method, path) in DATA_EDITOR_ROUTES:
                deps = _dependency_names(route)
                assert "require_data_editor" in deps, f"{method} {path} must require an active data editor"
                assert "require_superuser" not in deps, f"{method} {path} should not require superuser"


def test_destructive_backup_routes_require_db_operator_dependency():
    for route in app.router.routes:
        path = getattr(route, "path", None)
        methods = set(getattr(route, "methods", set()) or set())
        for method in methods:
            if (method, path) in DB_OPERATOR_ROUTES:
                deps = _dependency_names(route)
                assert "require_db_operator" in deps, f"{method} {path} must require db operator"
                assert "require_superuser" not in deps, f"{method} {path} should not require superuser"
