#!/usr/bin/env python3
"""Check the built site against its preserved source, without using the builder.

Uses the Python standard library only. Checks local files and HTML fragments,
source text/placements, duplicate IDs, image alternatives, and Arabic RTL roots.
External URLs, scientific correctness, rendering, and media playback are not
validated. The sole written output is the requested JSON report.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urljoin, urlsplit


VOID_TAGS = set("area base br col embed hr img input link meta param source track wbr".split())
BLOCK_TAGS = set("address article aside blockquote caption dd details div dl dt figure figcaption footer h1 h2 h3 h4 h5 h6 header li main nav ol p section summary table tbody td th thead tr ul".split())
NON_CONTENT = {"script", "style", "template"}


def normalize(text: str) -> str:
    """Ignore display-only spacing/direction markers, not spelling or punctuation."""
    text = re.sub(r"[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]", "", text)
    return " ".join(text.split())


@dataclass
class Node:
    tag: str
    attrs: dict[str, str | None]
    line: int
    parent: Node | None = None
    children: list = field(default_factory=list)

    def text(self) -> str:
        if self.tag in NON_CONTENT:
            return ""
        if self.tag == "br":
            return "\n"
        value = "".join(c.text() if isinstance(c, Node) else c for c in self.children)
        return f" {value} " if self.tag in BLOCK_TAGS else value

    def is_content(self) -> bool:
        node = self
        while node is not None:
            style = str(node.attrs.get("style", "")).lower().replace(" ", "")
            if node.tag in NON_CONTENT or "hidden" in node.attrs or "display:none" in style:
                return False
            node = node.parent
        return True

    def descendants(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.descendants()


class PageParser(HTMLParser):
    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.root = Node("document", {}, 0)
        self.stack = [self.root]
        self.nodes = []
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs), self.getpos()[0], self.stack[-1])
        self.stack[-1].children.append(node)
        self.nodes.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


class Validator:
    def __init__(self, root: Path, base_path: str):
        self.root = root.resolve()
        self.base_path = "/" + base_path.strip("/") + "/"
        if self.base_path == "//":
            self.base_path = "/"
        self.pages = {}
        self.errors = []
        self.warnings = []
        self.stats = Counter()
        self.assets = set()
        self.external_urls = set()
        self.source_registry = defaultdict(list)
        self.image_registry = defaultdict(list)
        self.coverage = {}

    def issue(self, code, file, message, node=None, warning=False, **details):
        item = {"code": code, "file": str(file), "message": message}
        if node is not None:
            item.update({"line": node.line, "tag": node.tag})
        item.update(details)
        (self.warnings if warning else self.errors).append(item)

    def parse_pages(self):
        for path in sorted(self.root.rglob("*.html")):
            if any(part in {".git", "node_modules"} for part in path.relative_to(self.root).parts):
                continue
            relative = path.relative_to(self.root).as_posix()
            try:
                page = PageParser(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError) as exc:
                self.issue("html_read_error", relative, str(exc))
                continue
            page.ids = defaultdict(list)
            for node in page.nodes:
                if "id" in node.attrs:
                    value = node.attrs["id"]
                    if not value or re.search(r"\s", value):
                        self.issue("invalid_id", relative, "ID is empty or contains whitespace.", node, id=value)
                    page.ids[value].append(node)
                if node.attrs.get("data-source"):
                    self.source_registry[node.attrs["data-source"]].append((relative, node))
                if node.attrs.get("data-image"):
                    self.image_registry[node.attrs["data-image"]].append((relative, node))
            self.pages[relative] = page
            roots = [n for n in page.nodes if n.tag == "html"]
            if len(roots) != 1:
                self.issue("html_root_count", relative, "Exactly one html element is required.", count=len(roots))
            elif not str(roots[0].attrs.get("lang", "")).lower().startswith("ar") or roots[0].attrs.get("dir") != "rtl":
                self.issue("arabic_rtl_root", relative, "The html root must declare Arabic language and RTL direction.", roots[0], lang=roots[0].attrs.get("lang"), direction=roots[0].attrs.get("dir"))
            for value, nodes in page.ids.items():
                if len(nodes) > 1:
                    self.issue("duplicate_id", relative, "ID occurs more than once in this document.", nodes[0], id=value, lines=[n.line for n in nodes])
            headings = [n for n in page.nodes if n.tag == "h1" and n.is_content()]
            if len(headings) != 1:
                self.issue("h1_count", relative, "Exactly one readable h1 is expected.", count=len(headings))
            titles = [n for n in page.nodes if n.tag == "title"]
            if len(titles) != 1 or not normalize(titles[0].text()):
                self.issue("page_title", relative, "A nonempty page title is required.")
            for node in page.nodes:
                if node.tag == "img":
                    self.stats["images_checked"] += 1
                    decorative = node.attrs.get("aria-hidden") == "true" or node.attrs.get("role") in {"presentation", "none"}
                    if "alt" not in node.attrs or (not normalize(node.attrs.get("alt") or "") and not decorative):
                        self.issue("image_alt", relative, "A content image needs nonempty alternative text.", node, src=node.attrs.get("src"))
                if node.attrs.get("aria-controls"):
                    for target in node.attrs["aria-controls"].split():
                        if target not in page.ids:
                            self.issue("aria_controls_target", relative, "aria-controls has no target ID.", node, target=target)
                if node.tag == "label" and node.attrs.get("for") and node.attrs["for"] not in page.ids:
                    self.issue("label_target", relative, "Label has no matching control ID.", node, target=node.attrs["for"])

    def local_target(self, file: str, value: str):
        raw = value.strip()
        parts = urlsplit(raw)
        if parts.scheme or parts.netloc:
            self.external_urls.add(raw)
            self.stats["external_urls_skipped"] += 1
            return None
        origin = "https://local.invalid"
        resolved = urlsplit(urljoin(origin + self.base_path + file, raw))
        pathname = unquote(resolved.path)
        if not pathname.startswith(self.base_path):
            return ("outside_site", pathname, unquote(resolved.fragment))
        target = (self.root / pathname[len(self.base_path):]).resolve()
        if not target.is_relative_to(self.root):
            return ("outside_site", str(target), unquote(resolved.fragment))
        if target.is_dir():
            target = target / "index.html"
        return ("local", target, unquote(resolved.fragment))

    def check_url(self, file, value, node=None, attribute="href", resource=False):
        if value is None or (resource and not value.strip()):
            self.issue("empty_resource_url", file, "Resource URL is empty.", node, attribute=attribute)
            return
        try:
            result = self.local_target(file, value)
        except (ValueError, OSError) as exc:
            self.issue("invalid_url", file, str(exc), node, attribute=attribute, value=value)
            return
        if result is None:
            return
        self.stats["local_urls_checked"] += 1
        kind, target, fragment = result
        if kind == "outside_site":
            self.issue("outside_project_url", file, "Local URL leaves the published project base path.", node, attribute=attribute, value=value, target=str(target))
            return
        relative = target.relative_to(self.root).as_posix()
        if not target.is_file():
            self.issue("missing_local_file", file, "Local URL has no corresponding file.", node, attribute=attribute, value=value, target=relative)
            return
        if target.stat().st_size == 0:
            self.issue("empty_local_file", file, "Linked local file is empty.", node, attribute=attribute, value=value, target=relative)
        if target.suffix.lower() != ".html":
            self.assets.add(relative)
        if fragment and target.suffix.lower() == ".html":
            self.stats["html_fragments_checked"] += 1
            target_page = self.pages.get(relative)
            if target_page is None:
                self.issue("unparsed_html_target", file, "HTML target could not be parsed.", node, target=relative)
            elif fragment not in target_page.ids:
                self.issue("missing_fragment", file, "HTML fragment has no target ID.", node, attribute=attribute, value=value, target=relative, fragment=fragment)

    def css_urls(self, file, text, node=None):
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        for match in re.finditer(r"url\(\s*(['\"]?)(.*?)\1\s*\)", text, flags=re.I | re.S):
            self.check_url(file, match.group(2).strip(), node, "css-url", resource=True)
        for match in re.finditer(r"@import\s+(['\"])(.*?)\1", text, flags=re.I):
            self.check_url(file, match.group(2), node, "css-import", resource=True)

    def check_links(self):
        for relative, page in self.pages.items():
            for node in page.nodes:
                for attr in ("href", "src", "poster", "data-search-index", "xlink:href"):
                    if attr in node.attrs:
                        self.check_url(relative, node.attrs[attr], node, attr, resource=attr in {"src", "poster", "data-search-index"})
                if node.attrs.get("srcset"):
                    raw = node.attrs["srcset"]
                    if not raw.lstrip().startswith("data:"):
                        for entry in raw.split(","):
                            candidate = entry.strip().split()
                            if candidate:
                                self.check_url(relative, candidate[0], node, "srcset", resource=True)
                if node.attrs.get("style"):
                    self.css_urls(relative, node.attrs["style"], node)
                if node.tag == "style":
                    self.css_urls(relative, "".join(c for c in node.children if isinstance(c, str)), node)
        for css in sorted(self.root.rglob("*.css")):
            if ".git" not in css.relative_to(self.root).parts:
                self.css_urls(css.relative_to(self.root).as_posix(), css.read_text(encoding="utf-8"))
        search_index = self.root / "data/search-index.json"
        if search_index.is_file():
            try:
                search = json.loads(search_index.read_text(encoding="utf-8"))
                items = search if isinstance(search, list) else search.get("items", [])
                for item in items:
                    if isinstance(item, dict) and (item.get("url") or item.get("href")):
                        # Search entries are resolved against the fetched index URL.
                        self.check_url("data/search-index.json", item.get("url") or item.get("href"), attribute="search-index-url")
                        self.stats["search_targets_checked"] += 1
            except (ValueError, AttributeError) as exc:
                self.issue("search_index_parse", "data/search-index.json", str(exc))

    def check_source(self):
        source_file = self.root / "content/source.json"
        try:
            data = json.loads(source_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self.issue("source_manifest_read", "content/source.json", str(exc))
            return
        entries = [(p["path"], b) for p in data["pages"] for b in p["blocks"]]
        categories = {
            "paragraphs": {b["source"] for _, b in entries if b["type"] in {"paragraph", "heading"}},
            "tables": {b["source"] for _, b in entries if b["type"] == "table"},
            "images": {b["source_image"] for _, b in entries if b["type"] == "image"},
            "references": {b["reference_id"] for _, b in entries if b.get("reference_id")},
        }
        declared = data.get("summary", {}).get("coverage", {})
        for kind, field_name in (("paragraphs", "nonempty_paragraph_ids"), ("tables", "table_ids"), ("images", "image_ids")):
            expected = set(declared.get(field_name, []))
            if expected != categories[kind]:
                self.issue("source_manifest_coverage", "content/source.json", "Declared coverage differs from the source blocks.", category=kind, declared_only=sorted(expected-categories[kind]), blocks_only=sorted(categories[kind]-expected))
        covered = defaultdict(set)
        for relative, block in entries:
            source_id = block.get("source")
            if block["type"] == "image":
                registry = self.image_registry[block["source_image"]]
                matches = [(f, n) for f, n in registry if f == relative and n.attrs.get("id") == block.get("id")]
                category, coverage_id = "images", block["source_image"]
            else:
                registry = self.source_registry[source_id]
                matches = [(f, n) for f, n in registry if f == relative and n.attrs.get("id") == block.get("id")]
                category, coverage_id = ("tables" if block["type"] == "table" else "paragraphs"), source_id
            if len(matches) != 1:
                self.issue("source_placement", relative, "Expected exactly one element with the source identifier and anchor.", source=coverage_id, anchor=block.get("id"), occurrences=len(matches))
                continue
            node = matches[0][1]
            if not node.is_content():
                self.issue("hidden_source_content", relative, "Source content is in an explicitly hidden or noncontent element.", node, source=coverage_id)
                continue
            covered[category].add(coverage_id)
            if block["type"] in {"paragraph", "heading"}:
                expected_text = normalize(block.get("text", ""))
                if expected_text and expected_text not in normalize(node.text()):
                    self.issue("source_text_mismatch", relative, "Visible text does not preserve the source text.", node, source=source_id, expected=expected_text, actual=normalize(node.text()))
                if len(registry) != 1:
                    self.issue("repeated_source_paragraph", relative, "Source paragraph has multiple data-source placements.", node, source=source_id, placements=[f for f, _ in registry])
                if block.get("reference_id"):
                    covered["references"].add(block["reference_id"])
            elif block["type"] == "table":
                content = normalize(" ".join(n.text() for f, n in registry if f == relative and n.is_content()))
                missing_cells = []
                for row_index, row in enumerate(block.get("rows", []), 1):
                    for cell_index, cell in enumerate(row, 1):
                        text = normalize(cell)
                        if text and text not in content:
                            missing_cells.append({"row": row_index, "column": cell_index, "text": text})
                if missing_cells:
                    self.issue("source_table_content", relative, "Original table cells are absent from its declared source placements.", node, source=source_id, missing_cells=missing_cells)
            elif block["type"] == "image":
                images = [n for n in node.descendants() if n.tag == "img"]
                expected_file = (self.root / block["src"]).resolve()
                actual_files = []
                for img in images:
                    resolved = self.local_target(relative, img.attrs.get("src") or "")
                    if resolved and resolved[0] == "local":
                        actual_files.append(resolved[1])
                if expected_file not in actual_files:
                    self.issue("source_image_file", relative, "Source image placement does not load its declared image file.", node, source=coverage_id, expected_file=block["src"])
                if expected_file.is_file() and block.get("sha256"):
                    if hashlib.sha256(expected_file.read_bytes()).hexdigest() != block["sha256"]:
                        self.issue("source_image_hash", relative, "Preserved source image differs from its recorded checksum.", node, source=coverage_id, expected_file=block["src"])
        for category, expected in categories.items():
            missing = expected - covered[category]
            self.coverage[category] = {"expected": len(expected), "covered": len(covered[category]), "missing": sorted(missing)}
            if missing:
                self.issue("source_coverage_missing", "content/source.json", "Source category is incompletely represented in HTML.", category=category, missing=sorted(missing))
        summary = data.get("summary", {})
        for kind, key in (("paragraphs", "paragraphs_nonempty_preserved"), ("tables", "tables_preserved"), ("images", "image_placements_preserved"), ("references", "references_preserved")):
            if key in summary and summary[key] != len(categories[kind]):
                self.issue("source_summary_count", "content/source.json", "Source summary count differs from independently counted blocks.", category=kind, declared=summary[key], counted=len(categories[kind]))

    def run(self):
        self.parse_pages()
        self.check_links()
        self.check_source()
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "validator": "scripts/validate_site.py",
            "status": "passed" if not self.errors else "failed",
            "scope": {
                "local_files_and_fragments": True,
                "html_ids_and_image_alternatives": True,
                "arabic_rtl_root": True,
                "source_text_and_placement_coverage": True,
                "external_network_requests": False,
                "scientific_reference_correctness": "not assessed",
                "visual_rendering_and_media_playback": "not assessed",
            },
            "summary": {
                "html_pages": len(self.pages),
                "error_count": len(self.errors),
                "warning_count": len(self.warnings),
                "unique_local_assets": len(self.assets),
                "unique_external_urls_skipped": len(self.external_urls),
                **dict(self.stats),
            },
            "source_coverage": self.coverage,
            "asset_groups": {group: sorted(p for p in self.assets if p.startswith(group + "/")) for group in ("assets", "videos", "downloads")},
            "errors": self.errors,
            "warnings": self.warnings,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report", type=Path, default=Path("docs/site-validation.json"))
    parser.add_argument("--base-path", help="Published project prefix; defaults to /<root directory name>/")
    args = parser.parse_args()
    root = args.root.resolve()
    report = Validator(root, args.base_path if args.base_path is not None else root.name).run()
    output = args.report if args.report.is_absolute() else root / args.report
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(output), "summary": report["summary"], "source_coverage": report["source_coverage"]}, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
