"""Builds the architecture diagram in two formats from one layout:

  docs/images/architecture.svg   shown in the README (logos embedded, so GitHub renders them)
  docs/architecture.drawio       the same diagram, editable in draw.io / app.diagrams.net

Brand logos come from Simple Icons (CC0), downloaded once into docs/images/icons/.

Run:  uv run python scripts/buildArchitectureDiagram.py
Change the diagram by editing the NODES / CONTAINERS / EDGES lists below and re-running.
"""

from __future__ import annotations

import base64
import html
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from digest.envSettings import REPO_ROOT, env, envUrl  # noqa: E402

ICON_DIR = REPO_ROOT / "docs" / "images" / "icons"
SVG_OUT = REPO_ROOT / "docs" / "images" / "architecture.svg"
DRAWIO_OUT = REPO_ROOT / "docs" / "architecture.drawio"

WIDTH, HEIGHT = 1640, 940
FONT = "Segoe UI, -apple-system, Helvetica, Arial, sans-serif"
TEXT, MUTED, BORDER = "#1F2328", "#59636E", "#D1D9E0"

BRAND_SLUGS = [
    "openai",
    "deepmind",
    "anthropic",
    "mistralai",
    "huggingface",
    "arxiv",
    "ycombinator",
    "reddit",
    "youtube",
    "gmail",
    "x",
    "python",
    "githubactions",
    "modelcontextprotocol",
    "langgraph",
    "googlegemini",
    "qwen",
    "github",
    "astro",
    "cloudflareworkers",
]
# Logos without a colour in the Simple Icons data file.
COLOUR_OVERRIDES = {"openai": "000000"}
# Logos removed from Simple Icons v16; fetched from SIMPLE_ICONS_LEGACY_ICON_URL instead.
LEGACY_SLUGS = {"openai"}


# --------------------------------------------------------------------------- icons


@dataclass
class Icon:
    viewBox: str
    body: str  # inner SVG elements

    def standalone(self) -> str:
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{self.viewBox}">{self.body}</svg>'

    def nested(self, x: float, y: float, size: float) -> str:
        return (
            f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="{self.viewBox}">'
            f"{self.body}</svg>"
        )


def downloadBrandIcons() -> None:
    """Fetch logos + brand colours once; later runs work offline from docs/images/icons/."""
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    coloursFile = ICON_DIR / "colours.json"
    missing = [s for s in BRAND_SLUGS if not (ICON_DIR / f"{s}.svg").exists()]
    if not missing and coloursFile.exists():
        return
    with httpx.Client(timeout=60, headers={"User-Agent": env("USER_AGENT")}) as client:
        for slug in missing:
            urlName = (
                "SIMPLE_ICONS_LEGACY_ICON_URL" if slug in LEGACY_SLUGS else "SIMPLE_ICONS_ICON_URL"
            )
            resp = client.get(envUrl(urlName, slug=slug))
            resp.raise_for_status()
            (ICON_DIR / f"{slug}.svg").write_text(resp.text, encoding="utf-8")
        data = client.get(env("SIMPLE_ICONS_DATA_URL")).json()
    colours = {e["slug"]: e["hex"] for e in data if e.get("slug") in BRAND_SLUGS}
    colours.update(COLOUR_OVERRIDES)
    coloursFile.write_text(json.dumps(colours, indent=2, sort_keys=True), encoding="utf-8")


