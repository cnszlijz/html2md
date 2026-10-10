#!/usr/bin/env python3
"""OnlineJudge(markdown 渲染)HTML -> 原始 markdown 反编译器.

用法: python main.py input.html [output.md]
      不给参数时从 stdin 读、向 stdout 写。
"""
import re
import sys
from bs4 import BeautifulSoup, NavigableString, Tag

BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "ul", "ol",
              "blockquote", "table", "hr", "div", "details"}


def preprocess(soup: BeautifulSoup) -> None:
    """把 KaTeX 节点替换回原始 LaTeX: 行内 $...$，独立公式 $$...$$."""
    for disp in soup.select(".katex-display"):
        ann = disp.select_one("annotation")
        disp.replace_with(NavigableString(
            "\n$$\n%s\n$$\n" % (ann.get_text().strip() if ann else "")))
    for k in soup.select(".katex"):
        ann = k.select_one("annotation")
        k.replace_with(NavigableString(
            "$%s$" % (ann.get_text().strip() if ann else "")))


def clean(text: str) -> str:
    """折叠内部空白为单个空格，但保留节点首/尾的一个空格边界."""
    lead = " " if text[:1].isspace() else ""
    trail = " " if text[-1:].isspace() else ""
    core = " ".join(text.split())
    return lead + core + trail if core else (lead or trail)

def render_inline_str(c) -> str:
    """渲染单个行内子节点(文本或标签)."""
    if isinstance(c, NavigableString):
        return clean(str(c))
    if not isinstance(c, Tag):
        return ""
    return render_inline(c)

def render_inline(node: Tag) -> str:
    out = []
    for c in node.children:
        if isinstance(c, NavigableString):
            out.append(clean(str(c)))
        elif not isinstance(c, Tag):
            continue
        elif c.name in ("strong", "b"):
            out.append("**%s**" % render_inline(c))
        elif c.name in ("em", "i"):
            out.append("*%s*" % render_inline(c))
        elif c.name in ("del", "s"):
            out.append("~~%s~~" % render_inline(c))
        elif c.name == "u":
            out.append("<u>%s</u>" % render_inline(c))
        elif c.name == "code":
            out.append("`%s`" % c.get_text())
        elif c.name == "a":
            title = ' "%s"' % c["title"] if c.get("title") else ""
            out.append("[%s](%s%s)" % (render_inline(c), c.get("href", ""), title))
        elif c.name == "img":
            title = ' "%s"' % c["title"] if c.get("title") else ""
            out.append("![%s](%s%s)" % (c.get("alt", ""), c.get("src", ""), title))
        elif c.name == "br":
            out.append("\n")
        elif c.name in BLOCK_TAGS:
            out.append("\n\n%s\n\n" % render_block(c))
        else:  # span 等纯容器
            out.append(render_inline(c))
    return re.sub("\n[ \t]+", "\n", "".join(out))  # <br> 后不吃前导空格


def render_code(pre: Tag) -> str:
    code = pre.find("code")
    lang = ""
    if code is not None:
        cls = code.get("class") or []
        for x in cls:
            if x.startswith("language-"):
                lang = x[len("language-"):]
        text = code.get_text()
    else:
        text = pre.get_text()
    return "```%s\n%s\n```" % (lang, text.rstrip("\n"))


def render_list(node: Tag, ordered: bool, indent: str = "") -> str:
    lines = []
    for i, li in enumerate(node.find_all("li", recursive=False), 1):
        marker = "%d. " % i if ordered else "- "
        pad = indent + " " * len(marker)
        head, sub, head_open = [], [], True
        for c in li.children:
            if isinstance(c, Tag) and c.name in BLOCK_TAGS:
                # 首个 <p>(loose list) 内容并入标记行，其余块缩进为子块
                if head_open and c.name == "p":
                    head.append(render_inline(c))
                    head_open = False
                else:
                    sub.append(render_block(c, pad))
            elif str(c).strip() or isinstance(c, Tag):
                head.append(render_inline_str(c))
        text = "".join(head).strip()
        lines.append(indent + marker + text)
        lines.extend(b for b in sub if b.strip())
    return "\n".join(lines)


def render_table(node: Tag) -> str:
    rows = []
    header = None
    for tr in node.find_all("tr"):
        cells = tr.find_all(("th", "td"), recursive=False)
        rendered = [clean(render_inline(c)).strip() or " " for c in cells]
        rows.append("| " + " | ".join(rendered) + " |")
        if header is None and tr.find("th") is not None:
            header = [align_of(c) for c in cells]
    if header and len(rows) >= 2:
        rows.insert(1, "|" + "|".join(header) + "|")
    return "\n".join(rows)


def align_of(cell: Tag) -> str:
    style = (cell.get("style") or "").replace(" ", "")
    if "text-align:center" in style:
        return ":---:"
    if "text-align:right" in style:
        return "---:"
    if "text-align:left" in style:
        return ":---"
    return "---"


def render_block(node: Tag, indent: str = "") -> str:
    if node.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return "#" * int(node.name[1]) + " " + render_inline(node).strip()
    if node.name == "pre":
        return render_code(node)
    if node.name == "ul":
        return render_list(node, ordered=False, indent=indent)
    if node.name == "ol":
        return render_list(node, ordered=True, indent=indent)
    if node.name == "blockquote":
        inner = render_blocks(node)
        return "\n".join("> " + l if l else ">" for l in inner.split("\n"))
    if node.name == "table":
        return render_table(node)
    if node.name == "hr":
        return "---"
    # p / div: 行内内容，若解析器把块级元素嵌进来则拆开
    parts, buf = [], []
    for c in node.children:
        if isinstance(c, Tag) and c.name in BLOCK_TAGS:
            if buf:
                parts.append(render_inline_buf(buf))
                buf = []
            parts.append(render_block(c, indent))
        else:
            buf.append(c)
    if buf:
        parts.append(render_inline_buf(buf))
    parts = [p.strip() for p in parts if p.strip()]
    joined = "\n\n".join(parts)
    return "\n".join(indent + l if l else l for l in joined.split("\n"))


def render_inline_buf(children) -> str:
    holder = BeautifulSoup("", "html.parser")  # 临时父节点复用 render_inline
    for c in children:
        holder.append(c.extract() if isinstance(c, Tag) else str(c))
    return render_inline(holder)


def render_blocks(node: Tag) -> str:
    blocks = []
    for c in node.children:
        if isinstance(c, NavigableString):
            text = str(c).strip()
            if text:  # 独立 $$...$$ 公式等顶层文本
                blocks.append(text)
        elif isinstance(c, Tag):
            if c.name in ("script", "style"):
                continue
            blocks.append(render_block(c))
    return "\n\n".join(b for b in blocks if b.strip())


def html2md(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    preprocess(soup)
    root = soup.body if soup.body is not None else soup
    return render_blocks(root) + "\n"


def main() -> None:
    if len(sys.argv) >= 2:
        html = open(sys.argv[1], encoding="utf-8").read()
        out = html2md(html)
        if len(sys.argv) >= 3:
            open(sys.argv[2], "w", encoding="utf-8", newline="\n").write(out)
        else:
            sys.stdout.write(out)
    else:
        sys.stdout.write(html2md(sys.stdin.read()))


if __name__ == "__main__":
    main()
