"""Dark trading-desk dashboard: a rotating 3D implied-volatility surface plus term structure, smiles and skew."""
from __future__ import annotations

import html
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from .surface import atm_term_structure, grid, skew_25

BG, PANEL, GRID_C, TEXT, MUTED = "#06080b", "#0d1117", "#1b2230", "#d7dde8", "#7d8799"
ACCENT, ACCENT2, WARN = "#4cc9f0", "#e9c46a", "#e76f51"
SCALE = [[0.0, "#081c3a"], [0.22, "#123f73"], [0.45, "#1d6f8c"], [0.65, "#2a9d8f"],
         [0.82, "#e9c46a"], [1.0, "#e76f51"]]
FONT = "Inter, -apple-system, Segoe UI, sans-serif"
MONO = "JetBrains Mono, SFMono-Regular, Menlo, monospace"


def _axis(title):
    return dict(title=dict(text=title, font=dict(color=MUTED, size=12)), backgroundcolor=BG, gridcolor=GRID_C,
                zerolinecolor=GRID_C, showbackground=True, color=MUTED, tickfont=dict(family=MONO, size=10))


def surface_figure(df: pd.DataFrame, meta: dict) -> go.Figure:
    spot = meta["spot"]
    K, D, Z = grid(df, spot)
    fig = go.Figure()
    fig.add_trace(go.Surface(
        x=K, y=D, z=Z * 100, colorscale=SCALE, cmin=np.nanpercentile(Z * 100, 2), cmax=np.nanpercentile(Z * 100, 98),
        opacity=0.97, showscale=True, name="IV surface",
        colorbar=dict(title=dict(text="IV %", font=dict(color=MUTED)), tickfont=dict(color=MUTED, family=MONO),
                      thickness=12, len=0.65, x=0.98, outlinewidth=0),
        contours=dict(z=dict(show=True, usecolormap=True, project_z=True, width=1, highlightcolor=ACCENT)),
        lighting=dict(ambient=0.6, diffuse=0.75, specular=0.08, roughness=0.8, fresnel=0.02),
        lightposition=dict(x=2000, y=-2000, z=3000),
        hovertemplate="Strike %{x:.0f}<br>%{y:.0f} days<br>IV %{z:.1f}%<extra></extra>"))
    fig.add_trace(go.Scatter3d(
        x=df.strike, y=df.days, z=df.iv * 100, mode="markers", name="Market quotes",
        marker=dict(size=1.6, color=np.where(df.kind == "put", ACCENT, ACCENT2), opacity=0.4),
        customdata=np.stack([df.kind, df.expiry, df.mid], axis=1),
        hovertemplate="%{customdata[0]} %{x:.0f} · %{customdata[1]}<br>mid %{customdata[2]:.2f} · IV %{z:.1f}%<extra></extra>"))
    # spot line on the floor of the strike axis
    fig.add_trace(go.Scatter3d(x=[spot, spot], y=[D.min(), D.max()], z=[np.nanmin(Z) * 100] * 2, mode="lines",
                               line=dict(color="#ffffff", width=3, dash="dash"), name=f"Spot {spot:,.2f}",
                               hoverinfo="skip"))
    fig.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BG, font=dict(family=FONT, color=TEXT), margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(x=0.01, y=0.98, bgcolor="rgba(13,17,23,0.7)", bordercolor=GRID_C, borderwidth=1,
                    font=dict(size=11, color=MUTED)),
        scene=dict(xaxis=_axis("Strike"), yaxis=_axis("Days to expiry"), zaxis=_axis("Implied vol (%)"),
                   aspectmode="manual", aspectratio=dict(x=1.45, y=1.2, z=0.85),
                   camera=dict(eye=dict(x=1.38, y=-1.2, z=0.62), center=dict(x=0, y=0, z=-0.14))))
    return fig


def _small(title):
    return dict(paper_bgcolor=PANEL, plot_bgcolor=PANEL, font=dict(family=FONT, color=TEXT, size=11),
                margin=dict(l=48, r=16, t=36, b=40), title=dict(text=title, font=dict(size=13, color=TEXT), x=0.02),
                xaxis=dict(gridcolor=GRID_C, zerolinecolor=GRID_C, color=MUTED, tickfont=dict(family=MONO)),
                yaxis=dict(gridcolor=GRID_C, zerolinecolor=GRID_C, color=MUTED, tickfont=dict(family=MONO)),
                legend=dict(font=dict(size=10, color=MUTED), bgcolor="rgba(0,0,0,0)"), hovermode="x unified")