def loadIcons() -> dict[str, Icon]:
    colours = json.loads((ICON_DIR / "colours.json").read_text(encoding="utf-8"))
    icons: dict[str, Icon] = {}
    for slug in BRAND_SLUGS:
        raw = (ICON_DIR / f"{slug}.svg").read_text(encoding="utf-8")
        path = re.search(r'<path d="([^"]+)"', raw).group(1)
        icons[slug] = Icon("0 0 24 24", f'<path fill="#{colours.get(slug, "000000")}" d="{path}"/>')

    # Hand-drawn glyphs for things without a brand logo.
    icons["microsoft"] = Icon(
        "0 0 24 24",
        '<rect x="1" y="1" width="10.5" height="10.5" fill="#F25022"/>'
        '<rect x="12.5" y="1" width="10.5" height="10.5" fill="#7FBA00"/>'
        '<rect x="1" y="12.5" width="10.5" height="10.5" fill="#00A4EF"/>'
        '<rect x="12.5" y="12.5" width="10.5" height="10.5" fill="#FFB900"/>',
    )
    icons["groq"] = Icon(
        "0 0 48 24",
        '<rect width="48" height="24" rx="6" fill="#F55036"/>'
        f'<text x="24" y="16.5" font-family="{FONT}" font-size="13" font-weight="700" '
        'fill="#fff" text-anchor="middle">groq</text>',
    )
    icons["globe"] = Icon(
        "0 0 24 24",
        '<circle cx="12" cy="12" r="10" fill="none" stroke="#0969DA" stroke-width="2"/>'
        '<ellipse cx="12" cy="12" rx="4.2" ry="10" fill="none" stroke="#0969DA" stroke-width="1.6"/>'
        '<path d="M2.5 8.5h19M2.5 15.5h19" stroke="#0969DA" stroke-width="1.6"/>',
    )
    icons["funnel"] = Icon(
        "0 0 24 24",
        '<path fill="#8250DF" d="M2 3h20l-7.5 9v7.5L9.5 22v-10z"/>',
    )
    icons["readers"] = Icon(
        "0 0 24 24",
        '<circle cx="8" cy="7" r="4" fill="#0969DA"/><path fill="#0969DA" d="M0 21c0-4.4 3.6-8 8-8s8 3.6 8 8z"/>'
        '<circle cx="17" cy="8" r="3.2" fill="#54AEFF"/><path fill="#54AEFF" d="M13 21c.3-3.7 1.6-6.4 4-7 3.3 0 6 2.9 7 7z"/>',
    )
    icons["database"] = Icon(
        "0 0 24 24",
        '<ellipse cx="12" cy="5" rx="9" ry="3.2" fill="#F38020"/>'
        '<path fill="#F38020" d="M3 7.5c0 1.8 4 3.2 9 3.2s9-1.4 9-3.2V12c0 1.8-4 3.2-9 3.2S3 13.8 3 12z'
        'M3 14.5c0 1.8 4 3.2 9 3.2s9-1.4 9-3.2V19c0 1.8-4 3.2-9 3.2S3 20.8 3 19z"/>',
    )
    return icons


# --------------------------------------------------------------------------- layout


@dataclass
class Container:
    id: str
    x: float
    y: float
    w: float
    h: float
    title: str
    subtitle: str = ""
    icon: str | None = None
    fill: str = "#F6F8FA"
    stroke: str = BORDER
    dashed: bool = False


@dataclass
class Node:
    id: str
    x: float
    y: float
    w: float
    h: float
    title: str
    subtitle: str = ""
    icons: list[str] = field(default_factory=list)
    status: str | None = None  # "built" | "planned"
    llm: tuple[list[str], str] | None = None  # (badge icons, label) for agent cards
    accent: str | None = None  # left colour bar


@dataclass
class Edge:
    points: list[tuple[float, float]]
    source: str
    target: str
    label: str = ""
    dashed: bool = False
    both: bool = False
    colour: str = "#59636E"
    labelAt: int = 0  # which segment carries the label
    labelPos: tuple[float, float] | None = None  # explicit label centre, if the segment is crowded


