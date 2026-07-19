"""Server-side rendering for the block editor.

The block editor (Editor.js) stores each post as a JSON document of blocks.
We render that JSON to semantic HTML on the server so the published page stays
fast, SEO-friendly, and JavaScript-independent — the rendered HTML is stored in
`BlogPost.body` and shown exactly like the legacy CKEditor posts were.

Also provides:
  - `html_to_blocks`  : best-effort import of legacy CKEditor HTML into blocks
                        so old posts open in the new editor.
  - `estimate_reading_time` : words + reading minutes for the status bar / meta.

Only the site admin authors posts, but inline HTML from blocks is still passed
through a strict bleach allowlist as defense-in-depth.
"""

import json
import re
import math
from html import escape
from html.parser import HTMLParser

import bleach
from bleach.css_sanitizer import CSSSanitizer

# --- Sanitization allowlist ------------------------------------------------
# Inline formatting the editor can produce inside a block's rich text.
ALLOWED_INLINE_TAGS = [
    "b", "strong", "i", "em", "u", "s", "strike", "del",
    "mark", "a", "code", "br", "span", "sup", "sub",
]
ALLOWED_ATTRS = {
    "a": ["href", "title", "target", "rel"],
    "span": ["style", "class"],
    "mark": ["style", "class"],
    "code": ["class"],
}
ALLOWED_CSS_PROPS = [
    "color", "background-color", "font-family", "font-size", "text-decoration",
]
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

_css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPS)


def clean_inline(text):
    """Sanitize a block's inline rich-text HTML to the inline allowlist."""
    if not text:
        return ""
    return bleach.clean(
        text,
        tags=ALLOWED_INLINE_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=ALLOWED_PROTOCOLS,
        css_sanitizer=_css_sanitizer,
        strip=True,
    )


def _slugify(text, used=None):
    """Heading anchor slug (stable-ish, de-duplicated) for future TOC links."""
    base = re.sub(r"<[^>]+>", "", text or "")
    base = re.sub(r"[^\w\s-]", "", base).strip().lower()
    base = re.sub(r"[\s_-]+", "-", base) or "section"
    if used is None:
        return base
    slug, i = base, 2
    while slug in used:
        slug = f"{base}-{i}"
        i += 1
    used.add(slug)
    return slug


def _loads(content_json):
    if not content_json:
        return {}
    if isinstance(content_json, dict):
        return content_json
    try:
        return json.loads(content_json)
    except (ValueError, TypeError):
        return {}


# --- Block tunes (alignment / line spacing) --------------------------------
_ALIGN = {"left", "center", "right", "justify"}
_LINE_HEIGHTS = {"tight": "1.3", "normal": "", "relaxed": "1.8", "loose": "2.2"}


def _tune_attrs(block):
    """Turn a block's tune data into (class_list, style_str)."""
    tunes = block.get("tunes") or {}
    classes, styles = [], []

    align = (tunes.get("alignment") or {}).get("alignment")
    if align in _ALIGN:
        classes.append(f"pc-align-{align}")

    lh = (tunes.get("lineHeight") or {}).get("value")
    if lh in _LINE_HEIGHTS and _LINE_HEIGHTS[lh]:
        styles.append(f"line-height:{_LINE_HEIGHTS[lh]}")

    cls = f' class="{" ".join(classes)}"' if classes else ""
    sty = f' style="{";".join(styles)}"' if styles else ""
    return cls, sty


# --- Individual block renderers --------------------------------------------
def _render_list_items(items, ordered):
    """Render (possibly nested) list items from @editorjs/nested-list."""
    tag = "ol" if ordered else "ul"
    out = [f"<{tag}>"]
    for item in items:
        if isinstance(item, dict):
            content = clean_inline(item.get("content", ""))
            children = item.get("items") or []
            nested = _render_list_items(children, ordered) if children else ""
            out.append(f"<li>{content}{nested}</li>")
        else:
            out.append(f"<li>{clean_inline(str(item))}</li>")
    out.append(f"</{tag}>")
    return "".join(out)


