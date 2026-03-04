/**
 * Grok2API i18n module — lightweight, zero-dependency internationalization.
 * Detects language from: localStorage > ?lang= URL param > browser > fallback (zh).
 * Translates static HTML via data-i18n / data-i18n-placeholder / data-i18n-title attrs.
 * Provides global t(key, params) for dynamic JS strings with {var} interpolation.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'grok2api_lang';
  var SUPPORTED = ['zh', 'en'];
  var DEFAULT = 'zh';

  var lang = DEFAULT;
  var data = {};
  var ready = false;
  var queue = [];

  function getStaticVersion() {
    var script = document.querySelector('script[src*="?v="]');
    if (!script || !script.src) return '';
    var m = script.src.match(/[?&]v=([^&]+)/);
    return m ? m[1] : '';
  }

  function detect() {
    try {
      var s = localStorage.getItem(STORAGE_KEY);
      if (s && SUPPORTED.indexOf(s) !== -1) return s;
    } catch (e) { /* ignore */ }
    try {
      var p = new URLSearchParams(location.search).get('lang');
      if (p && SUPPORTED.indexOf(p) !== -1) {
        try { localStorage.setItem(STORAGE_KEY, p); } catch (e) { /* ignore */ }
        return p;
      }
    } catch (e) { /* ignore */ }
    var b = (navigator.language || '').split('-')[0];
    if (SUPPORTED.indexOf(b) !== -1) return b;
    return DEFAULT;
  }

  function get(obj, key) {
    for (var parts = key.split('.'), i = 0; i < parts.length; i++) {
      if (obj == null) return undefined;
      obj = obj[parts[i]];
    }
    return obj;
  }

  function t(key, params) {
    var v = get(data, key);
    if (v === undefined) return key;
    if (params) {
      Object.keys(params).forEach(function (k) {
        v = v.replace(new RegExp('\\{' + k + '\\}', 'g'), params[k]);
      });
    }
    return v;
  }

  function applyToDOM(root) {
    var c = root || document;
    c.querySelectorAll('[data-i18n]').forEach(function (el) {
      var v = get(data, el.getAttribute('data-i18n'));
      if (v !== undefined) el.textContent = v;
    });
    c.querySelectorAll('[data-i18n-placeholder]').forEach(function (el) {
      var v = get(data, el.getAttribute('data-i18n-placeholder'));
      if (v !== undefined) el.placeholder = v;
    });
    c.querySelectorAll('[data-i18n-title]').forEach(function (el) {
      var v = get(data, el.getAttribute('data-i18n-title'));
      if (v !== undefined) el.title = v;
    });
    c.querySelectorAll('[data-i18n-html]').forEach(function (el) {
      var v = get(data, el.getAttribute('data-i18n-html'));
      if (v !== undefined) el.innerHTML = v;
    });
  }

  function init() {
    lang = detect();
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : lang;
    var version = getStaticVersion();
    var url = '/static/i18n/locales/' + lang + '.json' + (version ? ('?v=' + encodeURIComponent(version)) : '');
    fetch(url)
      .then(function (r) { if (!r.ok) throw r; return r.json(); })
      .then(function (j) { data = j; })
      .catch(function () { data = {}; })
      .then(function () {
        ready = true;
        applyToDOM(document);
        queue.forEach(function (cb) { cb(); });
        queue = [];
      });
  }

  function setLang(l) {
    if (SUPPORTED.indexOf(l) === -1) return;
    try { localStorage.setItem(STORAGE_KEY, l); } catch (e) { /* ignore */ }
    location.reload();
  }

  window.I18n = {
    t: t,
    applyToDOM: applyToDOM,
    setLang: setLang,
    toggleLang: function () { setLang(lang === 'zh' ? 'en' : 'zh'); },
    getLang: function () { return lang; },
    onReady: function (cb) { if (ready) cb(); else queue.push(cb); }
  };
  window.t = t;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