CONTAINERS = [
    Container("sources", 24, 92, 272, 822, "Sources", "15 sources · every 3 h"),
    Container(
        "actions",
        320,
        92,
        766,
        822,
        "GitHub Actions",
        "every 3 h · 10:00 IST = daily edition · runs with your PC off",
        icon="githubactions",
        fill="#F1F8FF",
        stroke="#2088FF",
    ),
    Container(
        "langgraph",
        580,
        164,
        486,
        732,
        "AI agents · LangGraph",
        "7 agents · run order fixed in code",
        icon="langgraph",
        fill="#FFFFFF",
        stroke="#7FC8FF",
    ),
    Container("outputs", 1106, 92, 510, 822, "Outputs", "website · email · subscribers"),
]

SOURCES = [
    ("OpenAI", "News RSS", "openai", "built"),
    ("Google DeepMind", "Blog RSS", "deepmind", "built"),
    ("Anthropic", "News page", "anthropic", "built"),
    ("Mistral AI", "News RSS", "mistralai", "built"),
    ("Microsoft Research", "Research RSS", "microsoft", "built"),
    ("Hugging Face", "Blog · Papers · Trending", "huggingface", "built"),
    ("BAIR + arXiv", "Research + paper links", "arxiv", "built"),
    ("Hacker News", "AI stories, 50+ points", "ycombinator", "built"),
    ("Reddit", "3 AI subreddits", "reddit", "built"),
    ("YouTube", "AI Explained · Krish Naik", "youtube", "built"),
    ("Newsletters", "4 AI newsletters via Gmail", "gmail", "built"),
    ("X / Twitter", "Curated AI accounts", "x", "planned"),
]

QWEN = (["qwen", "groq"], "Qwen 3.8 27B")
GPT_OSS = (["openai", "groq"], "gpt-oss-120b")
GEMINI = (["googlegemini"], "Gemini Flash")

NODES = [
    *[
        Node(f"src{i}", 40, 146 + i * 63, 240, 54, t, s, [ic], st)
        for i, (t, s, ic, st) in enumerate(SOURCES)
    ],
    Node(
        "collectors",
        344,
        250,
        212,
        96,
        "Collectors",
        "Python · httpx · feedparser",
        ["python"],
        "built",
    ),
    Node(
        "dedupe",
        344,
        420,
        212,
        96,
        "Clean + de-duplicate",
        "link cleanup · seen-list 30 d",
        ["funnel"],
        "built",
    ),
    Node(
        "mcp",
        344,
        590,
        212,
        96,
        "MCP server",
        "5 read-only news tools",
        ["modelcontextprotocol"],
        "built",
    ),
    Node(
        "scoutLabs",
        600,
        228,
        200,
        76,
        "Scout · Labs & research",
        "",
        [],
        "planned",
        QWEN,
        "#6950EF",
    ),
    Node(
        "scoutCommunity", 600, 316, 200, 76, "Scout · Community", "", [], "planned", QWEN, "#6950EF"
    ),
    Node(
        "scoutMedia",
        600,
        404,
        200,
        76,
        "Scout · Video & newsletters",
        "",
        [],
        "planned",
        QWEN,
        "#6950EF",
    ),
    Node("scoutX", 600, 492, 200, 76, "Scout · X", "", [], "planned", QWEN, "#6950EF"),
    Node(
        "analyst",
        846,
        312,
        200,
        96,
        "Analyst",
        "score · group · 7-day memory",
        [],
        "planned",
        GPT_OSS,
        "#1F2328",
    ),
    Node(
        "writer",
        846,
        540,
        200,
        96,
        "Writer",
        "digest + op-ed · 10:00 IST",
        [],
        "planned",
        GEMINI,
        "#8E75B2",
    ),
    Node(
        "editor",
        846,
        716,
        200,
        96,
        "Editor",
        "fact-checks vs sources",
        [],
        "planned",
        GPT_OSS,
        "#1F2328",
    ),
    Node("llms", 600, 600, 200, 212, "Free LLM providers", "", [], None),
    Node(
        "data",
        1126,
        226,
        220,
        96,
        "data/ in the repo",
        "raw items · stories · digests",
        ["github"],
        "built",
    ),
    Node(
        "website",
        1126,
        430,
        220,
        110,
        "Website",
        "Latest every 3 h · digest\n+ op-ed · archive",
        ["globe", "astro"],
        "planned",
    ),
    Node(
        "email", 1126, 690, 220, 96, "Daily email", "10:00 IST · once a day", ["gmail"], "planned"
    ),
    Node("readers", 1390, 430, 206, 110, "Readers", "web + inbox", ["readers"]),
    Node(
        "worker",
        1390,
        690,
        206,
        96,
        "Subscriptions",
        "Cloudflare Worker + D1",
        ["cloudflareworkers", "database"],
        "planned",
    ),
]

