/* Tarangeeta block editor — Editor.js configuration + custom tools + editor shell.
   Loaded after Editor.js core and its tool bundles (see edit-post-block.html). */
(function () {
  'use strict';

  var app = document.getElementById('beApp');
  var CFG = {
    postId: app.dataset.postId || null,
    autosaveUrl: app.dataset.autosaveUrl,
    uploadUrl: app.dataset.uploadUrl,
    fetchUrl: app.dataset.fetchUrl,
    galleryUrl: app.dataset.galleryUrl,
    homeUrl: app.dataset.homeUrl,
    csrf: window.BE_CSRF
  };
  var FONTS = window.BE_FONTS || ['Lora', 'Playfair Display', 'Georgia'];

  // Design-system palette for the color / highlight pickers.
  var TEXT_COLORS = ['#4A4039', '#C4937A', '#5C4A3D', '#8B7355', '#D4A574', '#6B8E7F', '#9A6A6A', '#3A5A78'];
  var HL_COLORS = ['#F2D7C4', '#E8C4C4', '#F5E6C8', '#D8E6D2', '#D2E0E8', '#EADBF0', '#FBE3A2', '#FFFFFF'];
  var FONT_SIZES = [
    { label: 'Small', value: '0.85em' }, { label: 'Normal', value: '1em' },
    { label: 'Large', value: '1.25em' }, { label: 'X-Large', value: '1.6em' },
    { label: 'Huge', value: '2em' }
  ];

  function svgBtn(inner) { return '<span class="be-it-ic">' + inner + '</span>'; }

  /* =====================================================================
     Custom INLINE tools
  ===================================================================== */
  function makeTagTool(opts) {
    return function (ctor) { return ctor; }(class {
      static get isInline() { return true; }
      static get sanitize() {
        var s = {};
        s[opts.tag.toLowerCase()] = opts.cls ? { class: true } : {};
        return s;
      }
      get shortcut() { return opts.shortcut; }
      constructor(o) { this.api = o.api; this.button = null; }
      render() {
        this.button = document.createElement('button');
        this.button.type = 'button';
        this.button.classList.add(this.api.styles.inlineToolButton);
        this.button.innerHTML = svgBtn(opts.icon);
        this.button.title = opts.title;
        return this.button;
      }
      surround(range) {
        if (!range) return;
        var found = this.api.selection.findParentTag(opts.tag, opts.cls || null);
        if (found) { this.unwrap(found); } else { this.wrap(range); }
      }
      wrap(range) {
        var el = document.createElement(opts.tag);
        if (opts.cls) el.classList.add(opts.cls);
        el.appendChild(range.extractContents());
        range.insertNode(el);
        this.api.selection.expandToTag(el);
      }
      unwrap(el) {
        var p = el.parentNode;
        while (el.firstChild) p.insertBefore(el.firstChild, el);
        p.removeChild(el);
      }
      checkState() {
        var active = !!this.api.selection.findParentTag(opts.tag, opts.cls || null);
        if (this.button) this.button.classList.toggle(this.api.styles.inlineToolButtonActive, active);
        return active;
      }
    });
  }

  var Underline = makeTagTool({ tag: 'U', icon: '<u>U</u>', title: 'Underline', shortcut: 'CMD+U' });
  var Strike = makeTagTool({ tag: 'S', icon: '<s>S</s>', title: 'Strikethrough', shortcut: 'CMD+SHIFT+S' });
  var InlineCode = makeTagTool({ tag: 'CODE', cls: 'be-inline-code', icon: '&lt;/&gt;', title: 'Inline code', shortcut: 'CMD+SHIFT+M' });

  // Shared floating popover for the style pickers (color / highlight / font).
  var Popover = {
    el: null,
    init: function () {
      this.el = document.createElement('div');
      this.el.className = 'be-style-pop';
      this.el.hidden = true;
      document.body.appendChild(this.el);
      document.addEventListener('mousedown', function (e) {
        if (Popover.el && !Popover.el.hidden && !Popover.el.contains(e.target)) Popover.hide();
      });
    },
    open: function (rect, builder) {
      if (!this.el) this.init();
      this.el.innerHTML = '';
      builder(this.el);
      this.el.hidden = false;
      var top = window.scrollY + rect.bottom + 8;
      var left = window.scrollX + rect.left;
      left = Math.min(left, window.scrollX + document.documentElement.clientWidth - this.el.offsetWidth - 12);
      this.el.style.top = top + 'px';
      this.el.style.left = Math.max(8, left) + 'px';
    },
    hide: function () { if (this.el) this.el.hidden = true; }
  };

  function makeStyleTool(opts) {
    return class {
      static get isInline() { return true; }
      static get title() { return opts.title; }
      static get sanitize() { return { span: { class: true, style: true } }; }
      constructor(o) { this.api = o.api; this.savedRange = null; this.button = null; }
      render() {
        this.button = document.createElement('button');
        this.button.type = 'button';
        this.button.classList.add(this.api.styles.inlineToolButton);
        this.button.innerHTML = svgBtn(opts.icon);
        this.button.title = opts.title;
        return this.button;
      }
      surround(range) {
        if (!range) return;
        this.savedRange = range.cloneRange();
        var rect = range.getBoundingClientRect();
        var self = this;
        Popover.open(rect, function (pop) { self.build(pop); });
      }
      build(pop) {
        var self = this;
        var head = document.createElement('div');
        head.className = 'be-pop-title';
        head.textContent = opts.title;
        pop.appendChild(head);
        var grid = document.createElement('div');
        grid.className = opts.grid || 'be-swatches';
        opts.options.forEach(function (o) {
          var b = document.createElement('button');
          b.type = 'button';
          b.className = 'be-swatch';
          if (opts.kind === 'color' || opts.kind === 'bg') {
            b.style[opts.kind === 'bg' ? 'backgroundColor' : 'color'] = o.value;
            b.style.setProperty('--sw', o.value);
            b.classList.add(opts.kind === 'bg' ? 'be-swatch-bg' : 'be-swatch-color');
            b.innerHTML = '<span>A</span>';
          } else {
            b.classList.add('be-swatch-text');
            b.textContent = o.label;
            b.style.fontSize = (opts.kind === 'size') ? o.value : '';
            b.style.fontFamily = (opts.kind === 'font') ? o.value : '';
          }
          b.title = o.label;
          b.addEventListener('click', function () { self.apply(o.value); });
          grid.appendChild(b);
        });
        pop.appendChild(grid);
        var clear = document.createElement('button');
        clear.type = 'button';
        clear.className = 'be-pop-clear';
        clear.textContent = 'Clear';
        clear.addEventListener('click', function () { self.clear(); });
        pop.appendChild(clear);
      }
      apply(value) {
        var range = this.savedRange;
        if (!range) { Popover.hide(); return; }
        // Re-select the saved range so the wrap targets the right text even
        // though the visible selection was lost while the popover was open.
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        var span = document.createElement('span');
        span.className = opts.cls;
        span.style[opts.prop] = value;
        try {
          range.surroundContents(span);
        } catch (e) {
          try { span.appendChild(range.extractContents()); range.insertNode(span); } catch (e2) { }
        }
        sel.removeAllRanges();
        Popover.hide();
        markDirty(); recount(); scheduleSave();
      }
      clear() {
        var range = this.savedRange;
        if (range) {
          var node = range.commonAncestorContainer;
          while (node && node !== document.body) {
            if (node.nodeType === 1 && node.tagName === 'SPAN' && node.classList.contains(opts.cls)) {
              var p = node.parentNode;
              while (node.firstChild) p.insertBefore(node.firstChild, node);
              p.removeChild(node);
              break;
            }
            node = node.parentNode;
          }
        }
        Popover.hide();
        markDirty(); recount(); scheduleSave();
      }
      checkState() {
        var active = !!this.api.selection.findParentTag('SPAN', opts.cls);
        if (this.button) this.button.classList.toggle(this.api.styles.inlineToolButtonActive, active);
        return active;
      }
    };
  }

  var TextColor = makeStyleTool({
    title: 'Text color', cls: 'be-color', prop: 'color', kind: 'color',
    icon: '<span style="border-bottom:3px solid #C4937A;line-height:1">A</span>',
    options: TEXT_COLORS.map(function (c) { return { label: c, value: c }; })
  });
  var Highlight = makeStyleTool({
    title: 'Highlight', cls: 'be-hl', prop: 'backgroundColor', kind: 'bg',
    icon: '<span style="background:#F5E6C8;padding:0 2px;border-radius:2px;line-height:1">A</span>',
    options: HL_COLORS.map(function (c) { return { label: c, value: c }; })
  });
  var FontSize = makeStyleTool({
    title: 'Font size', cls: 'be-fsize', prop: 'fontSize', kind: 'size', grid: 'be-stack',
    icon: '<span style="line-height:1">A<sup>A</sup></span>',
    options: FONT_SIZES
  });
  var FontFamily = makeStyleTool({
    title: 'Font', cls: 'be-ffam', prop: 'fontFamily', kind: 'font', grid: 'be-stack',
    icon: '<span style="font-family:Georgia,serif;line-height:1">F</span>',
    options: FONTS.map(function (f) { return { label: f, value: "'" + f + "'" }; })
  });

  /* =====================================================================
     Block TUNES: alignment, line spacing, duplicate
  ===================================================================== */
  var ALIGN_ICONS = {
    left: '<svg width="16" height="16" viewBox="0 0 16 16"><path fill="currentColor" d="M1 2h14v2H1zM1 6h9v2H1zM1 10h14v2H1zM1 14h9v2H1z"/></svg>',
    center: '<svg width="16" height="16" viewBox="0 0 16 16"><path fill="currentColor" d="M1 2h14v2H1zM3 6h10v2H3zM1 10h14v2H1zM3 14h10v2H3z"/></svg>',
    right: '<svg width="16" height="16" viewBox="0 0 16 16"><path fill="currentColor" d="M1 2h14v2H1zM6 6h9v2H6zM1 10h14v2H1zM6 14h9v2H6z"/></svg>',
    justify: '<svg width="16" height="16" viewBox="0 0 16 16"><path fill="currentColor" d="M1 2h14v2H1zM1 6h14v2H1zM1 10h14v2H1zM1 14h14v2H1z"/></svg>'
  };

  class AlignmentTune {
    static get isTune() { return true; }
    constructor(o) { this.api = o.api; this.block = o.block; this.data = { alignment: (o.data && o.data.alignment) || 'left' }; this.wrapper = null; }
    wrap(blockContent) { this.wrapper = blockContent; this.applyStyle(); return blockContent; }
    applyStyle() { if (this.wrapper) this.wrapper.style.textAlign = this.data.alignment; }
    render() {
      var self = this;
      return {
        icon: ALIGN_ICONS[this.data.alignment] || ALIGN_ICONS.left,
        title: 'Alignment',
        toggle: false,
        children: {
          items: ['left', 'center', 'right', 'justify'].map(function (a) {
            return {
              icon: ALIGN_ICONS[a], title: a.charAt(0).toUpperCase() + a.slice(1),
              isActive: self.data.alignment === a, closeOnActivate: true,
              onActivate: function () { self.data.alignment = a; self.applyStyle(); markDirty(); }
            };
          })
        }
      };
    }
    save() { return this.data; }
  }

  var LINE_HEIGHTS = [
    { key: 'tight', label: 'Tight', css: '1.3' }, { key: 'normal', label: 'Normal', css: '' },
    { key: 'relaxed', label: 'Relaxed', css: '1.8' }, { key: 'loose', label: 'Loose', css: '2.2' }
  ];
  class LineHeightTune {
    static get isTune() { return true; }
    constructor(o) { this.api = o.api; this.block = o.block; this.data = { value: (o.data && o.data.value) || 'normal' }; this.wrapper = null; }
    wrap(blockContent) { this.wrapper = blockContent; this.applyStyle(); return blockContent; }
    applyStyle() {
      if (!this.wrapper) return;
      var m = LINE_HEIGHTS.filter(function (x) { return x.key === this.data.value; }, this)[0];
      this.wrapper.style.lineHeight = (m && m.css) ? m.css : '';
    }
    render() {
      var self = this;
      return {
        icon: '<svg width="16" height="16" viewBox="0 0 16 16"><path fill="currentColor" d="M2 3h12v1.5H2zM2 7.25h12v1.5H2zM2 11.5h12V13H2z"/></svg>',
        title: 'Line spacing', toggle: false,
        children: {
          items: LINE_HEIGHTS.map(function (lh) {
            return {
              title: lh.label, isActive: self.data.value === lh.key, closeOnActivate: true,
              onActivate: function () { self.data.value = lh.key; self.applyStyle(); markDirty(); }
            };
          })
        }
      };
    }
    save() { return this.data; }
  }

  class DuplicateTune {
    static get isTune() { return true; }
    constructor(o) { this.api = o.api; }
    render() {
      var api = this.api;
      return {
        icon: '<svg width="16" height="16" viewBox="0 0 16 16"><path fill="currentColor" d="M4 2h7a1 1 0 0 1 1 1v7h-1.5V3.5H4zM2.5 5H9a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1H2.5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zm.5 1.5V13H8.5V6.5z"/></svg>',
        title: 'Duplicate', closeOnActivate: true,
        onActivate: function () {
          api.saver.save().then(function (out) {
            var idx = api.blocks.getCurrentBlockIndex();
            var blk = out.blocks[idx];
            if (blk) { api.blocks.insert(blk.type, blk.data, {}, idx + 1, true); markDirty(); }
          });
        }
      };
    }
    save() { return {}; }
  }

  /* =====================================================================
     Custom BLOCK tools: Gallery, Caption
  ===================================================================== */
  class GalleryTool {
    static get toolbox() { return { title: 'Gallery', icon: '<svg width="17" height="15" viewBox="0 0 17 15"><path fill="currentColor" d="M1 1h7v6H1zM9 1h7v3H9zM9 5h7v3H9zM1 8h7v6H1zM9 9h7v5H9z"/></svg>' }; }
    constructor(o) { this.api = o.api; this.config = o.config || {}; this.data = { images: (o.data && o.data.images) || [] }; }
    render() {
      this.wrapper = document.createElement('div');
      this.wrapper.className = 'be-gallery-tool';
      this.grid = document.createElement('div');
      this.grid.className = 'be-gallery-grid';
      this.wrapper.appendChild(this.grid);
      var add = document.createElement('button');
      add.type = 'button';
      add.className = 'be-gallery-add';
      add.innerHTML = '<i class="fas fa-plus"></i> Add images';
      var self = this;
      add.addEventListener('click', function () { self.pick(); });
      this.wrapper.appendChild(add);
      this.renderGrid();
      return this.wrapper;
    }
    renderGrid() {
      var self = this;
      this.grid.innerHTML = '';
      this.data.images.forEach(function (url, i) {
        var src = (typeof url === 'string') ? url : url.url;
        var cell = document.createElement('div');
        cell.className = 'be-gallery-cell';
        var img = document.createElement('img');
        img.src = src;
        cell.appendChild(img);
        var del = document.createElement('button');
        del.type = 'button';
        del.className = 'be-gallery-del';
        del.innerHTML = '&times;';
        del.addEventListener('click', function () { self.data.images.splice(i, 1); self.renderGrid(); markDirty(); });
        cell.appendChild(del);
        self.grid.appendChild(cell);
      });
      if (!this.data.images.length) {
        this.grid.innerHTML = '<div class="be-gallery-empty"><i class="fas fa-images"></i> No images yet</div>';
      }
    }
    pick() {
      var self = this;
      var input = document.createElement('input');
      input.type = 'file'; input.accept = 'image/*'; input.multiple = true;
      input.onchange = function () {
        if (!input.files.length) return;
        var fd = new FormData();
        for (var i = 0; i < input.files.length; i++) fd.append('files', input.files[i]);
        toast('Uploading images…');
        fetch(self.config.uploadUrl, { method: 'POST', headers: { 'X-CSRFToken': self.config.csrf }, body: fd })
          .then(function (r) { return r.json(); })
          .then(function (j) {
            (j.data || []).forEach(function (u) { self.data.images.push(u); });
            self.renderGrid(); markDirty();
            toast((j.data || []).length + ' image(s) added');
          })
          .catch(function () { toast('Upload failed'); });
      };
      input.click();
    }
    save() { return { images: this.data.images }; }
    static get sanitize() { return { images: false }; }
  }

  class CaptionTool {
    static get toolbox() { return { title: 'Caption', icon: '<svg width="16" height="16" viewBox="0 0 16 16"><path fill="currentColor" d="M1 4h14v8H1zM3 6.5h4V8H3zM9 6.5h4V8H9z"/></svg>' }; }
    constructor(o) { this.api = o.api; this.data = { text: (o.data && o.data.text) || '' }; }
    render() {
      this.el = document.createElement('div');
      this.el.className = 'be-caption-tool';
      this.el.contentEditable = 'true';
      this.el.dataset.placeholder = 'Caption or credit…';
      this.el.innerHTML = this.data.text;
      return this.el;
    }
    save(el) { return { text: el.innerHTML }; }
    static get sanitize() { return { text: { br: true, b: {}, i: {}, a: { href: true } } }; }
  }

  /* =====================================================================
     Phase 3 — Canva-style design blocks
  ===================================================================== */
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function num(v, d) { v = parseFloat(v); return isNaN(v) ? d : v; }
  function iconBtn(icon, title) { var b = el('button', 'be-des-btn', '<i class="fas ' + icon + '"></i>'); b.type = 'button'; b.title = title || ''; return b; }
  function beUpload(file) {
    var fd = new FormData(); fd.append('image', file);
    return fetch(CFG.uploadUrl, { method: 'POST', headers: { 'X-CSRFToken': CFG.csrf }, body: fd }).then(function (r) { return r.json(); });
  }
  var CALLOUT_ICONS = { info: 'fa-circle-info', success: 'fa-circle-check', warning: 'fa-triangle-exclamation', idea: 'fa-lightbulb', quote: 'fa-quote-right', note: 'fa-pen' };
  var CALLOUT_V = ['info', 'success', 'warning', 'idea', 'quote', 'note'];
  var IMG_LAYOUTS = ['contained', 'wide', 'full', 'left', 'right'];

  class AdvancedImage {
    static get toolbox() { return { title: 'Image', icon: '<svg width="17" height="15" viewBox="0 0 512 512"><path fill="currentColor" d="M448 80c8.8 0 16 7.2 16 16V416c0 8.8-7.2 16-16 16H64c-8.8 0-16-7.2-16-16V96c0-8.8 7.2-16 16-16H448zM64 32C28.7 32 0 60.7 0 96V416c0 35.3 28.7 64 64 64H448c35.3 0 64-28.7 64-64V96c0-35.3-28.7-64-64-64H64zM189.3 226.7l-90.7 121.3H413.3l-64-85.3-42.7 56.9-58.7-92.9zM128 176a32 32 0 1 0 0-64 32 32 0 1 0 0 64z"/></svg>' }; }
    static get sanitize() { return { url: false, caption: { br: true, b: {}, i: {}, a: { href: true } }, alt: false, layout: false, filters: false, opacity: false, radius: false, rotate: false, flipH: false, flipV: false, border: false, shadow: false }; }
    constructor(o) {
      this.api = o.api;
      var d = o.data || {}, f = d.file || {}, fl = d.filters || {};
      this.data = {
        url: d.url || f.url || '', caption: d.caption || '', alt: d.alt || '',
        layout: IMG_LAYOUTS.indexOf(d.layout) >= 0 ? d.layout : (d.stretched ? 'full' : 'contained'),
        filters: { brightness: num(fl.brightness, 100), contrast: num(fl.contrast, 100), saturate: num(fl.saturate, 100) },
        opacity: num(d.opacity, 100), radius: num(d.radius, 0), rotate: num(d.rotate, 0),
        flipH: !!d.flipH, flipV: !!d.flipV, border: !!(d.border || d.withBorder), shadow: !!d.shadow
      };
    }
    render() { this.wrap = el('div', 'be-aimg'); this.data.url ? this.renderImage() : this.renderUploader(); return this.wrap; }
    renderUploader() {
      var self = this; this.wrap.innerHTML = '';
      var up = el('div', 'be-aimg-upload', '<i class="fas fa-image"></i><span>Upload an image or paste a URL</span>');
      var pick = el('button', 'be-aimg-pick', 'Choose file'); pick.type = 'button';
      var urlin = el('input', 'be-input'); urlin.placeholder = 'Paste image URL';
      pick.addEventListener('click', function () { self.pickFile(); });
      urlin.addEventListener('change', function () { if (urlin.value.trim()) { self.data.url = urlin.value.trim(); self.renderImage(); markDirty(); scheduleSave(); } });
      up.appendChild(pick); this.wrap.appendChild(up); this.wrap.appendChild(urlin);
    }
    pickFile() {
      var self = this, input = el('input'); input.type = 'file'; input.accept = 'image/*';
      input.onchange = function () {
        if (!input.files.length) return; toast('Uploading…');
        beUpload(input.files[0]).then(function (j) { if (j.success && j.file) { self.data.url = j.file.url; self.renderImage(); markDirty(); scheduleSave(); toast('Image added'); } else toast(j.message || 'Upload failed'); }).catch(function () { toast('Upload failed'); });
      };
      input.click();
    }
    renderImage() {
      var self = this; this.wrap.innerHTML = '';
      this.fig = el('figure', 'be-aimg-fig');
      this.img = el('img'); this.img.src = this.data.url; this.img.alt = this.data.alt;
      this.fig.appendChild(this.img); this.wrap.appendChild(this.fig);
      this.wrap.appendChild(this.buildBar());
      this.adjustPanel = this.buildAdjust(); this.wrap.appendChild(this.adjustPanel);
      this.cap = el('div', 'be-aimg-cap'); this.cap.contentEditable = 'true'; this.cap.dataset.placeholder = 'Add a caption…'; this.cap.innerHTML = this.data.caption;
      this.cap.addEventListener('input', function () { markDirty(); scheduleSave(); });
      this.wrap.appendChild(this.cap);
      this.applyStyle();
    }
    buildBar() {
      var self = this, bar = el('div', 'be-aimg-bar');
      var g1 = el('div', 'be-des-group'); this.layoutBtns = {};
      [['contained', 'fa-image', 'Contained'], ['wide', 'fa-left-right', 'Wide'], ['full', 'fa-expand', 'Full width'], ['left', 'fa-align-left', 'Float left'], ['right', 'fa-align-right', 'Float right']].forEach(function (L) {
        var b = iconBtn(L[1], L[2]); if (self.data.layout === L[0]) b.classList.add('is-active');
        b.addEventListener('click', function () { self.data.layout = L[0]; self.applyStyle(); markDirty(); scheduleSave(); });
        self.layoutBtns[L[0]] = b; g1.appendChild(b);
      });
      var g2 = el('div', 'be-des-group');
      var rot = iconBtn('fa-rotate-right', 'Rotate 90°'); rot.addEventListener('click', function () { self.data.rotate = (self.data.rotate + 90) % 360; self.applyStyle(); markDirty(); scheduleSave(); });
      var fh = iconBtn('fa-arrows-left-right', 'Flip horizontal'); if (self.data.flipH) fh.classList.add('is-active'); fh.addEventListener('click', function () { self.data.flipH = !self.data.flipH; fh.classList.toggle('is-active', self.data.flipH); self.applyStyle(); markDirty(); scheduleSave(); });
      var fv = iconBtn('fa-arrows-up-down', 'Flip vertical'); if (self.data.flipV) fv.classList.add('is-active'); fv.addEventListener('click', function () { self.data.flipV = !self.data.flipV; fv.classList.toggle('is-active', self.data.flipV); self.applyStyle(); markDirty(); scheduleSave(); });
      g2.appendChild(rot); g2.appendChild(fh); g2.appendChild(fv);
      var g3 = el('div', 'be-des-group');
      var bd = iconBtn('fa-border-all', 'Border'); if (self.data.border) bd.classList.add('is-active'); bd.addEventListener('click', function () { self.data.border = !self.data.border; bd.classList.toggle('is-active', self.data.border); self.applyStyle(); markDirty(); scheduleSave(); });
      var sh = iconBtn('fa-clone', 'Shadow'); if (self.data.shadow) sh.classList.add('is-active'); sh.addEventListener('click', function () { self.data.shadow = !self.data.shadow; sh.classList.toggle('is-active', self.data.shadow); self.applyStyle(); markDirty(); scheduleSave(); });
      var adj = iconBtn('fa-sliders', 'Adjust filters'); adj.addEventListener('click', function () { self.adjustPanel.style.display = self.adjustPanel.style.display === 'none' ? 'block' : 'none'; });
      var rep = iconBtn('fa-arrows-rotate', 'Replace image'); rep.addEventListener('click', function () { self.data.url = ''; self.renderUploader(); markDirty(); });
      g3.appendChild(bd); g3.appendChild(sh); g3.appendChild(adj); g3.appendChild(rep);
      bar.appendChild(g1); bar.appendChild(g2); bar.appendChild(g3);
      return bar;
    }
    buildAdjust() {
      var self = this, p = el('div', 'be-aimg-adjust'); p.style.display = 'none';
      function slider(label, min, max, get, set) {
        var row = el('div', 'be-slider-row'); var val = el('span', 'be-slider-val', get());
        var inp = el('input'); inp.type = 'range'; inp.min = min; inp.max = max; inp.value = get();
        inp.addEventListener('input', function () { set(parseFloat(inp.value)); val.textContent = get(); self.applyStyle(); markDirty(); });
        inp.addEventListener('change', scheduleSave);
        row.appendChild(el('label', null, label)); row.appendChild(inp); row.appendChild(val); return row;
      }
      p.appendChild(slider('Brightness', 0, 200, function () { return self.data.filters.brightness; }, function (v) { self.data.filters.brightness = v; }));
      p.appendChild(slider('Contrast', 0, 200, function () { return self.data.filters.contrast; }, function (v) { self.data.filters.contrast = v; }));
      p.appendChild(slider('Saturation', 0, 200, function () { return self.data.filters.saturate; }, function (v) { self.data.filters.saturate = v; }));
      p.appendChild(slider('Opacity', 0, 100, function () { return self.data.opacity; }, function (v) { self.data.opacity = v; }));
      p.appendChild(slider('Roundness', 0, 60, function () { return self.data.radius; }, function (v) { self.data.radius = v; }));
      var altrow = el('div', 'be-slider-row'); var altin = el('input', 'be-input'); altin.value = self.data.alt; altin.placeholder = 'Alt text (accessibility)';
      altin.addEventListener('input', function () { self.data.alt = altin.value; self.img.alt = altin.value; markDirty(); scheduleSave(); });
      altrow.appendChild(el('label', null, 'Alt')); altrow.appendChild(altin); p.appendChild(altrow);
      var reset = el('button', 'be-des-reset', 'Reset adjustments'); reset.type = 'button';
      reset.addEventListener('click', function () { self.data.filters = { brightness: 100, contrast: 100, saturate: 100 }; self.data.opacity = 100; self.data.radius = 0; self.data.rotate = 0; self.data.flipH = false; self.data.flipV = false; self.renderImage(); self.adjustPanel.style.display = 'block'; markDirty(); scheduleSave(); });
      p.appendChild(reset); return p;
    }
    applyStyle() {
      var d = this.data, f = [], t = [];
      if (d.filters.brightness != 100) f.push('brightness(' + d.filters.brightness + '%)');
      if (d.filters.contrast != 100) f.push('contrast(' + d.filters.contrast + '%)');
      if (d.filters.saturate != 100) f.push('saturate(' + d.filters.saturate + '%)');
      if (d.rotate) t.push('rotate(' + d.rotate + 'deg)');
      if (d.flipH) t.push('scaleX(-1)'); if (d.flipV) t.push('scaleY(-1)');
      this.img.style.filter = f.join(' '); this.img.style.transform = t.join(' ');
      this.img.style.opacity = d.opacity / 100; this.img.style.borderRadius = d.radius + 'px';
      this.fig.className = 'be-aimg-fig be-aimg-' + d.layout + (d.border ? ' be-aimg-border' : '') + (d.shadow ? ' be-aimg-shadow' : '');
      if (this.layoutBtns) for (var k in this.layoutBtns) this.layoutBtns[k].classList.toggle('is-active', k === d.layout);
    }
    save() { if (this.cap) this.data.caption = this.cap.innerHTML; return this.data; }
  }

  class CalloutTool {
    static get toolbox() { return { title: 'Callout', icon: '<svg width="16" height="16" viewBox="0 0 512 512"><path fill="currentColor" d="M256 512A256 256 0 1 0 256 0a256 256 0 1 0 0 512zm-40-176h24V272H216c-13.3 0-24-10.7-24-24s10.7-24 24-24h48c13.3 0 24 10.7 24 24v88h8c13.3 0 24 10.7 24 24s-10.7 24-24 24H216c-13.3 0-24-10.7-24-24s10.7-24 24-24zm40-208a32 32 0 1 1 0 64 32 32 0 1 1 0-64z"/></svg>' }; }
    static get sanitize() { return { variant: false, icon: false, text: { br: true, b: {}, i: {}, u: {}, a: { href: true }, mark: {}, span: { style: true, 'class': true } } }; }
    constructor(o) { this.api = o.api; var d = o.data || {}; this.data = { variant: CALLOUT_V.indexOf(d.variant) >= 0 ? d.variant : 'info', icon: d.icon || '', text: d.text || '' }; }
    render() {
      var self = this;
      this.wrap = el('div', 'be-callout pc-callout pc-callout-' + this.data.variant);
      this.iconEl = el('span', 'pc-callout-icon', '<i class="fas ' + (this.data.icon || CALLOUT_ICONS[this.data.variant]) + '"></i>');
      this.body = el('div', 'pc-callout-body'); this.body.contentEditable = 'true'; this.body.dataset.placeholder = 'Write a callout…'; this.body.innerHTML = this.data.text;
      this.body.addEventListener('input', function () { markDirty(); scheduleSave(); });
      var picker = el('div', 'be-callout-picker');
      CALLOUT_V.forEach(function (v) {
        var b = el('button', 'be-cv be-cv-' + v, '<i class="fas ' + CALLOUT_ICONS[v] + '"></i>'); b.type = 'button'; b.title = v; if (v === self.data.variant) b.classList.add('is-active');
        b.addEventListener('click', function () { self.data.variant = v; self.data.icon = ''; self.wrap.className = 'be-callout pc-callout pc-callout-' + v; self.iconEl.innerHTML = '<i class="fas ' + CALLOUT_ICONS[v] + '"></i>'; [].forEach.call(picker.children, function (c) { c.classList.remove('is-active'); }); b.classList.add('is-active'); markDirty(); scheduleSave(); });
        picker.appendChild(b);
      });
      this.wrap.appendChild(this.iconEl); this.wrap.appendChild(this.body); this.wrap.appendChild(picker);
      return this.wrap;
    }
    save() { return { variant: this.data.variant, icon: this.data.icon, text: this.body.innerHTML }; }
  }

  class ButtonTool {
    static get toolbox() { return { title: 'Button', icon: '<svg width="18" height="14" viewBox="0 0 576 512"><path fill="currentColor" d="M64 112c-8.8 0-16 7.2-16 16V384c0 8.8 7.2 16 16 16H512c8.8 0 16-7.2 16-16V128c0-8.8-7.2-16-16-16H64zM0 128C0 92.7 28.7 64 64 64H512c35.3 0 64 28.7 64 64V384c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V128z"/></svg>' }; }
    static get sanitize() { return { label: false, url: false, style: false, align: false }; }
    constructor(o) { this.api = o.api; var d = o.data || {}; this.data = { label: d.label || 'Click here', url: d.url || '', style: ['solid', 'outline', 'soft'].indexOf(d.style) >= 0 ? d.style : 'solid', align: ['left', 'center', 'right'].indexOf(d.align) >= 0 ? d.align : 'left' }; }
    render() {
      var self = this; this.wrap = el('div', 'be-btnblock');
      this.pv = el('div', 'be-btn-preview pc-align-' + this.data.align);
      this.btn = el('a', 'pc-btn pc-btn-' + this.data.style); this.btn.contentEditable = 'true'; this.btn.innerHTML = this.data.label;
      this.btn.addEventListener('input', function () { markDirty(); scheduleSave(); });
      this.btn.addEventListener('keydown', function (e) { if (e.key === 'Enter') e.preventDefault(); });
      this.pv.appendChild(this.btn);
      var c = el('div', 'be-des-controls');
      var urlin = el('input', 'be-input'); urlin.placeholder = 'https://…'; urlin.value = this.data.url;
      urlin.addEventListener('input', function () { self.data.url = urlin.value; markDirty(); scheduleSave(); });
      var ss = el('select', 'be-select'); ['solid', 'outline', 'soft'].forEach(function (s) { var o2 = el('option', null, s); o2.value = s; if (s === self.data.style) o2.selected = true; ss.appendChild(o2); });
      ss.addEventListener('change', function () { self.data.style = ss.value; self.btn.className = 'pc-btn pc-btn-' + ss.value; markDirty(); scheduleSave(); });
      var ag = el('div', 'be-des-group'); ['left', 'center', 'right'].forEach(function (a) { var b = iconBtn('fa-align-' + a, a); if (a === self.data.align) b.classList.add('is-active'); b.addEventListener('click', function () { self.data.align = a; self.pv.className = 'be-btn-preview pc-align-' + a; [].forEach.call(ag.children, function (x) { x.classList.remove('is-active'); }); b.classList.add('is-active'); markDirty(); scheduleSave(); }); ag.appendChild(b); });
      c.appendChild(urlin); c.appendChild(ss); c.appendChild(ag);
      this.wrap.appendChild(this.pv); this.wrap.appendChild(c); return this.wrap;
    }
    save() { return { label: this.btn.textContent, url: this.data.url, style: this.data.style, align: this.data.align }; }
  }

  class HeroTool {
    static get toolbox() { return { title: 'Hero / Banner', icon: '<svg width="18" height="14" viewBox="0 0 576 512"><path fill="currentColor" d="M0 96C0 60.7 28.7 32 64 32H512c35.3 0 64 28.7 64 64V416c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V96zm352 96a48 48 0 1 0 0-96 48 48 0 1 0 0 96zM64 384H512V320l-96-96-96 96-64-64L64 448V384z"/></svg>' }; }
    static get sanitize() { return { heading: { br: true, b: {}, i: {} }, subheading: { br: true, b: {}, i: {} }, image: false, bg: false, align: false, height: false, buttonLabel: false, buttonUrl: false }; }
    constructor(o) { this.api = o.api; var d = o.data || {}; this.data = { heading: d.heading || '', subheading: d.subheading || '', image: d.image || '', bg: /^#[0-9a-fA-F]{3,8}$/.test(d.bg || '') ? d.bg : '#5C4A3D', align: ['left', 'center', 'right'].indexOf(d.align) >= 0 ? d.align : 'center', height: ['small', 'medium', 'large'].indexOf(d.height) >= 0 ? d.height : 'medium', buttonLabel: d.buttonLabel || '', buttonUrl: d.buttonUrl || '' }; }
    render() {
      var self = this; this.wrap = el('div', 'be-heroblock');
      this.hero = el('div', 'be-hero-edit be-hero-' + this.data.height + ' pc-align-' + this.data.align);
      this.h = el('div', 'be-hero-h'); this.h.contentEditable = 'true'; this.h.dataset.placeholder = 'Hero heading'; this.h.innerHTML = this.data.heading;
      this.sub = el('div', 'be-hero-sub'); this.sub.contentEditable = 'true'; this.sub.dataset.placeholder = 'Supporting text'; this.sub.innerHTML = this.data.subheading;
      this.h.addEventListener('input', function () { markDirty(); scheduleSave(); });
      this.sub.addEventListener('input', function () { markDirty(); scheduleSave(); });
      this.hero.appendChild(this.h); this.hero.appendChild(this.sub);
      this.applyBg(); this.wrap.appendChild(this.hero);
      var c = el('div', 'be-des-controls');
      var imgb = el('button', 'be-des-cbtn', '<i class="fas fa-image"></i> Image'); imgb.type = 'button'; imgb.addEventListener('click', function () { self.pickBg(); });
      var color = el('input'); color.type = 'color'; color.value = this.data.bg; color.title = 'Background color'; color.addEventListener('input', function () { self.data.bg = color.value; self.data.image = ''; self.applyBg(); markDirty(); scheduleSave(); });
      var clr = el('button', 'be-des-cbtn', 'Clear image'); clr.type = 'button'; clr.addEventListener('click', function () { self.data.image = ''; self.applyBg(); markDirty(); scheduleSave(); });
      var hs = el('select', 'be-select'); ['small', 'medium', 'large'].forEach(function (hh) { var o2 = el('option', null, hh); o2.value = hh; if (hh === self.data.height) o2.selected = true; hs.appendChild(o2); }); hs.addEventListener('change', function () { self.data.height = hs.value; self.syncHeroClass(); markDirty(); scheduleSave(); });
      var ag = el('div', 'be-des-group'); ['left', 'center', 'right'].forEach(function (a) { var b = iconBtn('fa-align-' + a, a); if (a === self.data.align) b.classList.add('is-active'); b.addEventListener('click', function () { self.data.align = a; self.syncHeroClass(); [].forEach.call(ag.children, function (x) { x.classList.remove('is-active'); }); b.classList.add('is-active'); markDirty(); scheduleSave(); }); ag.appendChild(b); });
      var bl = el('input', 'be-input'); bl.placeholder = 'Button label (optional)'; bl.value = this.data.buttonLabel; bl.addEventListener('input', function () { self.data.buttonLabel = bl.value; markDirty(); scheduleSave(); });
      var bu = el('input', 'be-input'); bu.placeholder = 'Button URL'; bu.value = this.data.buttonUrl; bu.addEventListener('input', function () { self.data.buttonUrl = bu.value; markDirty(); scheduleSave(); });
      [imgb, color, clr, hs, ag, bl, bu].forEach(function (x) { c.appendChild(x); });
      this.wrap.appendChild(c); return this.wrap;
    }
    syncHeroClass() { this.hero.className = 'be-hero-edit be-hero-' + this.data.height + ' pc-align-' + this.data.align + (this.data.image ? ' be-hero-hasimg' : ''); }
    applyBg() {
      if (this.data.image) { this.hero.style.background = ''; this.hero.style.backgroundImage = "linear-gradient(rgba(0,0,0,.35),rgba(0,0,0,.35)),url('" + this.data.image + "')"; }
      else { this.hero.style.backgroundImage = ''; this.hero.style.background = this.data.bg; }
      this.syncHeroClass();
    }
    pickBg() { var self = this, input = el('input'); input.type = 'file'; input.accept = 'image/*'; input.onchange = function () { if (!input.files.length) return; toast('Uploading…'); beUpload(input.files[0]).then(function (j) { if (j.success && j.file) { self.data.image = j.file.url; self.applyBg(); markDirty(); scheduleSave(); toast('Background set'); } else toast(j.message || 'Upload failed'); }); }; input.click(); }
    save() { return { heading: this.h.innerHTML, subheading: this.sub.innerHTML, image: this.data.image, bg: this.data.bg, align: this.data.align, height: this.data.height, buttonLabel: this.data.buttonLabel, buttonUrl: this.data.buttonUrl }; }
  }

  /* =====================================================================
     Editor init
  ===================================================================== */
  var state = { ready: false, dirty: false, saving: false, postId: CFG.postId || null };
  var editor = new EditorJS({
    holder: 'editorjs',
    autofocus: false,
    placeholder: "Start writing, or press '/' to add a block…",
    data: window.BE_INITIAL_DOC || {},
    inlineToolbar: ['bold', 'italic', 'underline', 'strike', 'link', 'color', 'highlight', 'fontSize', 'fontFamily', 'inlineCode'],
    tools: {
      header: { class: Header, inlineToolbar: true, config: { levels: [2, 3, 4], defaultLevel: 2, placeholder: 'Heading' } },
      list: { class: NestedList, inlineToolbar: true, config: { defaultStyle: 'unordered' } },
      checklist: { class: Checklist, inlineToolbar: true },
      quote: { class: Quote, inlineToolbar: true, config: { quotePlaceholder: 'Quote', captionPlaceholder: 'Attribution' } },
      code: { class: CodeTool, config: { placeholder: 'Code' } },
      delimiter: { class: Delimiter },
      table: { class: Table, inlineToolbar: true },
      image: { class: AdvancedImage },
      callout: { class: CalloutTool, inlineToolbar: true },
      button: { class: ButtonTool },
      hero: { class: HeroTool, inlineToolbar: true },
      gallery: { class: GalleryTool, config: { uploadUrl: CFG.galleryUrl, csrf: CFG.csrf } },
      caption: { class: CaptionTool },
      // inline
      underline: { class: Underline }, strike: { class: Strike }, inlineCode: { class: InlineCode },
      color: { class: TextColor }, highlight: { class: Highlight },
      fontSize: { class: FontSize }, fontFamily: { class: FontFamily },
      // tunes
      alignment: { class: AlignmentTune }, lineHeight: { class: LineHeightTune }, duplicate: { class: DuplicateTune }
    },
    tunes: ['alignment', 'lineHeight', 'duplicate'],
    onReady: function () {
      try { new Undo({ editor: editor }); } catch (e) { console.warn('undo init', e); }
      try { new DragDrop(editor); } catch (e) { console.warn('dragdrop init', e); }
      Popover.init();
      setTimeout(function () { state.ready = true; recount(); rebuildOutline(); }, 400);
    },
    onChange: function () {
      if (!state.ready) return;
      markDirty();
      recount();
      debounce(rebuildOutline, 400)();
      scheduleSave();
    }
  });

  /* =====================================================================
     Insert helpers (shared by slash menu + palette)
  ===================================================================== */
  function insertBlock(type, data) {
    var idx;
    try { idx = editor.blocks.getCurrentBlockIndex(); } catch (e) { idx = -1; }
    var replace = false;
    if (idx >= 0) {
      var blk = editor.blocks.getBlockByIndex(idx);
      // Only swap out an empty *paragraph* — never a freshly-inserted design block.
      if (blk && blk.isEmpty && blk.name === 'paragraph') { replace = true; }
    }
    var at = (idx >= 0) ? (replace ? idx : idx + 1) : editor.blocks.getBlocksCount();
    editor.blocks.insert(type, data || {}, {}, at, true, replace);
    markDirty(); recount(); scheduleSave();
  }

  var BLOCK_MENU = [
    { type: 'paragraph', label: 'Text', icon: 'fa-paragraph', keys: 'text paragraph body' },
    { type: 'header', data: { level: 2 }, label: 'Heading', icon: 'fa-heading', keys: 'heading h2 title' },
    { type: 'header', data: { level: 3 }, label: 'Subheading', icon: 'fa-heading', keys: 'subheading h3' },
    { type: 'header', data: { level: 4 }, label: 'Small heading', icon: 'fa-heading', keys: 'h4 minor small' },
    { type: 'list', data: { style: 'unordered' }, label: 'Bulleted list', icon: 'fa-list-ul', keys: 'list bullet unordered ul' },
    { type: 'list', data: { style: 'ordered' }, label: 'Numbered list', icon: 'fa-list-ol', keys: 'numbered ordered ol' },
    { type: 'checklist', label: 'Checklist', icon: 'fa-square-check', keys: 'todo check task checklist' },
    { type: 'quote', label: 'Quote', icon: 'fa-quote-right', keys: 'quote blockquote' },
    { type: 'code', label: 'Code block', icon: 'fa-code', keys: 'code snippet' },
    { type: 'delimiter', label: 'Divider', icon: 'fa-grip-lines', keys: 'divider hr delimiter separator line' },
    { type: 'image', label: 'Image', icon: 'fa-image', keys: 'image img photo picture' },
    { type: 'gallery', label: 'Gallery', icon: 'fa-images', keys: 'gallery grid collage images carousel' },
    { type: 'hero', label: 'Hero / Banner', icon: 'fa-panorama', keys: 'hero banner cover section header' },
    { type: 'callout', label: 'Callout', icon: 'fa-circle-info', keys: 'callout note box tip info warning idea' },
    { type: 'button', label: 'Button', icon: 'fa-hand-pointer', keys: 'button cta link action' },
    { type: 'table', label: 'Table', icon: 'fa-table', keys: 'table grid' },
    { type: 'caption', label: 'Caption', icon: 'fa-closed-captioning', keys: 'caption credit small' }
  ];

  /* =====================================================================
     Slash menu — handled natively by Editor.js (type "/" in an empty block
     to open its searchable toolbox, incl. our Gallery/Caption/Image tools).
     The left palette below is the click-to-insert alternative.
  ===================================================================== */

  /* =====================================================================
     Left panel: block palette + outline
  ===================================================================== */
  (function buildPalette() {
    var pal = document.getElementById('bePalette');
    BLOCK_MENU.forEach(function (it) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'be-pal-item';
      b.innerHTML = '<i class="fas ' + it.icon + '"></i><span>' + it.label + '</span>';
      b.addEventListener('click', function () { insertBlock(it.type, it.data); });
      pal.appendChild(b);
    });
  })();

  function rebuildOutline() {
    var out = document.getElementById('beOutline');
    var heads = document.querySelectorAll('#editorjs h1, #editorjs h2, #editorjs h3, #editorjs h4');
    if (!heads.length) { out.innerHTML = '<p class="be-hint">Headings will appear here as you write.</p>'; return; }
    out.innerHTML = '';
    [].forEach.call(heads, function (h) {
      var lvl = h.tagName.toLowerCase();
      var a = document.createElement('a');
      a.className = 'be-outline-item be-o-' + lvl;
      a.textContent = h.textContent || 'Untitled heading';
      a.addEventListener('click', function () { h.scrollIntoView({ behavior: 'smooth', block: 'center' }); });
      out.appendChild(a);
    });
  }

  /* =====================================================================
     Counts (words / reading time / blocks)
  ===================================================================== */
  function recount() {
    // Count only block content — not the Editor.js toolbox/popover labels
    // that also live inside #editorjs.
    var parts = [];
    [].forEach.call(document.querySelectorAll('#editorjs .ce-block__content'), function (b) { parts.push(b.innerText || ''); });
    var text = parts.join(' ').trim();
    var words = text ? (text.match(/\S+/g) || []).length : 0;
    var mins = words ? Math.max(1, Math.ceil(words / 200)) : 0;
    var blocks = 0; try { blocks = editor.blocks.getBlocksCount(); } catch (e) {}
    setText('beWords', words + (words === 1 ? ' word' : ' words'));
    setText('beRead', mins + ' min read');
    setText('beStatWords', words); setText('beStatRead', mins); setText('beStatBlocks', blocks);
  }

  /* =====================================================================
     Autosave / publish
  ===================================================================== */
  var els = {
    title: document.getElementById('beTitle'),
    subtitle: document.getElementById('beSubtitle'),
    category: document.getElementById('beCategory'),
    coverUrl: document.getElementById('beCoverUrl'),
    coverFile: document.getElementById('beCoverFile'),
    coverPrev: document.getElementById('beCoverPreview'),
    slug: document.getElementById('beSlug'),
    tags: document.getElementById('beTags'),
    excerpt: document.getElementById('beExcerpt'),
    metaTitle: document.getElementById('beMetaTitle'),
    metaDesc: document.getElementById('beMetaDesc'),
    ogImage: document.getElementById('beOgImage'),
    canonical: document.getElementById('beCanonical'),
    publishAt: document.getElementById('bePublishAt'),
    contentWidth: document.getElementById('beContentWidth'),
    pageBg: document.getElementById('bePageBg'),
    pageBgColor: document.getElementById('bePageBgColor'),
    pageBgClear: document.getElementById('bePageBgClear')
  };
  function parseTags(v) {
    return (v || '').split(',').map(function (t) { return t.trim(); }).filter(Boolean);
  }

  function docHasContent(saved) {
    if (els.title.value.trim() || els.subtitle.value.trim() || els.coverUrl.value.trim()) return true;
    return (saved.blocks || []).some(function (b) {
      var d = b.data || {};
      if (d.text && d.text.replace(/<[^>]+>/g, '').trim()) return true;
      if (d.items && d.items.length) return true;
      if (d.images && d.images.length) return true;
      if (d.file && d.file.url) return true;
      if (d.code && d.code.trim()) return true;
      if (b.type === 'delimiter' || b.type === 'table') return true;
      return false;
    });
  }

  function setStatus(stateName, text) {
    var el = document.getElementById('beStatus');
    el.dataset.state = stateName;
    setText('beStatusText', text);
  }

  var saveTimer = null;
  function scheduleSave() {
    if (saveTimer) clearTimeout(saveTimer);
    setStatus('unsaved', 'Unsaved…');
    saveTimer = setTimeout(function () { doSave(false); }, 1400);
  }

  function doSave(manual) {
    if (state.saving) { return Promise.resolve(state.postId); }
    return editor.save().then(function (saved) {
      if (!docHasContent(saved)) {
        setStatus('idle', 'Empty');
        return null;
      }
      state.saving = true;
      setStatus('saving', 'Saving…');
      var payload = {
        id: state.postId,
        title: els.title.value.trim(),
        subtitle: els.subtitle.value.trim(),
        category_id: els.category.value ? parseInt(els.category.value, 10) : null,
        media_url: els.coverUrl.value.trim(),
        slug: els.slug.value.trim(),
        tags: parseTags(els.tags.value),
        excerpt: els.excerpt.value.trim(),
        meta_title: els.metaTitle.value.trim(),
        meta_description: els.metaDesc.value.trim(),
        og_image: els.ogImage.value.trim(),
        canonical_url: els.canonical.value.trim(),
        content_width: els.contentWidth.value,
        page_bg: els.pageBg.value.trim(),
        content_json: saved
      };
      return fetch(CFG.autosaveUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CFG.csrf },
        body: JSON.stringify(payload)
      }).then(function (r) { return r.json(); }).then(function (j) {
        state.saving = false;
        if (j && j.id) {
          if (!state.postId) {
            state.postId = j.id;
            app.dataset.postId = j.id;
            history.replaceState(null, '', '/edit-post/' + j.id);
          }
          state.dirty = false;
          setStatus('saved', 'Saved');
          setText('beSavedAt', 'Last saved ' + j.saved_at);
          setText('beStatusDetail', (j.status === 'published' ? 'Published' : 'Draft'));
          if (j.slug && !els.slug.value.trim()) els.slug.value = j.slug;  // show auto slug
          if (typeof j.word_count === 'number') { setText('beStatWords', j.word_count); setText('beStatRead', j.reading_time); }
          if (manual) toast('Draft saved');
          return j.id;
        } else {
          setStatus('error', 'Save failed');
          if (manual) toast('Could not save');
          return null;
        }
      });
    }).catch(function () {
      state.saving = false;
      setStatus('error', 'Save failed');
      if (manual) toast('Could not save');
      return null;
    });
  }

  function publish() {
    if (!els.title.value.trim()) { toast('Add a title before publishing'); els.title.focus(); return; }
    var when = els.publishAt.value;
    if (when && new Date(when) > new Date()) {
      if (!confirm('Schedule this post for ' + new Date(when).toLocaleString() + '?')) return;
    }
    setStatus('saving', when ? 'Scheduling…' : 'Publishing…');
    doSave(false).then(function (id) {
      if (!id) { toast('Add some content first'); setStatus('error', 'Nothing to publish'); return; }
      fetch('/api/posts/' + id + '/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CFG.csrf },
        body: JSON.stringify({ publish_at: when || null })
      }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          if (res.ok && res.j.redirect) { window.location.href = res.j.redirect; }
          else { toast(res.j.error || 'Publish failed'); setStatus('error', 'Publish failed'); }
        }).catch(function () { toast('Publish failed'); setStatus('error', 'Publish failed'); });
    });
  }

  /* =====================================================================
     Cover image
  ===================================================================== */
  function setCover(url) {
    els.coverUrl.value = url || '';
    els.coverPrev.innerHTML = url ? '<img src="' + url + '" alt="Cover preview">' : '<span class="be-cover-empty"><i class="fas fa-image"></i> No cover yet</span>';
  }
  els.coverUrl.addEventListener('change', function () { setCover(els.coverUrl.value.trim()); markDirty(); scheduleSave(); });
  els.coverFile.addEventListener('change', function () {
    if (!els.coverFile.files.length) return;
    var fd = new FormData(); fd.append('image', els.coverFile.files[0]);
    toast('Uploading cover…');
    fetch(CFG.uploadUrl, { method: 'POST', headers: { 'X-CSRFToken': CFG.csrf }, body: fd })
      .then(function (r) { return r.json(); })
      .then(function (j) { if (j.success && j.file) { setCover(j.file.url); markDirty(); scheduleSave(); toast('Cover updated'); } else { toast(j.message || 'Upload failed'); } })
      .catch(function () { toast('Upload failed'); });
  });

  /* =====================================================================
     Shell interactions
  ===================================================================== */
  document.getElementById('beSaveBtn').addEventListener('click', function () { doSave(true); });
  document.getElementById('bePublishBtn').addEventListener('click', publish);

  els.title.addEventListener('input', function () { markDirty(); scheduleSave(); });
  els.subtitle.addEventListener('input', function () { markDirty(); scheduleSave(); });
  els.category.addEventListener('change', function () { markDirty(); scheduleSave(); });
  [els.slug, els.tags, els.excerpt, els.metaTitle, els.metaDesc, els.ogImage, els.canonical].forEach(function (el) {
    if (el) el.addEventListener('input', function () { markDirty(); scheduleSave(); });
  });

  // Page design: content width + background (with a live preview on the canvas)
  function applyPageBg() {
    var bg = els.pageBg.value.trim();
    document.getElementById('beCanvas').style.background = bg || '';
  }
  els.contentWidth.addEventListener('change', function () { markDirty(); scheduleSave(); });
  els.pageBg.addEventListener('input', function () { applyPageBg(); markDirty(); scheduleSave(); });
  els.pageBgColor.addEventListener('input', function () { els.pageBg.value = els.pageBgColor.value; applyPageBg(); markDirty(); scheduleSave(); });
  els.pageBgClear.addEventListener('click', function () { els.pageBg.value = ''; applyPageBg(); markDirty(); scheduleSave(); });
  applyPageBg();

  // Device preview
  [].forEach.call(document.querySelectorAll('.be-device-btn'), function (btn) {
    btn.addEventListener('click', function () {
      [].forEach.call(document.querySelectorAll('.be-device-btn'), function (b) { b.classList.remove('is-active'); });
      btn.classList.add('is-active');
      document.getElementById('beCanvas').dataset.device = btn.dataset.device;
    });
  });

  // Distraction-free
  var focusBtn = document.getElementById('beFocusBtn');
  function toggleFocus() {
    document.body.classList.toggle('be-focus');
    var on = document.body.classList.contains('be-focus');
    focusBtn.innerHTML = on ? '<i class="fas fa-compress"></i>' : '<i class="fas fa-expand"></i>';
  }
  focusBtn.addEventListener('click', toggleFocus);
  document.addEventListener('keydown', function (e) {
    if (e.altKey && (e.key === 'z' || e.key === 'Z')) { e.preventDefault(); toggleFocus(); }
  });

  // Theme toggle
  var themeBtn = document.getElementById('beThemeBtn');
  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem('theme', t);
    themeBtn.innerHTML = t === 'dark' ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>';
  }
  applyTheme(localStorage.getItem('theme') || 'light');
  themeBtn.addEventListener('click', function () {
    applyTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
  });

  // Panel collapse / reopen
  [].forEach.call(document.querySelectorAll('.be-collapse-btn'), function (btn) {
    btn.addEventListener('click', function () { document.getElementById(btn.dataset.panel).classList.add('is-collapsed'); });
  });
  [].forEach.call(document.querySelectorAll('.be-reopen'), function (btn) {
    btn.addEventListener('click', function () { document.getElementById(btn.dataset.open).classList.remove('is-collapsed'); });
  });

  // Warn on unload with unsaved changes
  window.addEventListener('beforeunload', function (e) {
    if (state.dirty && !state.saving) { e.preventDefault(); e.returnValue = ''; }
  });

  /* =====================================================================
     Utils
  ===================================================================== */
  function markDirty() { state.dirty = true; }
  function setText(id, v) { var el = document.getElementById(id); if (el) el.textContent = v; }
  function debounce(fn, ms) {
    var t; return function () { var a = arguments, c = this; clearTimeout(t); t = setTimeout(function () { fn.apply(c, a); }, ms); };
  }
  var toastTimer = null;
  function toast(msg) {
    var el = document.getElementById('beToast');
    el.textContent = msg; el.classList.add('is-show');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.classList.remove('is-show'); }, 2200);
  }
})();
