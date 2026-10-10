#!/usr/bin/env python3
"""OnlineJudge(markdown 渲染)HTML -> 原始 markdown 反编译器.

用法: python main.py input.html [output.md]
      不给参数时从 stdin 读、向 stdout 写。
"""
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
            out.append("[%s](%s)" % (render_inline(c), c.get("href", "")))
        elif c.name == "img":
            out.append("![%s](%s)" % (c.get("alt", ""), c.get("src", "")))
        elif c.name == "br":
            out.append("\n")
        elif c.name in BLOCK_TAGS:
            out.append("\n\n%s\n\n" % render_block(c))
        else:  # span 等纯容器
            out.append(render_inline(c))
    return "".join(out)


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
        sub = []
        inline_parts = []
        for c in li.children:
            if isinstance(c, Tag) and c.name in BLOCK_TAGS:
                sub.append(render_block(c, indent + " " * len(marker)))
            else:
                inline_parts.append(c)
        wrapper = li  # 借用 li 节点渲染行内部分
        for c in list(li.children):
            if isinstance(c, Tag) and c.name in BLOCK_TAGS:
                c.extract()
        text = render_inline(wrapper).strip()
        lines.append(indent + marker + text)
        lines.extend(sub)
    return "\n".join(lines)


def render_table(node: Tag) -> str:
    rows = []
    for tr in node.find_all("tr"):
        cells = [clean(render_inline(c)).strip() or " "
                 for c in tr.find_all(("th", "td"), recursive=False)]
        rows.append("| " + " | ".join(cells) + " |")
    if len(rows) >= 2:
        rows.insert(1, "|" + "---|" * (rows[0].count("|") - 1))
    return "\n".join(rows)


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
    return ("\n\n".join(parts)).replace("\n", "\n" + indent)


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