EDGES = [
    Edge([(296, 298), (344, 298)], "sources", "collectors"),
    Edge([(450, 346), (450, 420)], "collectors", "dedupe"),
    Edge([(450, 516), (450, 590)], "dedupe", "mcp"),
    Edge(
        [(556, 638), (572, 638), (572, 360), (600, 360)],
        "mcp",
        "scoutCommunity",
        "tool calls",
        both=True,
        labelPos=(572, 580),
    ),
    Edge([(800, 360), (846, 360)], "scoutCommunity", "analyst"),
    Edge([(946, 408), (946, 540)], "analyst", "writer", "10:00 IST only", dashed=True),
    Edge([(946, 636), (946, 716)], "writer", "editor"),
    Edge(
        [(846, 780), (826, 780), (826, 600), (846, 600)],
        "editor",
        "writer",
        "revise",
        dashed=True,
        labelAt=1,
    ),
    Edge(
        [(996, 312), (996, 258), (1126, 258)], "analyst", "data", "stories · every 3 h", labelAt=1
    ),
    Edge(
        [(1046, 744), (1094, 744), (1094, 298), (1126, 298)],
        "editor",
        "data",
        "digest + op-ed",
        labelPos=(1094, 376),
    ),
    Edge([(1236, 322), (1236, 430)], "data", "website", "build & deploy"),
    Edge([(1046, 780), (1126, 780)], "editor", "email", "10:00 IST", dashed=True),
    Edge([(1346, 478), (1390, 478)], "website", "readers"),
    Edge(
        [(1346, 712), (1366, 712), (1366, 516), (1390, 516)], "email", "readers", "inbox", labelAt=1
    ),
    Edge([(1493, 540), (1493, 690)], "readers", "worker", "subscribe"),
    Edge([(1390, 760), (1346, 760)], "worker", "email", "list"),
]

# --------------------------------------------------------------------------- SVG


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def svgText(x, y, text, size=12, weight=400, colour=TEXT, anchor="start") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
        f'fill="{colour}" text-anchor="{anchor}">{esc(text)}</text>'
    )


STATUS_COLOURS = {"built": "#1A7F37", "planned": "#AFB8C1"}


def statusDot(cx, cy, status) -> str:
    return f'<circle cx="{cx}" cy="{cy}" r="5" fill="{STATUS_COLOURS[status]}"/>'


def renderContainer(c: Container, icons: dict[str, Icon]) -> str:
    dash = ' stroke-dasharray="6 4"' if c.dashed else ""
    out = [
        f'<rect x="{c.x}" y="{c.y}" width="{c.w}" height="{c.h}" rx="14" fill="{c.fill}" '
        f'stroke="{c.stroke}" stroke-width="1.5"{dash}/>'
    ]
    tx = c.x + 16
    if c.icon:
        out.append(icons[c.icon].nested(c.x + 14, c.y + 12, 26))
        tx = c.x + 48
    out.append(svgText(tx, c.y + 25, c.title, 15, 700))
    if c.subtitle:
        out.append(svgText(tx, c.y + 42, c.subtitle, 11, 400, MUTED))
    return "".join(out)


