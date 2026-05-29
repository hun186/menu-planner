import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const reporterSource = readFileSync('src/menu_planner/ui_static/error_reporter.js', 'utf8');

test('pages install visible frontend error banner before page modules', () => {
  for (const page of ['index.html', 'admin.html', 'inventory.html']) {
    const html = readFileSync(`src/menu_planner/ui_static/${page}`, 'utf8');
    assert.match(html, /id="js_error_banner"/);
    assert.match(html, /<script src="error_reporter\.js"><\/script>\s*<script type="module"/);
  }
});

test('error reporter renders syntax error details without opening DevTools', () => {
  const listeners = {};
  const banner = {
    hidden: true,
    textContent: '',
    removeAttribute(name) {
      if (name === 'hidden') this.hidden = false;
    },
  };

  const context = {
    document: {
      getElementById(id) {
        return id === 'js_error_banner' ? banner : null;
      },
    },
    window: {
      location: { href: 'http://localhost:18000/' },
      addEventListener(type, handler) {
        listeners[type] = handler;
      },
    },
    URL,
    String,
  };
  context.window.window = context.window;

  vm.runInNewContext(reporterSource, context);
  listeners.error({
    message: 'Uncaught SyntaxError: missing ) after argument list',
    filename: 'http://localhost:18000/app.js',
    lineno: 114,
    colno: 9,
  });

  assert.equal(banner.hidden, false);
  assert.match(banner.textContent, /前端程式發生錯誤/);
  assert.match(banner.textContent, /missing \) after argument list/);
  assert.match(banner.textContent, /app\.js:114:9/);
});