def term_figure(ts: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Scatter(x=ts.days, y=ts.atm_iv * 100, mode="lines+markers", line=dict(color=ACCENT, width=2),
                               marker=dict(size=5), name="ATM IV",
                               hovertemplate="%{x:.0f} days · %{y:.2f}%<extra></extra>"))
    fig.update_layout(**_small("ATM term structure"), xaxis_title="Days to expiry", yaxis_title="IV %")
    return fig


def smile_figure(df: pd.DataFrame, spot: float) -> go.Figure:
    exps = sorted(df.expiry.unique(), key=lambda e: df[df.expiry == e].days.iloc[0])
    targets = [30, 90, 180, 365]
    picks = []
    for t in targets:
        e = min(exps, key=lambda e: abs(df[df.expiry == e].days.iloc[0] - t))
        if e not in picks:
            picks.append(e)
    colors = [ACCENT, "#2a9d8f", ACCENT2, WARN]
    fig = go.Figure()
    for e, c in zip(picks, colors):
        g = df[df.expiry == e].sort_values("strike")
        fig.add_trace(go.Scatter(x=g.strike / spot * 100, y=g.iv * 100, mode="lines", line=dict(color=c, width=2),
                                 name=f"{e} ({g.days.iloc[0]:.0f}d)",
                                 hovertemplate="%{x:.0f}% of spot · %{y:.1f}%<extra></extra>"))
    fig.add_vline(x=100, line=dict(color=MUTED, dash="dot", width=1))
    fig.update_layout(**_small("Volatility smiles"), xaxis_title="Strike (% of spot)", yaxis_title="IV %")
    fig.update_layout(hovermode="closest", legend=dict(x=0.55, y=0.98))
    return fig


def skew_figure(sk: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Bar(x=sk.days, y=sk.skew_val * 100, marker=dict(color=sk.skew_val * 100, colorscale=SCALE, line=dict(width=0)),
                           hovertemplate="%{x:.0f} days · %{y:.2f} vol pts<extra></extra>", name="Skew"))
    fig.update_layout(**_small("Skew: IV(90%) − IV(110%)"), xaxis_title="Days to expiry", yaxis_title="vol points")
    return fig


ROTATE_JS = """
(function(){
  var gd = document.getElementById('surface');
  var angle = Math.atan2(-1.2, 1.38), r = Math.hypot(1.38, 1.2), z = 0.62, spinning = true, last = null;
  var btn = document.getElementById('spin');
  function frame(t){
    if (spinning){
      if (last !== null) angle += (t - last) * 0.00012;
      Plotly.relayout(gd, {'scene.camera.eye': {x: r*Math.cos(angle), y: r*Math.sin(angle), z: z}});
    }
    last = t; requestAnimationFrame(frame);
  }
  function set(on){ spinning = on; btn.textContent = on ? 'Pause rotation' : 'Resume rotation'; btn.classList.toggle('off', !on); }
  btn.addEventListener('click', function(){ set(!spinning); });
  gd.addEventListener('mousedown', function(){ set(false); });
  gd.addEventListener('wheel', function(e){ window.scrollBy(0, e.deltaY); }, {passive: true});
  gd.on('plotly_relayout', function(e){
    var eye = e && e['scene.camera'] && e['scene.camera'].eye;
    if (eye && !spinning){ angle = Math.atan2(eye.y, eye.x); r = Math.hypot(eye.x, eye.y); z = eye.z; }
  });
  requestAnimationFrame(frame);
})();
"""