def renderNode(n: Node, icons: dict[str, Icon]) -> str:
    out = [
        f'<rect x="{n.x}" y="{n.y}" width="{n.w}" height="{n.h}" rx="10" fill="#FFFFFF" '
        f'stroke="{BORDER}" stroke-width="1.2" filter="url(#shadow)"/>'
    ]
    if n.accent:
        out.append(
            f'<path d="M{n.x + 10} {n.y}h-0a10 10 0 0 0 -10 10v{n.h - 20}a10 10 0 0 0 10 10z" '
            f'fill="{n.accent}"/>'
        )
    if n.id == "llms":
        out.append(svgText(n.x + 14, n.y + 24, n.title, 12.5, 700))
        rows = [
            (["groq"], "Groq", "gpt-oss-120b · Qwen 3.8 27B"),
            (["googlegemini"], "Google Gemini", "Flash · Flash-Lite fallback"),
        ]
        for i, (ics, name, models) in enumerate(rows):
            ry = n.y + 44 + i * 58
            size = 22
            if ics[0] == "groq":
                out.append(icons["groq"].nested(n.x + 12, ry - 5, 40))
            else:
                out.append(icons[ics[0]].nested(n.x + 20, ry, size))
            out.append(svgText(n.x + 58, ry + 10, name, 12, 600))
            out.append(svgText(n.x + 58, ry + 26, models, 10.5, 400, MUTED))
        out.append(
            f'<line x1="{n.x + 12}" y1="{n.y + 160}" x2="{n.x + n.w - 12}" '
            f'y2="{n.y + 160}" stroke="{BORDER}"/>'
        )
        out.append(svgText(n.x + 14, n.y + 180, "~45–60 calls / day", 11.5, 600))
        out.append(svgText(n.x + 14, n.y + 197, "hard cap 100 · free tiers", 10.5, 400, MUTED))
        return "".join(out)

    tx = n.x + 14 + (6 if n.accent else 0)
    if n.icons:
        for i, ic in enumerate(n.icons):
            out.append(
                icons[ic].nested(
                    n.x + 12 + i * 30, n.y + (n.h - 26) / 2 - (8 if n.h > 60 else 0), 26
                )
            )
        tx = n.x + 16 + 30 * len(n.icons)
    titleY = n.y + (22 if n.h <= 60 else 30)
    out.append(svgText(tx, titleY, n.title, 12.5 if n.h <= 60 else 13, 700))
    for i, line in enumerate(n.subtitle.split("\n") if n.subtitle else []):
        out.append(svgText(tx, titleY + 16 + i * 14, line, 10.5, 400, MUTED))
    if n.llm:
        badges, label = n.llm
        by = n.y + n.h - 28
        bx = tx
        for b in badges:
            if b == "groq":
                out.append(icons["groq"].nested(bx, by - 2, 32))
                bx += 36
            else:
                out.append(icons[b].nested(bx, by, 16))
                bx += 20
        out.append(svgText(bx + 2, by + 12.5, label, 10.5, 600, "#3D444D"))
    if n.status:
        out.append(statusDot(n.x + n.w - 13, n.y + 13, n.status))
    return "".join(out)


def renderEdge(e: Edge) -> str:
    d = "M" + " L".join(f"{x} {y}" for x, y in e.points)
    dash = ' stroke-dasharray="6 4"' if e.dashed else ""
    start = ' marker-start="url(#arrowStart)"' if e.both else ""
    return (
        f'<path d="{d}" fill="none" stroke="{e.colour}" stroke-width="1.6"{dash}{start} '
        f'marker-end="url(#arrow)"/>'
    )


def renderEdgeLabel(e: Edge) -> str:
    """Drawn after the cards so a label is never hidden behind one."""
    if not e.label:
        return ""
    if e.labelPos:
        mx, my = e.labelPos
    else:
        (x1, y1), (x2, y2) = e.points[e.labelAt], e.points[e.labelAt + 1]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    width = 10 + len(e.label) * 5.9
    return (
        f'<rect x="{mx - width / 2}" y="{my - 9}" width="{width}" height="18" rx="9" '
        f'fill="#FFFFFF" stroke="{BORDER}"/>'
        + svgText(mx, my + 4, e.label, 10, 600, "#3D444D", "middle")
    )