def _render_block(block, used_anchors):
    btype = block.get("type", "")
    data = block.get("data", {}) or {}
    cls, sty = _tune_attrs(block)

    if btype == "header":
        level = data.get("level", 2)
        level = level if level in (1, 2, 3, 4, 5, 6) else 2
        text = clean_inline(data.get("text", ""))
        anchor = _slugify(data.get("text", ""), used_anchors)
        classes = f"{cls[8:-1]} " if cls else ""  # merge tune class with id
        extra = f' class="{classes.strip()}"' if classes.strip() else ""
        return f'<h{level} id="{anchor}"{extra}{sty}>{text}</h{level}>'

    if btype == "paragraph":
        inner = clean_inline(data.get('text', ''))
        if not re.sub(r"<[^>]+>|&nbsp;|\s", "", inner):
            return ""  # skip empty paragraphs (e.g. trailing blank blocks)
        return f"<p{cls}{sty}>{inner}</p>"

    if btype == "caption":
        merged = (cls.replace('class="', 'class="pc-caption ') if cls
                  else ' class="pc-caption"')
        return f"<p{merged}{sty}>{clean_inline(data.get('text', ''))}</p>"

    if btype in ("list", "nestedList"):
        ordered = data.get("style") == "ordered"
        return _render_list_items(data.get("items", []), ordered)

    if btype == "checklist":
        out = ['<ul class="pc-checklist">']
        for it in data.get("items", []):
            checked = " pc-checked" if it.get("checked") else ""
            out.append(
                f'<li class="pc-check{checked}">'
                f'<span class="pc-check-box" aria-hidden="true"></span>'
                f'<span>{clean_inline(it.get("text", ""))}</span></li>'
            )
        out.append("</ul>")
        return "".join(out)

    if btype == "quote":
        text = clean_inline(data.get("text", ""))
        caption = clean_inline(data.get("caption", ""))
        cap = f"<cite>{caption}</cite>" if caption else ""
        return f"<blockquote{cls}{sty}><p>{text}</p>{cap}</blockquote>"

    if btype == "code":
        return f'<pre class="pc-code"><code>{escape(data.get("code", ""))}</code></pre>'

    if btype == "delimiter":
        return '<hr class="pc-delimiter">'

    if btype == "image":
        f = data.get("file") or {}
        url = f.get("url") or data.get("url") or ""
        if not url:
            return ""
        caption = clean_inline(data.get("caption", ""))
        alt = re.sub(r"<[^>]+>", "", caption) or "image"
        fig_cls = ["pc-image"]
        if data.get("stretched"):
            fig_cls.append("pc-stretched")
        if data.get("withBorder"):
            fig_cls.append("pc-bordered")
        if data.get("withBackground"):
            fig_cls.append("pc-bg")
        if cls:  # alignment tune
            fig_cls.append(cls.split('"')[1])
        figcap = f"<figcaption>{caption}</figcaption>" if caption else ""
        return (f'<figure class="{" ".join(fig_cls)}">'
                f'<img src="{escape(url, quote=True)}" alt="{escape(alt, quote=True)}" loading="lazy">'
                f"{figcap}</figure>")

    if btype == "gallery":
        images = data.get("images", []) or []
        if not images:
            return ""
        cols = data.get("columns") or min(max(len(images), 1), 3)
        cells = []
        for img in images:
            url = img.get("url") if isinstance(img, dict) else img
            if url:
                cells.append(
                    f'<figure><img src="{escape(url, quote=True)}" alt="" loading="lazy"></figure>'
                )
        return f'<div class="post-gallery" style="--pg-cols:{cols}">{"".join(cells)}</div>'

    if btype == "table":
        rows = data.get("content", []) or []
        if not rows:
            return ""
        with_head = data.get("withHeadings")
        out = ['<div class="pc-table-wrap"><table class="pc-table">']
        for r_i, row in enumerate(rows):
            cell_tag = "th" if (with_head and r_i == 0) else "td"
            cells = "".join(f"<{cell_tag}>{clean_inline(c)}</{cell_tag}>" for c in row)
            out.append(f"<tr>{cells}</tr>")
        out.append("</table></div>")
        return "".join(out)

    if btype == "raw":  # defensive: raw HTML block, sanitize fully
        return clean_inline(data.get("html", ""))

    # Unknown/unsupported (e.g. embed, deferred to a later phase): render its
    # caption/text if present, otherwise skip rather than dumping raw data.
    fallback = data.get("caption") or data.get("text")
    return f"<p>{clean_inline(fallback)}</p>" if fallback else ""


def render_blocks_to_html(content_json):
    """Render an Editor.js document (JSON str or dict) to sanitized HTML."""
    doc = _loads(content_json)
    blocks = doc.get("blocks", []) if isinstance(doc, dict) else []
    used_anchors = set()
    html_parts = [_render_block(b, used_anchors) for b in blocks]
    return "\n".join(p for p in html_parts if p)


# --- Reading time ----------------------------------------------------------
def _block_text(block):
    data = block.get("data", {}) or {}
    parts = []
    for key in ("text", "caption", "code"):
        if data.get(key):
            parts.append(str(data[key]))
    for it in data.get("items", []) or []:
        if isinstance(it, dict):
            parts.append(str(it.get("content", "") or it.get("text", "")))
        else:
            parts.append(str(it))
    for row in data.get("content", []) or []:
        if isinstance(row, list):
            parts.extend(str(c) for c in row)
    return " ".join(parts)