def dashboard(df: pd.DataFrame, meta: dict, out: Path, plotlyjs: bool | str = True, back: str = "") -> Path:
    """Write the dashboard. plotlyjs=True embeds Plotly (works offline); "cdn" links it (small files for the website).
    back, if given, is a link shown above the title (the website uses it to go back to the ticker list)."""
    spot = meta["spot"]
    ts, sk = atm_term_structure(df, spot), skew_25(df, spot)
    atm30 = float(np.interp(30, ts.days, ts.atm_iv)) if len(ts) else float("nan")
    atm365 = float(np.interp(365, ts.days, ts.atm_iv)) if len(ts) else float("nan")
    cfg = dict(displaylogo=False, responsive=True, scrollZoom=False, modeBarButtonsToRemove=["toImage"])
    surf = pio.to_html(surface_figure(df, meta), full_html=False, include_plotlyjs=plotlyjs, div_id="surface", config=cfg)
    small = [pio.to_html(f, full_html=False, include_plotlyjs=False, config=dict(displaylogo=False, responsive=True))
             for f in (term_figure(ts), smile_figure(df, spot), skew_figure(sk))]
    stats = [("Spot", f"{spot:,.2f}"), ("ATM IV 30d", f"{atm30:.1%}"), ("ATM IV 1y", f"{atm365:.1%}"),
             ("Risk-free r", f"{meta['r']:.2%}"), ("Div. yield q", f"{meta['q']:.2%}"),
             ("Expiries", str(meta["n_expiries"])), ("Quotes used", f"{meta['n_used']:,} / {meta['n_raw']:,}")]
    tiles = "".join(f"<div class='tile'><span>{html.escape(a)}</span><b>{html.escape(b)}</b></div>" for a, b in stats)
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{meta['ticker']} Implied Volatility Surface</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
  :root {{ --bg:{BG}; --panel:{PANEL}; --line:{GRID_C}; --text:{TEXT}; --muted:{MUTED}; --accent:{ACCENT}; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text); font-family:{FONT}; }}
  header {{ display:flex; align-items:flex-end; justify-content:space-between; gap:16px; flex-wrap:wrap;
           padding:18px 28px 14px; border-bottom:1px solid var(--line); }}
  h1 {{ margin:0; font-size:22px; letter-spacing:.3px; }} h1 em {{ font-style:normal; color:var(--accent); }}
  .back {{ color:var(--muted); font-size:12px; text-decoration:none; display:inline-block; margin-bottom:6px; }} .back:hover {{ color:var(--accent); }}
  .sub {{ color:var(--muted); font-size:12px; margin-top:4px; font-family:{MONO}; }}
  .tiles {{ display:flex; gap:10px; flex-wrap:wrap; }}
  .tile {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:8px 12px; min-width:104px; }}
  .tile span {{ display:block; color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:.8px; }}
  .tile b {{ font-family:{MONO}; font-size:15px; font-weight:600; }}
  .main {{ position:relative; height:74vh; min-height:520px; }}
  #surface {{ height:100%; }}
  #spin {{ position:absolute; right:24px; top:14px; z-index:5; background:var(--panel); color:var(--text);
          border:1px solid var(--line); border-radius:6px; padding:7px 12px; font:600 12px {FONT}; cursor:pointer; }}
  #spin:hover {{ border-color:var(--accent); }} #spin.off {{ color:var(--accent); }}
  .row {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:12px; padding:12px 28px; }}
  .card {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; overflow:hidden; height:300px; }}
  .card > div {{ height:100%; }}
  footer {{ color:var(--muted); font-size:11px; padding:8px 28px 22px; line-height:1.6; }}
  @media (max-width: 900px) {{ .row {{ grid-template-columns:1fr; }} header {{ padding:14px 16px; }} .row, footer {{ padding-left:16px; padding-right:16px; }} }}
</style></head><body>
<header>
  <div>{f'<a class="back" href="{html.escape(back)}">← All tickers</a>' if back else ''}<h1><em>{meta['ticker']}</em> Implied Volatility Surface</h1>
  <div class="sub">Black-Scholes-Merton · Brent root-finding · OTM mids · as of {meta['asof']}</div></div>
  <div class="tiles">{tiles}</div>
</header>
<div class="main"><button id="spin">Pause rotation</button>{surf}</div>
<div class="row"><div class="card">{small[0]}</div><div class="card">{small[1]}</div><div class="card">{small[2]}</div></div>
<footer>
  Each dot is one out-of-the-money option quote (blue = put, gold = call). Its implied volatility σ solves
  BS(S, K, T, r, q, σ) = mid price using scipy.optimize.brentq on [0.01%, 500%]. The surface is interpolated in
  (log-moneyness, √T) and lightly smoothed. r is the 13-week T-bill (^IRX), q the dividend yield. Data: Yahoo Finance via yfinance,
  delayed and for study only. Reference: J. Hull, <i>Options, Futures, and Other Derivatives</i>, ch. 15 & 20.
  Drag to rotate · use the toolbar to zoom.
</footer>
<script>{ROTATE_JS}</script>
</body></html>"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out