def buildSvg(icons: dict[str, Icon]) -> str:
    legend = [
        statusDot(1150, 42, "built"),
        svgText(1160, 46, "working today", 11, 400, MUTED),
        statusDot(1262, 42, "planned"),
        svgText(1272, 46, "next phases", 11, 400, MUTED),
        '<path d="M1400 42 L1440 42" stroke="#59636E" stroke-width="1.6" marker-end="url(#arrow)"/>',
        svgText(1446, 46, "every 3 h", 11, 400, MUTED),
        '<path d="M1510 42 L1550 42" stroke="#59636E" stroke-width="1.6" stroke-dasharray="6 4" '
        'marker-end="url(#arrow)"/>',
        svgText(1556, 46, "10:00 IST", 11, 400, MUTED),
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}">',
        "<defs>"
        '<filter id="shadow" x="-10%" y="-10%" width="120%" height="140%">'
        '<feDropShadow dx="0" dy="1.5" stdDeviation="1.5" flood-color="#1F2328" flood-opacity="0.12"/>'
        "</filter>"
        '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#59636E"/></marker>'
        '<marker id="arrowStart" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        'markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#59636E"/>'
        "</marker></defs>",
        f'<rect width="{WIDTH}" height="{HEIGHT}" rx="16" fill="#FFFFFF"/>',
        svgText(24, 46, "GenAI Daily Digest · Architecture", 22, 700),
        svgText(
            24,
            70,
            "Every 3 h: collect → scouts → analyst → Latest dashboard.   "
            "10:00 IST: writer + editor → digest, op-ed and one email.",
            12.5,
            400,
            MUTED,
        ),
        *legend,
        *(renderContainer(c, icons) for c in CONTAINERS),
        *(renderEdge(e) for e in EDGES),
        *(renderNode(n, icons) for n in NODES),
        *(renderEdgeLabel(e) for e in EDGES),
        "</svg>",
    ]
    return "\n".join(parts)


# --------------------------------------------------------------------------- draw.io


def drawioImage(icon: Icon) -> str:
    # draw.io's convention: data:image/svg+xml,<base64> (no ";base64").
    return "data:image/svg+xml," + base64.b64encode(icon.standalone().encode()).decode()


