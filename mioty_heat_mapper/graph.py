import json
import logging
import math
import matplotlib.pyplot as plt
import statistics

from PIL import Image
from matplotlib.axes import Axes
from pathlib import Path
from typing import Any, Optional

from mioty_heat_mapper import wgs84
from mioty_heat_mapper.acmqtti import (
    build_locadis_supply_rss_data_request,
    build_locadis_train_request,
)
from mioty_heat_mapper.measurement import Location
from mioty_heat_mapper.misc import image_has_transparency, load_image_as_png
from mioty_heat_mapper.state import State


class DataPoint:
    def __init__(self, x: float, y: float, value: float) -> None:
        self.x = x
        self.y = y
        self.value = value


class BaseStation:
    def __init__(self, x: float, y: float, description: Optional[str]) -> None:
        self.x = x
        self.y = y
        self.description = description


def generate_graph(
    config_path: Path,
    state: State,
    factor_key: str,
    bs_key: Optional[str] = None,
) -> None:
    """
    Generates a specific plot.
    """

    logging.debug(f"Generating plot for {factor_key}...")

    factor = state.factors.get(factor_key)
    assert factor is not None

    # Loads the background image and determines its size.
    try:
        img, img_bytes, canvas_size = load_image_as_png(
            state.map_path, state.dpi
        )
        xmax, ymax = img.size
    except Exception as e:
        print(f"Error loading background image: {e}")
        exit(1)

    # Extracts the data points to be plotted.
    data_points: list[DataPoint] = []
    base_stations: dict[str, BaseStation] = {}
    val_count = 0

    for key, loc in [
        (key, loc)
        for loc in state.locations
        if loc.is_base_station and (key := loc.bs_key) is not None
    ]:
        base_stations[key] = BaseStation(
            loc.position[0], loc.position[1], loc.description
        )

    for loc in [loc for loc in state.locations if not loc.is_base_station]:
        if state.sub_measurements:
            subvals = [
                (snrs, subs)
                for meas in loc.measurements
                if meas.sub_measurement is not None
                and (bs_key is None or meas.bs_key == bs_key)
                and (subs := meas.sub_measurement.get(factor_key)) is not None
                and (snrs := meas.sub_measurement.get("snr")) is not None
            ]
            vals = [
                val
                for (snrs, vals) in subvals
                for (snr, val) in zip(snrs, vals)
                if snr is not None and snr > -5 and val is not None
            ]
        else:
            vals = [
                val
                for meas in loc.measurements
                if (bs_key is None or meas.bs_key == bs_key)
                and (val := meas.get(factor_key)) is not None
                and (snr := meas.get("snr")) is not None
                and snr > -5
            ]
        if len(vals) == 0:
            continue
        val_count = val_count + len(vals)
        agg = max(vals) if bs_key is None else statistics.median(vals)
        data_points.append(DataPoint(loc.position[0], loc.position[1], agg))

    key = "global" if bs_key is None else bs_key

    if len(data_points) < 4:
        print(f"Skipping {key} with too few data points.")
        return

    print(f"Plotting {key}...")
    print(f" - {len(data_points)} data points (locations)")
    print(f" - {val_count} individual values")

    # Determines effective vmin, vmax and vzero.
    vmin = factor.vmin
    vmax = factor.vmax
    vzero = factor.vzero
    if vmin is None:
        vmin = min([dp.value for dp in data_points])
    if vmax is None:
        vmax = max([dp.value for dp in data_points])
    if vzero is None:
        vzero = vmin

    # Adds the boundary conditions.
    if state.extrapolate:
        data_points.append(DataPoint(0, 0, vzero))
        data_points.append(DataPoint(0, ymax, vzero))
        data_points.append(DataPoint(xmax, 0, vzero))
        data_points.append(DataPoint(xmax, ymax, vzero))

    fig, ax = plt.subplots(1, 1, figsize=(xmax / 100, ymax / 100))
    assert isinstance(ax, Axes)

    bench_plot = ax.tricontourf(
        [dp.x for dp in data_points],
        [dp.y for dp in data_points],
        [dp.value for dp in data_points],
        alpha=0.5,
        cmap=state.colormap,
        levels=state.contours,
        vmin=vmin,
        vmax=vmax,
        zorder=150,
    )

    fdim_coef = math.sqrt(xmax * ymax)
    marker_size = max(4, fdim_coef // 210)
    ax.plot(
        [dp.x for dp in data_points],
        [dp.y for dp in data_points],
        zorder=200,
        marker="o",
        markeredgecolor="black",
        markeredgewidth=0.5,
        linestyle="None",
        linewidth=0,
        markersize=marker_size,
        label="Benchmark Point",
    )

    ax.plot(
        [bs.x for bs in base_stations.values() if bs.x >= 0 and bs.y >= 0],
        [bs.y for bs in base_stations.values() if bs.x >= 0 and bs.y >= 0],
        zorder=250,
        marker="o",
        markeredgecolor="black",
        markerfacecolor="orange",
        markeredgewidth=0.5,
        linestyle="None",
        markersize=marker_size,
        label="Base Station",
    )

    ax.imshow(
        img.transpose(Image.Transpose.FLIP_TOP_BOTTOM),
        zorder=1000 if image_has_transparency(img) else 1,
        alpha=1,
        origin="lower",
    )

    title_size = max(10, fdim_coef // 70)
    label_size = max(7, title_size - 5)

    cb = fig.colorbar(bench_plot)
    cb.ax.tick_params(labelsize=label_size)
    if bs_key is not None:
        bs = base_stations.get(bs_key)
        if bs is not None and bs.description is not None:
            bs_name = bs.description
        else:
            bs_name = bs_key
        title = f"{factor.description} [{factor.unit}], {bs_name}"
    else:
        title = f"{factor.description} [{factor.unit}]"

    plt.title(title, fontsize=title_size)
    plt.axis("off")
    plt.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.05),
        ncol=2,
        prop={"size": label_size},
    )

    config_dir = config_path.parents[0]
    config_name = config_path.stem
    if bs_key is not None:
        file_name = f"{factor_key}_{bs_key}.{state.file_format}"
    else:
        file_name = f"{factor_key}.{state.file_format}"
    (config_dir / config_name).mkdir(exist_ok=True)
    full_path = config_dir / config_name / file_name
    print(full_path)
    plt.savefig(full_path, format=state.file_format, dpi=2 * state.dpi)


