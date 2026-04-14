import test from 'node:test';
import assert from 'node:assert/strict';

import { createCatalogCache, setCatalogCache } from '../../src/menu_planner/ui_static/shared/catalog_cache.js';
import { httpJson } from '../../src/menu_planner/ui_static/shared/http.js';
import { deleteDbBackup, deleteDbBackupsByDateRange, getDbBackupStats, listUnitConversions, loadCatalog, updateDbBackupComment, upsertIngredient, upsertUnitConversion } from '../../src/menu_planner/ui_static/admin/api.js';

test('catalog cache + admin api smoke flow with mocked fetch', async () => {
  const calls = [];

  global.localStorage = {
    getItem(key) {
      if (key === 'menu_admin_key') return 'secret';
      return null;
    },
  };

  global.fetch = async (url, options = {}) => {
    calls.push({ url, options });

    if (url === '/catalog/ingredients') {
      return {
        ok: true,
        json: async () => [{ id: 'ing_a', name: 'A' }],
      };
    }

    if (url === '/catalog/dishes') {
      return {
        ok: true,
        json: async () => [{ id: 'dish_a', name: 'Dish A', role: 'main' }],
      };
    }

    if (url.includes('/admin/catalog/ingredients/ing_new') && options.method === 'PUT') {
      return {
        ok: true,
        json: async () => ({ ok: true }),
      };
    }

    return {
      ok: false,
      status: 404,
      json: async () => ({ detail: { message: 'not found' } }),
    };
  };

  const { ingredients, dishes } = await loadCatalog();

  const cache = createCatalogCache();
  setCatalogCache(cache, ingredients, dishes);

  assert.equal(cache.ingredients.length, 1);
  assert.equal(cache.dishes.length, 1);
  assert.equal(cache.ingById.get('ing_a').name, 'A');

  await upsertIngredient('ing_new', {
    name: 'new',
    category: 'vegetable',
    protein_group: null,
    default_unit: 'g',
  });

  const adminPut = calls.find((x) => String(x.url).includes('/admin/catalog/ingredients/ing_new'));
  assert.ok(adminPut, 'expected admin ingredient PUT call');
  assert.equal(adminPut.options.headers['X-Admin-Key'], 'secret');
});

test('httpJson throws detail message on non-2xx response', async () => {
  global.fetch = async () => ({
    ok: false,
    status: 400,
    json: async () => ({ detail: { message: 'bad request' } }),
  });

  await assert.rejects(
    () => httpJson('/x', { method: 'GET' }),
    /bad request/,
  );
});

test('backup api helpers call expected endpoints', async () => {
  const calls = [];

  global.localStorage = {
    getItem(key) {
      if (key === 'menu_admin_key') return 'secret';
      return null;
    },
  };

  global.fetch = async (url, options = {}) => {
    calls.push({ url, options });
    return {
      ok: true,
      json: async () => ({ ok: true, count: 1 }),
    };
  };

  await getDbBackupStats();
  await deleteDbBackup('menu_20260320_120001_000001.db');
  await deleteDbBackupsByDateRange({ dateFrom: '2026-03-20', dateTo: '2026-03-21' });
  await updateDbBackupComment('menu_20260320_120001_000001.db', 'release before schema update');

  assert.ok(calls.some((x) => x.url === '/admin/catalog/backups/stats' && x.options.method === 'GET'));
  assert.ok(calls.some((x) => String(x.url).includes('/admin/catalog/backups/menu_20260320_120001_000001.db') && x.options.method === 'DELETE'));
  assert.ok(calls.some((x) => x.url === '/admin/catalog/backups/batch-delete' && x.options.method === 'POST'));
  assert.ok(calls.some((x) => String(x.url).includes('/admin/catalog/backups/menu_20260320_120001_000001.db/comment') && x.options.method === 'PATCH'));
});

test('unit conversion api helpers call expected endpoints', async () => {
  const calls = [];

  global.localStorage = {
    getItem(key) {
      if (key === 'menu_admin_key') return 'secret';
      return null;
    },
  };

  global.fetch = async (url, options = {}) => {
    calls.push({ url, options });
    return {
      ok: true,
      json: async () => ([]),
    };
  };

  await listUnitConversions();
  await upsertUnitConversion('kg', 'g', 1000);

  assert.ok(calls.some((x) => x.url === '/admin/catalog/unit-conversions' && x.options.method === 'GET'));
  assert.ok(calls.some((x) => x.url === '/admin/catalog/unit-conversions/kg/g' && x.options.method === 'PUT'));
});