def buildDrawio(icons: dict[str, Icon]) -> str:
    cells: list[str] = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    counter = iter(range(1000, 100000))

    def vertex(cid, x, y, w, h, value, style):
        cells.append(
            f'<mxCell id="{cid}" value="{esc(value)}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
        )

    def image(x, y, w, h, icon: Icon):
        style = f"shape=image;aspect=fixed;imageAspect=1;image={drawioImage(icon)};"
        vertex(f"img{next(counter)}", x, y, w, h, "", style)

    for c in CONTAINERS:
        label = f"<b>{esc(c.title)}</b><br><font color='{MUTED}' style='font-size:11px'>{esc(c.subtitle)}</font>"
        style = (
            f"rounded=1;arcSize=3;whiteSpace=wrap;html=1;fillColor={c.fill};strokeColor={c.stroke};"
            f"strokeWidth=1.5;verticalAlign=top;align=left;spacingLeft={48 if c.icon else 16};"
            f"spacingTop=6;fontSize=15;fontColor={TEXT};container=0;"
        )
        vertex(c.id, c.x, c.y, c.w, c.h, label, style)
        if c.icon:
            image(c.x + 14, c.y + 12, 26, 26, icons[c.icon])

    for n in NODES:
        lines = [f"<b>{esc(n.title)}</b>"]
        if n.subtitle:
            lines.append(
                f"<font color='{MUTED}' style='font-size:10px'>{esc(n.subtitle).replace(chr(10), '<br>')}</font>"
            )
        if n.llm:
            lines.append(f"<font style='font-size:10px'><b>LLM:</b> {esc(n.llm[1])}</font>")
        if n.status:
            lines.append(
                f"<font color='{'#1A7F37' if n.status == 'built' else MUTED}' style='font-size:9px'>● {n.status}</font>"
            )
        if n.id == "llms":
            lines = [
                "<b>Free LLM providers</b>",
                "Groq: gpt-oss-120b · Qwen 3.8 27B",
                "Google Gemini: Flash · Flash-Lite",
                "<b>~45–60 calls/day</b> · cap 100",
            ]
        indent = 16 + 30 * len(n.icons) + (10 if n.accent else 0)
        style = (
            "rounded=1;arcSize=10;whiteSpace=wrap;html=1;fillColor=#FFFFFF;"
            f"strokeColor={n.accent or BORDER};strokeWidth={2 if n.accent else 1.2};shadow=1;"
            f"align=left;verticalAlign=middle;spacingLeft={indent};fontSize=12;fontColor={TEXT};"
        )
        vertex(n.id, n.x, n.y, n.w, n.h, "<br>".join(lines), style)
        for i, ic in enumerate(n.icons):
            image(n.x + 12 + i * 30, n.y + (n.h - 26) / 2, 26, 26, icons[ic])
        if n.llm:
            bx = n.x + n.w - 26 * len(n.llm[0]) - 8
            for b in n.llm[0]:
                w = 32 if b == "groq" else 18
                image(bx, n.y + n.h - 24, w, 16 if b == "groq" else 18, icons[b])
                bx += w + 4

    geometry = {c.id: (c.x, c.y, c.w, c.h) for c in CONTAINERS}
    geometry |= {n.id: (n.x, n.y, n.w, n.h) for n in NODES}
    for e in EDGES:
        sx, sy, sw, sh = geometry[e.source]
        tx, ty, tw, th = geometry[e.target]
        (px, py), (qx, qy) = e.points[0], e.points[-1]
        style = (
            "edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;endFill=1;"
            f"strokeColor={e.colour};strokeWidth=1.6;fontSize=10;labelBackgroundColor=#FFFFFF;"
            f"exitX={(px - sx) / sw:.3f};exitY={(py - sy) / sh:.3f};exitDx=0;exitDy=0;"
            f"entryX={(qx - tx) / tw:.3f};entryY={(qy - ty) / th:.3f};entryDx=0;entryDy=0;"
            + ("dashed=1;" if e.dashed else "")
            + ("startArrow=block;startFill=1;" if e.both else "")
        )
        waypoints = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in e.points[1:-1])
        cells.append(
            f'<mxCell id="edge{next(counter)}" value="{esc(e.label)}" style="{style}" edge="1" '
            f'parent="1" source="{e.source}" target="{e.target}">'
            f'<mxGeometry relative="1" as="geometry"><Array as="points">{waypoints}</Array>'
            "</mxGeometry></mxCell>"
        )

    return (
        '<mxfile host="genai-digest" type="device">'
        '<diagram id="architecture" name="Architecture">'
        f'<mxGraphModel dx="{WIDTH}" dy="{HEIGHT}" grid="1" gridSize="10" guides="1" tooltips="1" '
        f'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{WIDTH}" '
        f'pageHeight="{HEIGHT}" math="0" shadow="0"><root>{"".join(cells)}</root>'
        "</mxGraphModel></diagram></mxfile>\n"
    )


def main() -> None:
    downloadBrandIcons()
    icons = loadIcons()
    SVG_OUT.parent.mkdir(parents=True, exist_ok=True)
    SVG_OUT.write_text(buildSvg(icons), encoding="utf-8")
    DRAWIO_OUT.write_text(buildDrawio(icons), encoding="utf-8")
    print(f"Wrote {SVG_OUT.relative_to(REPO_ROOT)} and {DRAWIO_OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
