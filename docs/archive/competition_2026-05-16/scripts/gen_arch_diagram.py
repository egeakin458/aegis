"""
Generates Aegis system architecture diagram as a PNG for the poster.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np

# ── Palette ──────────────────────────────────────────────────────────────────
BG        = "#0f1117"
LAYER_BG  = "#1a1d27"
BORDER    = "#2a2d3a"

AGENT_BG  = "#1e2235"
AGENT_BD  = "#4f6ef7"   # blue border
AGENT_TX  = "#e8eaf6"

SCHEMA_BG = "#1a2a1a"
SCHEMA_BD = "#4caf7d"   # green
SCHEMA_TX = "#c8e6c9"

ARROW_COL = "#4f6ef7"
LOOP_COL  = "#f59e0b"   # amber for revision loops
WHITE     = "#e8eaf6"
MUTED     = "#8b8fa8"
TITLE_COL = "#ffffff"

W, H = 18, 10
fig, ax = plt.subplots(figsize=(W, H), facecolor=BG)
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")
ax.set_facecolor(BG)

def rbox(ax, x, y, w, h, fc, ec, lw=1.5, radius=0.3):
    box = FancyBboxPatch((x, y), w, h,
                         boxstyle=f"round,pad=0,rounding_size={radius}",
                         facecolor=fc, edgecolor=ec, linewidth=lw, zorder=3)
    ax.add_patch(box)

def label(ax, x, y, txt, size=9, color=WHITE, ha="center", va="center",
          bold=False, zorder=4):
    weight = "bold" if bold else "normal"
    ax.text(x, y, txt, fontsize=size, color=color, ha=ha, va=va,
            fontweight=weight, zorder=zorder, fontfamily="monospace")

def arrow(ax, x0, y0, x1, y1, color=ARROW_COL, lw=1.8,
          arrowstyle="-|>", ms=10, zorder=3):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle=arrowstyle, color=color,
                                lw=lw, mutation_scale=ms),
                zorder=zorder)

def dashed_arrow(ax, x0, y0, x1, y1, color=LOOP_COL, lw=1.5, zorder=3):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", color=color,
                                lw=lw, mutation_scale=9,
                                linestyle="dashed",
                                connectionstyle="arc3,rad=0.0"),
                zorder=zorder)

# ── Layer background panels ───────────────────────────────────────────────────

# Layer 3 — API & Persistence (top band)
rbox(ax,  0.3, 8.3, 17.4, 1.4, LAYER_BG, BORDER, lw=1, radius=0.25)
label(ax, 9.0, 9.55, "LAYER 3 — API & Persistence", size=8, color=MUTED, bold=True)

# Layer 2 — Lifecycle Management (middle band)
rbox(ax,  0.3, 5.9, 17.4, 2.0, LAYER_BG, BORDER, lw=1, radius=0.25)
label(ax, 9.0, 7.65, "LAYER 2 — Lifecycle Management  (RunnerManager)", size=8, color=MUTED, bold=True)

# Layer 1 — Pipeline Engine (bottom band)
rbox(ax,  0.3, 0.5, 17.4, 5.05, LAYER_BG, BORDER, lw=1, radius=0.25)
label(ax, 9.0, 5.25, "LAYER 1 — Pipeline Engine  (PipelineRunner + Agents)", size=8, color=MUTED, bold=True)

# ── Layer 3 boxes ─────────────────────────────────────────────────────────────
L3_Y = 8.55; L3_H = 0.65

rbox(ax, 0.6,  L3_Y, 3.2, L3_H, "#12192e", AGENT_BD, radius=0.2)
label(ax, 2.2, L3_Y+0.33, "POST /start", size=8.5, color=AGENT_TX, bold=True)

rbox(ax, 4.1,  L3_Y, 3.6, L3_H, "#12192e", AGENT_BD, radius=0.2)
label(ax, 5.9, L3_Y+0.33, "GET /{id}/events  (SSE)", size=8.5, color=AGENT_TX, bold=True)

rbox(ax, 8.0,  L3_Y, 3.6, L3_H, "#12192e", AGENT_BD, radius=0.2)
label(ax, 9.8, L3_Y+0.33, "POST /{id}/clarification", size=8.5, color=AGENT_TX, bold=True)

rbox(ax, 11.9, L3_Y, 2.4, L3_H, "#12192e", AGENT_BD, radius=0.2)
label(ax, 13.1, L3_Y+0.33, "GET /{id}/status", size=8.5, color=AGENT_TX, bold=True)

rbox(ax, 14.6, L3_Y, 2.8, L3_H, "#12192e", AGENT_BD, radius=0.2)
label(ax, 16.0, L3_Y+0.33, "GET /{id}/output", size=8.5, color=AGENT_TX, bold=True)

# Persistence row
rbox(ax, 0.6, 8.3+0.02, 17.1, 0.25, "#0a1520", BORDER, lw=0.8, radius=0.1)
label(ax, 9.15, 8.3+0.135, "SQLite  (pipeline_runs, pipeline_events)   ·   outputs/{run_id}/   (manifest.json + files)",
      size=7.5, color=MUTED)

# ── Layer 2 boxes ─────────────────────────────────────────────────────────────
L2_Y = 6.15; L2_H = 0.75

rbox(ax, 0.6,  L2_Y, 4.2, L2_H, AGENT_BG, AGENT_BD, radius=0.2)
label(ax, 0.9, L2_Y+0.55, "RunnerManager", size=8.5, color=AGENT_TX, bold=True, ha="left")
label(ax, 0.9, L2_Y+0.22, "spawn · track · cleanup runs", size=7.5, color=MUTED, ha="left")

rbox(ax, 5.1,  L2_Y, 4.2, L2_H, AGENT_BG, AGENT_BD, radius=0.2)
label(ax, 5.4, L2_Y+0.55, "Event Bus", size=8.5, color=AGENT_TX, bold=True, ha="left")
label(ax, 5.4, L2_Y+0.22, "SSE queue  +  SQLite fire-and-forget", size=7.5, color=MUTED, ha="left")

rbox(ax, 9.6,  L2_Y, 3.5, L2_H, AGENT_BG, AGENT_BD, radius=0.2)
label(ax, 9.9, L2_Y+0.55, "Clarification Gate", size=8.5, color=AGENT_TX, bold=True, ha="left")
label(ax, 9.9, L2_Y+0.22, "pause pipeline → await answers", size=7.5, color=MUTED, ha="left")

rbox(ax, 13.4, L2_Y, 4.0, L2_H, AGENT_BG, AGENT_BD, radius=0.2)
label(ax, 13.7, L2_Y+0.55, "Keepalive / Replay", size=8.5, color=AGENT_TX, bold=True, ha="left")
label(ax, 13.7, L2_Y+0.22, "30s ping  ·  event replay on reconnect", size=7.5, color=MUTED, ha="left")

# ── Layer 1 — Agent pipeline ──────────────────────────────────────────────────
# Row heights
AY   = 2.9   # agent box top-left y
AH   = 1.2   # agent box height
AW   = 2.5   # agent box width

# Schema strip y
SY   = 1.05
SH   = 0.55

agents = [
    ("Requirements\nAnalyst", "RA"),
    ("Solution\nArchitect",   "SA"),
    ("Developer",             "Dev"),
    ("QA\nReviewer",          "QA"),
]

schemas = [
    "CustomerConfigV2\n(finalized)",
    "TechnicalDesign",
    "CodeOutput /\nCodePatch (rev.)",
    "QAReview",
]

# Layout: input(0.45–1.35) → gap → RA(1.55–4.05) → gap → SA(4.25–6.75)
#         → gap → Dev(6.95–9.45) → gap → BC(9.75–11.35) → gap → QA(11.65–14.15)
#         → gap → COMPLETE(14.4–16.9)   Legend floats inside Layer1 bottom-right
XS = [1.55, 4.25, 6.95, 11.65]
BC_X = 9.75; BC_W = 1.7; BC_H = 0.9; BC_Y = AY + 0.15

for i, ((name, abbr), schema) in enumerate(zip(agents, schemas)):
    ax_x = XS[i]
    # Agent box
    rbox(ax, ax_x, AY, AW, AH, AGENT_BG, AGENT_BD, lw=2.0, radius=0.3)
    label(ax, ax_x + AW/2, AY + AH*0.62, name, size=10, color=AGENT_TX, bold=True)
    label(ax, ax_x + AW/2, AY + AH*0.25, f"({abbr})", size=8, color=MUTED)

    # Schema box below
    rbox(ax, ax_x, SY, AW, SH, SCHEMA_BG, SCHEMA_BD, lw=1.5, radius=0.2)
    label(ax, ax_x + AW/2, SY + SH/2, schema, size=7.5, color=SCHEMA_TX)

    # Arrow from agent down to schema
    arrow(ax, ax_x + AW/2, AY, ax_x + AW/2, SY + SH, color=SCHEMA_BD, lw=1.4, ms=8)

# Arrows between schemas (schema right-edge → next agent left-edge)
# RA→SA, SA→Dev: straight horizontal through schema row
for i in range(2):
    sx = XS[i] + AW
    nx = XS[i+1]
    mid_y = SY + SH/2
    arrow(ax, sx, mid_y, nx, mid_y, color=SCHEMA_BD, lw=1.6, ms=9)

# Dev schema → QA schema (skip BuildCheck — BC is on the agent row)
sx = XS[2] + AW; nx = XS[3]; mid_y = SY + SH/2
arrow(ax, sx, mid_y, nx, mid_y, color=SCHEMA_BD, lw=1.6, ms=9)

# Input box + arrow into RA
rbox(ax, 0.45, AY+0.2, 0.85, 0.8, SCHEMA_BG, SCHEMA_BD, lw=1.4, radius=0.2)
label(ax, 0.875, AY+0.72, "Customer", size=7.5, color=SCHEMA_TX, bold=True)
label(ax, 0.875, AY+0.42, "ConfigV2", size=7.5, color=SCHEMA_TX)
label(ax, 0.875, AY+0.23, "(intake)", size=6.5, color=MUTED)
ax.annotate("", xy=(XS[0], AY + AH/2), xytext=(0.45+0.85, AY + AH/2),
            arrowprops=dict(arrowstyle="-|>", color=SCHEMA_BD, lw=1.6, mutation_scale=9), zorder=3)

# BuildCheck box (in the gap between Dev and QA on the agent row)
rbox(ax, BC_X, BC_Y, BC_W, BC_H, "#1e1a10", "#f59e0b", lw=1.5, radius=0.2)
label(ax, BC_X + BC_W/2, BC_Y + BC_H*0.65, "Build", size=8.5, color="#fcd34d", bold=True)
label(ax, BC_X + BC_W/2, BC_Y + BC_H*0.28, "Check", size=8.5, color="#fcd34d", bold=True)

# Arrow Dev → BuildCheck
arrow(ax, XS[2]+AW, AY+AH/2, BC_X, BC_Y+BC_H/2, color=LOOP_COL, lw=1.5, ms=9)
# Arrow BuildCheck → QA
arrow(ax, BC_X+BC_W, BC_Y+BC_H/2, XS[3], AY+AH/2, color=LOOP_COL, lw=1.5, ms=9)

# ── Feedback loops ────────────────────────────────────────────────────────────
qa_cx  = XS[3] + AW/2
dev_cx = XS[2] + AW/2
sa_cx  = XS[1] + AW/2

# revise_code: QA → Dev
ax.annotate("", xy=(dev_cx, AY), xytext=(qa_cx, AY),
            arrowprops=dict(arrowstyle="-|>", color=LOOP_COL, lw=1.6,
                            mutation_scale=9,
                            connectionstyle="arc,angleA=-90,angleB=-90,armA=60,armB=60,rad=8"),
            zorder=3)
label(ax, (dev_cx+qa_cx)/2, AY - 0.68,
      "revise_code  (max 2×)", size=7.5, color=LOOP_COL)

# revise_design: QA → SA
ax.annotate("", xy=(sa_cx, AY), xytext=(qa_cx, AY),
            arrowprops=dict(arrowstyle="-|>", color="#f87171", lw=1.4,
                            mutation_scale=9,
                            connectionstyle="arc,angleA=-90,angleB=-90,armA=95,armB=95,rad=8"),
            zorder=3)
label(ax, (sa_cx+qa_cx)/2, AY - 1.32,
      "revise_design  (max 1×)", size=7.5, color="#f87171")

# ── Approve terminal ──────────────────────────────────────────────────────────
DONE_X = 14.45; DONE_Y = AY + 0.25
rbox(ax, DONE_X, DONE_Y, 2.5, 0.7, "#0d2218", SCHEMA_BD, lw=1.8, radius=0.25)
label(ax, DONE_X+1.25, DONE_Y+0.35, "COMPLETE", size=9, color="#4caf7d", bold=True)
arrow(ax, XS[3]+AW, AY+AH/2, DONE_X, DONE_Y+0.35, color=SCHEMA_BD, lw=1.8, ms=10)
label(ax, DONE_X-0.4, DONE_Y+0.6, "approve", size=7.5, color=SCHEMA_BD)

# ── Legend (inside Layer1 panel, bottom-right) ────────────────────────────────
LX = 15.0; LY_start = 1.95
label(ax, LX+0.05, LY_start+0.52, "Legend", size=8, color=MUTED, ha="left", bold=True)
rbox(ax, LX, LY_start+0.05, 0.38, 0.25, AGENT_BG, AGENT_BD, radius=0.06)
label(ax, LX+0.62, LY_start+0.17, "Agent", size=7.5, color=MUTED, ha="left")
rbox(ax, LX, LY_start-0.32, 0.38, 0.25, SCHEMA_BG, SCHEMA_BD, radius=0.06)
label(ax, LX+0.62, LY_start-0.20, "Schema / artifact", size=7.5, color=MUTED, ha="left")
ax.plot([LX+0.0, LX+0.38], [LY_start-0.65, LY_start-0.65], color=LOOP_COL, lw=2)
label(ax, LX+0.62, LY_start-0.65, "Revision loop", size=7.5, color=MUTED, ha="left")

# ── Title ─────────────────────────────────────────────────────────────────────
label(ax, 9.0, 9.85, "Aegis — System Architecture", size=13, color=TITLE_COL, bold=True)

# ── Save ──────────────────────────────────────────────────────────────────────
out = "/home/ege/projects/aegis/docs/system_architecture.png"
fig.savefig(out, dpi=200, bbox_inches="tight", facecolor=BG)
print(f"Saved → {out}")