def generate_graphs(config_path: Path, state: State) -> None:
    """
    Generates all plots from a set of measurements.
    """

    for key in state.factors.keys():
        generate_graph(config_path, state, key)

    base_stations = set(
        [
            m.bs_key
            for loc_m in [loc.measurements for loc in state.locations]
            for m in loc_m
        ]
    )

    for bs_key in base_stations:
        for key in state.factors.keys():
            generate_graph(config_path, state, key, bs_key=bs_key)


def generate_locadis(config_path: Path, state: State) -> None:
    """
    Generates all training data sets for locadis.
    """

    if state.wgs84 is None:
        print("Cannot generate locadis data without WGS84 coordinates")
        exit(1)

    logging.debug("Generating locadis messages...")

    # Loads the background image and determines its size.
    try:
        img, img_bytes, canvas_size = load_image_as_png(
            state.map_path, state.dpi
        )
        xmax, ymax = img.size
    except Exception as e:
        print(f"Error loading background image: {e}")
        exit(1)

    def json_rpc(id: int, payload: dict[str, Any]) -> str:
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "id": id,
                **payload,
            }
        )

    config_dir = config_path.parents[0]
    config_name = config_path.stem
    world = wgs84.World(state.wgs84, xmax, ymax)

    locs = [
        (
            world.to_wgs(loc.position[0], loc.position[1]),
            [r for r in loc.measurements],
        )
        for loc in state.locations
    ]

    file_name = "measurements.jsonl"
    (config_dir / config_name).mkdir(exist_ok=True)
    full_path = config_dir / config_name / file_name

    _id = 0
    with open(full_path, "w") as f:
        for c, results in locs:
            if len(results) == 0:
                continue

            _id = _id + 1
            j = json_rpc(_id, build_locadis_train_request(c.lat(), c.lon()))
            f.write(f"{j}\n")

            for m in results:
                _id = _id + 1
                j = json_rpc(_id, build_locadis_supply_rss_data_request(m))
                f.write(f"{j}\n")