def estimate_reading_time(content_json, wpm=200):
    """Return (minutes, word_count) from a block document."""
    doc = _loads(content_json)
    blocks = doc.get("blocks", []) if isinstance(doc, dict) else []
    text = " ".join(_block_text(b) for b in blocks)
    text = re.sub(r"<[^>]+>", " ", text)
    words = len(re.findall(r"\w+", text))
    minutes = max(1, math.ceil(words / wpm)) if words else 0
    return minutes, words


# --- Legacy CKEditor HTML -> blocks (best effort) --------------------------
_BLOCK_INLINE_KEEP = {"b", "strong", "i", "em", "u", "s", "strike", "del",
                      "mark", "a", "code", "sup", "sub", "span", "br"}


class _HTMLToBlocks(HTMLParser):
    """Walk legacy HTML and emit Editor.js blocks. Intentionally forgiving."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.stack = []          # container context: p/h/li/quote/code
        self.buf = []            # inline HTML buffer for current text container
        self.list_type = None    # 'ordered' | 'unordered'
        self.list_items = None   # collecting list items
        self._skip_depth = 0

    # -- helpers
    def _flush_text(self, block_type, extra=None):
        html = "".join(self.buf).strip()
        self.buf = []
        if not html and block_type != "delimiter":
            return
        if block_type == "header":
            self.blocks.append({"type": "header",
                                "data": {"text": html, "level": extra or 2}})
        elif block_type == "quote":
            self.blocks.append({"type": "quote",
                                "data": {"text": html, "caption": "", "alignment": "left"}})
        elif block_type == "paragraph":
            self.blocks.append({"type": "paragraph", "data": {"text": html}})

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "img":
            src = a.get("src")
            if src:
                self.blocks.append({"type": "image",
                                    "data": {"file": {"url": src},
                                             "caption": a.get("alt", ""),
                                             "withBorder": False,
                                             "stretched": False,
                                             "withBackground": False}})
            return
        if tag == "hr":
            self.blocks.append({"type": "delimiter", "data": {}})
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.stack.append(("header", int(tag[1])))
            self.buf = []
        elif tag == "p":
            self.stack.append(("paragraph", None))
            self.buf = []
        elif tag == "blockquote":
            self.stack.append(("quote", None))
            self.buf = []
        elif tag in ("pre",):
            self.stack.append(("code", None))
            self.buf = []
        elif tag in ("ul", "ol"):
            self.list_type = "ordered" if tag == "ol" else "unordered"
            self.list_items = []
        elif tag == "li":
            self.stack.append(("li", None))
            self.buf = []
        elif tag in _BLOCK_INLINE_KEEP:
            attr_str = ""
            if tag == "a" and a.get("href"):
                attr_str = f' href="{escape(a["href"], quote=True)}"'
            self.buf.append(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            if self.stack and self.stack[-1][0] == "header":
                level = self.stack.pop()[1]
                self._flush_text("header", min(level, 4) if level > 1 else 2)
        elif tag == "p":
            if self.stack and self.stack[-1][0] == "paragraph":
                self.stack.pop()
                self._flush_text("paragraph")
        elif tag == "blockquote":
            if self.stack and self.stack[-1][0] == "quote":
                self.stack.pop()
                self._flush_text("quote")
        elif tag == "pre":
            if self.stack and self.stack[-1][0] == "code":
                self.stack.pop()
                code = re.sub(r"<[^>]+>", "", "".join(self.buf))
                self.buf = []
                if code.strip():
                    self.blocks.append({"type": "code", "data": {"code": code}})
        elif tag == "li":
            if self.stack and self.stack[-1][0] == "li":
                self.stack.pop()
                content = "".join(self.buf).strip()
                self.buf = []
                if self.list_items is not None and content:
                    self.list_items.append({"content": content, "items": []})
        elif tag in ("ul", "ol"):
            if self.list_items:
                self.blocks.append({"type": "nestedList",
                                    "data": {"style": self.list_type or "unordered",
                                             "items": self.list_items}})
            self.list_items = None
            self.list_type = None
        elif tag in _BLOCK_INLINE_KEEP and tag != "br":
            self.buf.append(f"</{tag}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self.stack or self.list_items is not None:
            self.buf.append(escape(data))
        elif data.strip():
            # loose text outside any block -> paragraph
            self.blocks.append({"type": "paragraph", "data": {"text": escape(data.strip())}})


def html_to_blocks(html):
    """Best-effort conversion of stored HTML into an Editor.js document."""
    if not html or not html.strip():
        return {"blocks": []}
    parser = _HTMLToBlocks()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass
    blocks = parser.blocks
    if not blocks:
        blocks = [{"type": "paragraph", "data": {"text": clean_inline(html)}}]
    return {"blocks": blocks, "version": "2.30.0"}
