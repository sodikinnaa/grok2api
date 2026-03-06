# Grok2API i18n Developer Guide

## Architecture

The i18n system is a single-file, zero-dependency module (`i18n.js`) that:

1. **Detects** the user's language: `localStorage` > `?lang=` URL param > browser `navigator.language` > fallback (`zh`)
2. **Fetches** the matching locale JSON (`/static/i18n/locales/{lang}.json`)
3. **Applies** translations to the DOM via `data-i18n-*` attributes
4. **Exposes** a global `t(key, params)` function for JS-driven strings

The script self-initializes on DOM ready. No import/export — it attaches `window.I18n` and `window.t`.

## File structure

```
public/static/i18n/
  i18n.js                  # Core module (IIFE, ~110 lines)
  locales/
    zh.json                # Chinese (default/fallback)
    en.json                # English
  README.md                # This file
```

Each HTML page includes the script before page-specific JS:

```html
<script src="/static/i18n/i18n.js"></script>
<script src="/static/public/js/chat.js"></script>
```

## Translation key conventions

Keys use **dot-notation** with a two-level namespace: `{page}.{name}`

| Namespace | Scope |
|-----------|-------|
| `common`  | Shared strings (save, cancel, loading, errors) |
| `nav`     | Navigation links and header labels |
| `login`   | Login pages (admin + public) |
| `config`  | Admin config page |
| `token`   | Token management page |
| `cache`   | Cache management page |
| `chat`    | Chat page |
| `imagine` | Image generation page |
| `video`   | Video generation page |
| `voice`   | Voice/LiveKit page |

Naming patterns:
- `page.pageTitle` — browser tab `<title>`
- `page.title` / `page.subtitle` — heading/subheading
- `page.placeholder` — main input placeholder
- `common.{verb}Failed` / `common.{verb}Error` — error messages
- `page.confirm{Action}` — confirmation dialog text

## Translating a static HTML element

Add one of these attributes to the HTML element:

### `data-i18n` — sets `textContent`

```html
<h2 data-i18n="chat.title">Chat 聊天</h2>
```

### `data-i18n-placeholder` — sets `placeholder`

```html
<textarea data-i18n-placeholder="chat.placeholder" placeholder="询问任何内容"></textarea>
```

### `data-i18n-title` — sets `title` (tooltip)

```html
<button data-i18n-title="chat.send" title="发送">▶</button>
```

### `data-i18n-html` — sets `innerHTML` (available, not currently used)

```html
<span data-i18n-html="chat.richContent"></span>
```

> Use only when the translation contains HTML markup. Prefer `data-i18n` for plain text to avoid XSS risks.

> Keep the Chinese fallback as the element's default content/attribute so the page renders correctly before translations load.

## Translating a dynamic JS string

Use the global `t(key, params?)` function:

```js
showToast(t('cache.clearSuccess', { size: data.result.size_mb }), 'success');
```

The `params` object replaces `{var}` placeholders in the locale string:

```json
{ "clearSuccess": "Cleared successfully, freed {size} MB" }
```

### Guard pattern for shared modules

Shared code (e.g., `toast.js`, `admin-auth.js`) may run before `i18n.js` loads. Guard with `typeof t`:

```js
const label = typeof t === 'function' ? t('common.notice') : '提示';
```

## Translating dynamically injected HTML

When HTML is injected at runtime (e.g., fetching a header fragment), call `I18n.applyToDOM(container)` after insertion:

```js
container.innerHTML = await res.text();

if (window.I18n) {
  I18n.applyToDOM(container);
}
```

This scans the container for `data-i18n-*` attributes and applies translations. The language toggle button text is set separately since it isn't a translation key:

```js
var toggle = container.querySelector('#lang-toggle');
if (toggle) toggle.textContent = I18n.getLang() === 'zh' ? 'EN' : '中';
```

## API reference

| Method | Description |
|--------|-------------|
| `t(key, params?)` | Translate a key. Returns the key itself if not found. |
| `I18n.applyToDOM(root?)` | Scan `root` (default: `document`) for `data-i18n-*` attrs and apply translations. |
| `I18n.setLang(lang)` | Set language, persist to localStorage, reload page. |
| `I18n.toggleLang()` | Toggle between `zh` and `en`, reload. |
| `I18n.getLang()` | Return current language code (`'zh'` or `'en'`). |
| `I18n.onReady(cb)` | Run `cb` after translations have loaded. Runs immediately if already loaded. |

## How to add a new language

1. Create `public/static/i18n/locales/{code}.json` — copy `en.json` as a template
2. Translate every key (545+ keys across 10 namespaces)
3. In `i18n.js`, add the code to the `SUPPORTED` array:
   ```js
   var SUPPORTED = ['zh', 'en', 'ja'];
   ```
4. Update the `toggleLang` function if you want rotation instead of binary toggle
5. Update `#lang-toggle` button logic in `header.js` / `public-header.js`

## How to add a new page

Checklist:

- [ ] Add a new namespace in both `zh.json` and `en.json` (e.g., `"mypage": { ... }`)
- [ ] In the HTML: add `<script src="/static/i18n/i18n.js"></script>` before your page JS
- [ ] In the HTML: add `data-i18n` / `data-i18n-placeholder` / `data-i18n-title` attributes to all user-visible elements
- [ ] In the JS: use `t('mypage.keyName')` for any strings built in code
- [ ] If injecting HTML dynamically: call `I18n.applyToDOM(container)` after insertion
- [ ] If the page loads before `i18n.js`: use the `typeof t === 'function'` guard

## Common patterns

### Button with icon + translated text

```html
<button class="btn" type="button">
  <svg>...</svg>
  <span data-i18n="voice.startSession">开始会话</span>
</button>
```

Wrap the text in a `<span>` so the icon is preserved.

### Select options translated in JS

```js
const option = document.createElement('option');
option.value = 'value';
option.textContent = t('voice.optionLabel');
select.appendChild(option);
```

### Interpolation for dynamic values

```js
// Locale: "lastClear": "Last cleared: {time}"
setText(el, t('cache.lastClear', { time: timeText }));
```

### Table rows with inline translated strings

```js
body.innerHTML = `<tr><td colspan="5">${t('common.loading')}</td></tr>`;
```

## Gotchas

1. **Script order matters.** `i18n.js` must be loaded before page JS if the page JS calls `t()` at the top level. Otherwise use the `typeof t === 'function'` guard.

2. **`t()` returns the key on miss.** If you see a raw key like `chat.title` in the UI, the key is missing from the locale JSON or was misspelled.

3. **Keep both locale files in sync.** Every key in `zh.json` must exist in `en.json` and vice versa. Missing keys fall through to displaying the raw key string.

4. **`innerHTML` vs `textContent`.** Use `data-i18n-html` only when the translation contains HTML markup. For plain text, always use `data-i18n` to avoid XSS risks.

5. **Default content is Chinese.** The HTML files keep Chinese as inline fallback text. This means the page briefly shows Chinese before translations load — this is intentional and ensures the page is never blank.

6. **`setLang()` reloads the page.** Language switching is not live — it persists to localStorage and triggers a full page reload.

7. **`applyToDOM()` is idempotent.** Safe to call multiple times on the same container.

8. **Shared modules need guards.** Files under `common/js/` (toast, header, admin-auth) may be loaded by pages that don't include `i18n.js`. Always guard `t()` calls in shared code.
