#!/usr/bin/env python3
"""Generate the 7 migration-step diagrams as SVG, then render PNGs.
Style: dark (slate-950), JetBrains Mono-ish, semantic colors per component type."""
import os, subprocess, textwrap

OUT = "/home/ops/Project/bifrost-editorial/assets/diagrams"
os.makedirs(OUT, exist_ok=True)

C = {
    "app":     ("rgba(8,51,68,0.4)",  "#22d3ee"),   # frontend/cyan
    "gw":      ("rgba(251,146,60,0.25)","#fb923c"),  # gateway/orange
    "prov":    ("rgba(6,78,59,0.4)",  "#34d399"),    # backend/emerald
    "cache":   ("rgba(76,29,149,0.4)","#a78bfa"),    # db/violet
    "gov":     ("rgba(136,19,55,0.4)","#fb7185"),    # security/rose
    "ext":     ("rgba(30,41,59,0.5)", "#94a3b8"),    # slate
}

def box(x, y, w, h, label, sub, kind, dash=False):
    fill, stroke = C[kind]
    dashattr = ' stroke-dasharray="5,4"' if dash else ""
    return f'''
  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#0f172a"/>
  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.5"{dashattr}/>
  <text x="{x+w/2}" y="{y+h/2-4}" text-anchor="middle" fill="#e2e8f0" font-size="13" font-family="monospace" font-weight="bold">{label}</text>
  <text x="{x+w/2}" y="{y+h/2+13}" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="monospace">{sub}</text>'''

def arrow(x1, y1, x2, y2, color="#64748b", dash=False, label=None, ly=None):
    d = ' stroke-dasharray="6,4"' if dash else ""
    lbl = f'<text x="{(x1+x2)/2}" y="{ly or (y1+y2)/2-6}" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="monospace">{label}</text>' if label else ""
    return f'''
  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.5" marker-end="url(#ah)"{d}/>{lbl}'''

HEAD = '''<svg xmlns="http://www.w3.org/2000/svg" width="880" height="440" viewBox="0 0 880 440">
<defs>
  <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e293b" stroke-width="0.5"/>
  </pattern>
  <marker id="ah" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
    <path d="M0,0 L8,4 L0,8 Z" fill="#64748b"/>
  </marker>
</defs>
<rect width="880" height="440" fill="#020617"/>
<rect width="880" height="440" fill="url(#grid)"/>
'''
TAIL = "</svg>"

def svg(title, body):
    return HEAD + f'<text x="30" y="36" fill="#f1f5f9" font-size="17" font-family="monospace" font-weight="bold">{title}</text>' + body + TAIL

# step 1: legacy
s1 = svg("1 · Legacy: direct-to-provider", "".join([
    box(60, 150, 200, 70, "Support Copilot App", "one API key · no fallback", "app"),
    box(60, 250, 200, 60, "Billing Service", "shares the same key", "app"),
    arrow(260, 185, 560, 185, label="direct HTTPS"),
    arrow(260, 280, 560, 220, color="#fb7185", dash=True, label="same key, uncontrolled"),
    box(560, 150, 220, 70, "Provider (OpenAI)", "single point of failure", "prov"),
    '<text x="30" y="410" fill="#64748b" font-size="10" font-family="monospace">no fallback · no cache · no spend controls · availability = provider availability</text>',
]))

# step 2: gateway deployed beside
s2 = svg("2 · Deploy Bifrost beside the app", "".join([
    box(60, 150, 200, 70, "Support Copilot App", "unchanged for now", "app"),
    arrow(260, 185, 330, 185),
    box(330, 140, 200, 90, "Bifrost Gateway", "docker run -p 8080:8080", "gw"),
    arrow(530, 185, 620, 185),
    box(620, 150, 200, 70, "Provider (OpenAI)", "existing key, moved into config", "prov"),
    '<text x="330" y="270" fill="#94a3b8" font-size="9" font-family="monospace">nothing user-facing changes yet — same key, same provider, new hop</text>',
]))

# step 3: point one client
s3 = svg("3 · Point one client at the gateway", "".join([
    box(60, 120, 200, 70, "Copilot (migrated)", "base URL -> :8080", "app"),
    box(60, 250, 200, 70, "Billing Service", "still direct", "app"),
    arrow(260, 155, 340, 155, label="OpenAI-compatible"),
    arrow(260, 285, 620, 200, color="#64748b", dash=True, label="unchanged"),
    box(340, 120, 200, 70, "Bifrost Gateway", "", "gw"),
    arrow(540, 155, 620, 155),
    box(620, 120, 200, 70, "Provider", "", "prov"),
]))

