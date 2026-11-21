"""График напряжения и падения от длины, встроенный в окно Qt."""

from __future__ import annotations

import math
import os

# backend_qtagg должен взять PySide6, а не PyQt, если в системе стоят оба.
os.environ.setdefault("QT_API", "pyside6")

import matplotlib

# DejaVu Sans поставляется с matplotlib и содержит кириллицу.
matplotlib.rcParams["font.family"] = "DejaVu Sans"
matplotlib.rcParams["axes.unicode_minus"] = False

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import FuncFormatter, MultipleLocator
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from calculator import SweepPoint
from data import LENGTH_MAX_M
from gui.themes import Theme


def _comma_tick(value: float, _position: int) -> str:
    if abs(value - round(value)) < 1e-6:
        return str(int(round(value)))
    return f"{value:.1f}".replace(".", ",")


class PlotWidget(QWidget):
    """Оси ΔU и Vpd. Один Figure живёт всё время работы окна."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("plotWidget")
        self._font = FontProperties(family="DejaVu Sans", size=8)
        self._title_font = FontProperties(family="DejaVu Sans", size=11)
        self._figure = Figure(figsize=(6.4, 3.6))
        self._figure.subplots_adjust(left=0.09, right=0.98, top=0.90, bottom=0.32)
        self._axes = self._figure.add_subplot(111)
        self._canvas = FigureCanvas(self._figure)
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(200)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

    @property
    def figure(self) -> Figure:
        return self._figure

    def update_chart(
        self,
        sweep: tuple[SweepPoint, ...],
        *,
        length_m: float,
        v_pd_min: float,
        max_working_length_m: float | None,
        theme: Theme,
    ) -> None:
        axes = self._axes
        axes.clear()
        face = theme.plot_face
        self._figure.patch.set_facecolor(face)
        axes.set_facecolor(face)

        if max_working_length_m is None:
            axes.axvspan(0, LENGTH_MAX_M, color=theme.plot_shade, alpha=0.10, linewidth=0)
        elif max_working_length_m < LENGTH_MAX_M - 0.05:
            axes.axvspan(
                max_working_length_m,
                LENGTH_MAX_M,
                color=theme.plot_shade,
                alpha=0.10,
                linewidth=0,
            )

        lengths = [point.length_m for point in sweep]
        v_pd = [point.v_pd if point.v_pd is not None else math.nan for point in sweep]
        delta_u = [point.delta_u_v if point.delta_u_v is not None else math.nan for point in sweep]
        axes.plot(lengths, v_pd, color=theme.plot_vpd, linewidth=2.0, label="Напряжение на PD")
        axes.plot(lengths, delta_u, color=theme.plot_du, linewidth=2.0, label="Падение напряжения")
        axes.axhline(
            v_pd_min,
            color=theme.plot_limit,
            linestyle=":",
            linewidth=1.3,
            label="Минимум напряжения PD",
        )
        axes.axvline(
            length_m,
            color=theme.plot_current,
            linestyle="-",
            linewidth=1.2,
            label="Текущая длина",
        )
        if max_working_length_m is not None:
            axes.axvline(
                max_working_length_m,
                color=theme.plot_max_len,
                linestyle="--",
                linewidth=1.2,
                label="Максимальная рабочая длина",
            )

        current = next((point for point in sweep if point.length_m == length_m), None)
        if current is not None and current.v_pd is not None:
            axes.scatter(
                [length_m],
                [current.v_pd],
                s=32,
                zorder=5,
                color=theme.plot_vpd,
                edgecolors=face,
                linewidths=0.6,
            )

        axes.set_xlim(-1, LENGTH_MAX_M + 1)
        axes.set_ylim(0, 62)
        axes.xaxis.set_major_locator(MultipleLocator(25))
        axes.yaxis.set_major_locator(MultipleLocator(10))
        formatter = FuncFormatter(_comma_tick)
        axes.xaxis.set_major_formatter(formatter)
        axes.yaxis.set_major_formatter(formatter)
        axes.set_xlabel(
            "Длина кабеля, м",
            color=theme.plot_text,
            fontproperties=self._font,
            labelpad=4,
        )
        axes.set_ylabel("Напряжение, В", color=theme.plot_text, fontproperties=self._font)
        axes.set_title(
            "Зависимость от длины кабеля",
            color=theme.plot_text,
            fontproperties=self._title_font,
            pad=8,
        )
        axes.tick_params(colors=theme.plot_text, labelsize=8)
        axes.grid(True, color=theme.plot_grid, linewidth=0.6)
        axes.set_axisbelow(True)
        for spine in axes.spines.values():
            spine.set_color(theme.plot_grid)

        legend = axes.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, -0.28),
            ncol=3,
            frameon=False,
            fontsize=8,
        )
        for text in legend.get_texts():
            text.set_color(theme.plot_text)
            text.set_fontproperties(self._font)

        self._canvas.draw_idle()
