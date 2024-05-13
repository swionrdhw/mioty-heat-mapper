import PySimpleGUI as sg  # type: ignore
import logging

from pathlib import Path
from typing import Optional

import mioty_heat_mapper.acmqtti as acmqtti
from mioty_heat_mapper.graph import generate_graphs
from mioty_heat_mapper.measurement import Location, Measurement
from mioty_heat_mapper.misc import load_image_as_png
from mioty_heat_mapper.state import State


def start_gui(config_path: Path, state: State) -> None:
    """
    Starts the GUI of the application.
    """

    try:
        img, img_bytes, canvas_size = load_image_as_png(
            state.map_path, state.dpi
        )
    except Exception as e:
        print(f"Error loading background image: {e}")
        exit(1)

    right_click_items = [
        "Items",
        ["&Measure", "&Delete", "&Mark/Un-Mark as Station"],
    ]
    graph = sg.Graph(
        canvas_size=canvas_size,
        graph_bottom_left=(0, 0),
        graph_top_right=canvas_size,
        key="Floor Map",
        enable_events=True,
        background_color="White",
        right_click_menu=right_click_items,
    )
    layout = [
        [graph],
        [
            sg.Button("Exit"),
            sg.Button("Clear All"),
            sg.Button("Measure"),
            sg.Button("Save Results"),
            sg.Button("Plot"),
        ],
    ]
    window = sg.Window("mioty Heat Mapper", layout, finalize=True)

    logging.info("Drawing on canvas")
    # photo_image = ImageTk.PhotoImage(img)  # type: ignore
    logging.info("Updated canvas")

    current_selection: Optional[Location] = None

    # TODO: Load previous measurements

    print("Ready for benchmarking.")

    post_process = False
    redraw(graph, img_bytes, state.locations, current_selection)

    while True:
        event, values = window.read()

        logging.debug(f"Window event: {event}")

        if event == "Exit" or event == sg.WIN_CLOSED:
            break

        if event == "Floor Map":
            mouse = values["Floor Map"]
            if mouse == (None, None):
                continue

            point_has_measurement = False
            for loc in state.locations:
                if point_lies_within_circle(mouse, loc.position):
                    point_has_measurement = True
                    current_selection = loc
                    break

            if not point_has_measurement:
                loc = Location(position=mouse)
                state.locations.append(loc)
                current_selection = loc

        if event == "Delete":
            if current_selection is not None:
                state.locations.remove(current_selection)
                current_selection = None

        if event == "Measure":
            if (
                current_selection is not None
                and not current_selection.is_base_station
            ):
                acquire(state, current_selection)
            else:
                sg.popup_error("Please select a measurement location.")

        if event == "Mark/Un-Mark as Station":
            if current_selection is not None:
                # TODO: only if it doesn't have results already
                current_selection.is_base_station = (
                    not current_selection.is_base_station
                )

        if event == "Save Results":
            current_selection = None

            try:
                state.save(config_path)
                sg.popup_ok("Configuration saved.")
            except Exception as e:
                sg.popup_error(f"Error saving configuration: {e}")

        if event == "Plot":
            valid_benchmark_points = len(
                [True for x in state.locations if len(x.measurements) >= 1]
            )
            if valid_benchmark_points >= 4:
                current_selection = None
                post_process = True
                break
            else:
                sg.popup_error("Not enough measurements.")

        if event == "Clear All":
            state.locations = []
            current_selection = None

        # Redraws the graph with the current state
        redraw(graph, img_bytes, state.locations, current_selection)

    window.close()

    if post_process:
        generate_graphs(config_path, state)


def point_lies_within_circle(
    pt1: tuple[float, float], pt2: tuple[float, float]
) -> bool:
    """
    Checks if tuple (x, y) of first point lies in a circle contructed from the
    center point of second point.

    Args:
        pt1 (tuple): tuple of (x, y).
        pt2 (tuple): tuple of (x, y).
    """
    return ((pt1[0] - pt2[0]) ** 2 + (pt1[1] - pt2[1]) ** 2) <= 7**2


def redraw(
    graph: sg.Graph,
    background: bytes,
    locations: list[Location],
    current_selection: Optional[Location],
) -> None:
    """
    Redraws the graph with the measurement points.

    Colors: https://htmlcolorcodes.com/color-chart/material-design-color-chart/
    """
    graph.erase()
    _, height = graph.get_size()
    assert isinstance(height, int)
    graph.DrawImage(data=background, location=(0, height))
    for loc in locations:
        if loc.is_base_station:
            if loc is current_selection:
                fill_color = "#ffcc80"
            else:
                fill_color = "#ff9800"
        elif loc is current_selection:
            fill_color = "#81d4fa"
        else:
            fill_color = "#039be5"
        loc.gui_id = graph.draw_circle(loc.position, 7, fill_color)


def acquire(state: State, current_location: Location) -> None:
    """
    Begins acquiring new measurements for a given measurement point.
    """

    if state.acmqtti_broker is None:
        sg.popup_error("MQTT Broker not set.")
        return

    password: Optional[str] = None
    if state.acmqtti_broker_username is not None:
        password = sg.popup_get_text(
            f"ACMQTTI Password for {state.acmqtti_broker_username}"
        )

    broker_addr = state.acmqtti_broker.split(":")[0]
    broker_port = int(state.acmqtti_broker.split(":")[1])
    config = acmqtti.AcmqttiConfig(
        broker_addr=broker_addr,
        broker_port=broker_port,
        ac_eui=state.acmqtti_ac_eui,
        ep_euis=state.acmqtti_ep_euis,
        username=state.acmqtti_broker_username,
        password=password,
        tls_ca_cert=state.acmqtti_broker_tls_ca_cert,
        sub_measurements=state.sub_measurements,
    )

    def record(measurement: Measurement) -> None:
        current_location.measurements.append(measurement)

    mqtt_client = acmqtti.measure(config, record)

    sg.popup_cancel("Measuring until cancelled...", keep_on_top=True)

    mqtt_client.disconnect()
    # return results