# step 4: fallback
s4 = svg("4 · Add a fallback provider", "".join([
    box(60, 180, 200, 70, "Copilot", 'fallbacks: ["anthropic/model"]', "app"),
    arrow(260, 215, 330, 215),
    box(330, 170, 200, 90, "Bifrost Gateway", "request-level fallback chain", "gw"),
    arrow(530, 195, 620, 165, label="primary"),
    arrow(530, 235, 620, 285, color="#fb923c", dash=True, label="on failure"),
    box(620, 130, 200, 60, "Provider A", "primary", "prov"),
    box(620, 260, 200, 60, "Provider B", "fallback", "prov"),
    '<text x="620" y="350" fill="#34d399" font-size="9" font-family="monospace">routing_info records the fallback</text>',
]))

# step 5: cache
s5 = svg("5 · Enable semantic caching", "".join([
    box(60, 180, 200, 70, "Copilot", "FAQ-heavy traffic", "app"),
    arrow(260, 215, 330, 215),
    box(330, 170, 200, 90, "Bifrost", "semantic_cache plugin", "gw"),
    arrow(530, 195, 620, 165, label="cache miss"),
    arrow(430, 260, 430, 320),
    box(330, 320, 200, 60, "Vector Store", "Redis Stack (direct + similarity)", "cache"),
    box(620, 130, 200, 60, "Provider", "", "prov"),
    '<text x="330" y="405" fill="#a78bfa" font-size="9" font-family="monospace">measured: 32/60 requests served from cache · 53% token cost cut</text>',
]))

# step 6: virtual keys
s6 = svg("6 · Issue virtual keys per team", "".join([
    box(60, 110, 180, 60, "Support Team", "vk: support-chat only", "app"),
    box(60, 200, 180, 60, "Billing Team", "vk: own budget", "app"),
    box(60, 290, 180, 60, "Research Team", "vk: premium models", "app"),
    arrow(240, 140, 340, 200, color="#fb7185", dash=True)
    + arrow(240, 230, 340, 235, color="#fb7185", dash=True)
    + arrow(240, 320, 340, 270, color="#fb7185", dash=True),
    box(340, 190, 200, 110, "Bifrost Governance", "allowlists · budgets · rate limits", "gov"),
    arrow(540, 245, 630, 245),
    box(630, 205, 190, 70, "Providers", "per-key access enforced first", "prov"),
    '<text x="340" y="330" fill="#fb7185" font-size="9" font-family="monospace">denied at the gateway: "Model X is not allowed for this virtual key"</text>',
]))

# step 7: cutover
s7 = svg("7 · Cutover complete", "".join([
    box(60, 110, 180, 55, "Copilot", "", "app"),
    box(60, 185, 180, 55, "Billing", "", "app"),
    box(60, 260, 180, 55, "Agents (MCP)", "tools via gateway", "app"),
    arrow(240, 137, 340, 200) + arrow(240, 212, 340, 222) + arrow(240, 287, 340, 245),
    box(340, 180, 200, 90, "Bifrost", "one OpenAI-compatible API", "gw"),
    arrow(540, 205, 620, 150) + arrow(540, 225, 620, 230) + arrow(540, 245, 620, 310),
    box(620, 115, 200, 55, "OpenAI", "", "prov"),
    box(620, 195, 200, 55, "Anthropic", "fallback", "prov"),
    box(620, 275, 200, 55, "Vertex / others", "23+ providers", "prov"),
    '<text x="60" y="380" fill="#94a3b8" font-size="10" font-family="monospace">one integration surface · per-team keys · cache on repeat traffic · failover with an audit trail</text>',
]))

names = ["step1-legacy","step2-beside","step3-one-client","step4-fallback","step5-cache","step6-virtual-keys","step7-cutover"]
for name, s in zip(names, [s1,s2,s3,s4,s5,s6,s7]):
    p = os.path.join(OUT, name + ".svg")
    open(p, "w").write(s)
    subprocess.run(["rsvg-convert", "-w", "1760", p, "-o", p.replace(".svg", ".png")], check=True)
    print(name, "ok")
