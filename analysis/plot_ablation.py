"""Checklist match and token yield for the report figure."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
PALETTE = {"blue_main": "#0F4D92", "green_3": "#8BCF8B", "red_strong": "#B64342", "teal": "#42949E"}


@dataclass(frozen=True)
class FigureStyle:
    font_size: int = 16
    axes_linewidth: float = 2.5


def apply_publication_style(style: FigureStyle | None = None) -> None:
    style = style or FigureStyle()
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
        "font.size": style.font_size,
        "axes.linewidth": style.axes_linewidth,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def main() -> None:
    data = json.loads((ROOT / "analysis" / "ablation.json").read_text(encoding="utf-8"))
    names = ["P0", "P1", "P2", "P3"]
    match = [100 * data[name]["checklist_match_rate"] for name in names]
    yield_ = [data[name]["matches_per_1k_tokens"] for name in names]
    apply_publication_style(FigureStyle(font_size=14, axes_linewidth=2))
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.2))
    colors = [PALETTE["blue_main"], PALETTE["red_strong"], PALETTE["teal"], PALETTE["green_3"]]
    for ax, values, ylabel, title in (
        (axes[0], match, "Checklist match (%)", "Match rate"),
        (axes[1], yield_, "Matches per 1,000 tokens", "Token yield"),
    ):
        bars = ax.bar(names, values, color=colors, width=0.72)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{value:.2f}",
                    ha="center", va="bottom", fontsize=11)
        ax.set_ylim(0, max(values) * 1.25)
    fig.tight_layout()
    out = ROOT / "analysis" / "figures" / "ablation"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)
    print(out.with_suffix(".png"))


if __name__ == "__main__":
    main()