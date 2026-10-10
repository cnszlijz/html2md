# html2md

OnlineJudge（HydroOJ 系）平台由 Markdown 渲染出的题面 HTML → 原始 Markdown 反编译器。

输入平台上「题目描述 / 题解」编辑框生成的 HTML（含 KaTeX 公式），输出可重新编辑的 Markdown 源码。

## 安装

```bash
pip install -r requirements.txt   # 仅依赖 beautifulsoup4
```

## 用法

```bash
python main.py input.html              # 转换结果打印到 stdout
python main.py input.html output.md    # 写入文件
type input.html | python main.py       # Windows：stdin → stdout
```

也可作为库调用：

```python
from main import html2md
md = html2md(open("problem.html", encoding="utf-8").read())
```

## 还原规则

| HTML | Markdown |
|---|---|
| `.katex` 内 `<annotation>` 的 LaTeX | `$...$`（丢弃 KaTeX 渲染层，直接取原始公式） |
| `.katex-display` | `$$` 独立公式块 |
| `<h1>`–`<h6>` | `#`×n（保留标题内的粗体等行内格式，如 `## **题目描述**`） |
| `<pre><code class="language-x">` | ```` ```x ```` 围栏代码块 |
| `<strong>` / `<em>` / `<del>` / `<u>` / `<code>` | `**…**` / `*…*` / `~~…~~` / `<u>…</u>` / `` `…` `` |
| `<a>` / `<img>`（含 title） | `[text](url "title")` / `![alt](src "title")` |
| `<br>` | 硬换行 |
| `<ul>` / `<ol>`（含任意嵌套、loose list 项内段落） | 缩进列表；项内首个 `<p>` 并入标记行，其余块缩进为子块 |
| `<blockquote>` | `>` 前缀（支持嵌套引用、引用内列表） |
| `<table>`（`text-align` style） | 管道表格 + `:---` / `:---:` / `---:` 对齐标记 |
| `<hr>` | `---` |

其他细节：

- 空白折叠：段落内连续空白折叠为单个空格，同时保留文本节点首/尾边界空格，确保 `给定底数 $g$ 和` 这类公式两侧空格不丢。
- 解析器嵌套（`html.parser` 对未闭合 `<p>` 的处理）会自动拆分为独立段落；段落内裸 `$$…$$` 文本原样保留。

## 已知不可还原项

这些信息在 HTML 渲染时已丢失，属预期行为：

- 转义符：`\*`、`\_` 等 → 输出裸 `*`、`_`
- 引用内的软换行 → 折叠为空格（无 `<br>` 即不可区分）
- 硬换行前的尾随空格 → 输出为单个 `\n`

## 文件说明

| 文件 | 说明 |
|---|---|
| `main.py` | 转换器本体 |
| `sample.html` / `complex.html` | 实际 OJ 题面样例（三元组统计 / FFT 求阶，含 KaTeX 公式） |
| `test.md` | 覆盖全部语法的测试源文件，粘贴到 OJ 生成对应 HTML 后可作回归测试 |

## 验证方式

```bash
python main.py test.html      # 与 test.md 逐项比对
python main.py sample.html
python main.py complex.html
```

`test.md` 全部语法（六级标题、行内格式、链接/图片、行内与独立公式、三种代码块、嵌套列表、引用、对齐表格、分割线、硬换行、空白折叠）经 `test.html` 往返验证一致。
