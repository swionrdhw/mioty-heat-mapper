import json
import os
import re
import sys
import traceback

from enum import StrEnum
from pathlib import Path
from typing import Any, Optional

from mioty_heat_mapper import wgs84
from mioty_heat_mapper.measurement import Location, Measurement, SubMeasurement


SUPPORTED_EXPORT_FILE_FORMATS = ["png", "pdf", "ps", "eps", "svg"]


class Mode(StrEnum):
    """
    Test modes supported by the application.

    The mode `BASE` is always supported by the application, for tests that do
    not need any further configuration or information.
    """

    UNKNOWN = "unknown"
    BASE = "base"
    ACMQTTI = "acmqtti"


class QualityFactor:
    """
    Represents a quality factor that can be measured by the application.
    """

    def __init__(
        self,
        description: str,
        modes: list[Mode],
        unit: str,
        reversed: bool = False,
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
        vzero: Optional[float] = None,
    ):
        self.description = description
        self.modes = modes
        self.reversed = reversed
        self.unit = unit
        self.vmin = vmin
        self.vmax = vmax
        self.vzero = vzero

    """
    Checks if this quality factor can be measured using the selected test modes.
    """

    def supported_for(self, selected_modes: list[Mode]) -> bool:
        for mode in self.modes:
            if mode not in selected_modes:
                return False

        return True


QUALITY_FACTORS = {
    "rssi": QualityFactor("RSSI", [Mode.ACMQTTI], "dBm", vmin=-140, vmax=-40),
    "snr": QualityFactor(
        "Signal-to-Noise", [Mode.ACMQTTI], "dBm", vmin=0, vmax=30
    ),
    "eq_snr": QualityFactor(
        "Equivalent SNR", [Mode.ACMQTTI], "dBm", vmin=0, vmax=30
    ),
}


class State:
    def __init__(self) -> None:
        """
        Initializes a default config file for the application.
        """
        supported_modes = [Mode.BASE, Mode.ACMQTTI]
        supported_factors = dict(
            [
                (key, val)
                for key, val in QUALITY_FACTORS.items()
                if val.supported_for(supported_modes)
            ]
        )

        self.colormap: str = "gnuplot2"
        self.contours: int = 100
        self.dpi: int = 300
        self.extrapolate: bool = False
        self.factors = supported_factors
        self.file_format: str = "svg"
        self.locations: list[Location] = []
        self.map_path = Path("")
        self.modes = supported_modes
        self.sub_measurements = False

        self.acmqtti_ac_eui: Optional[str] = None
        self.acmqtti_ep_euis: Optional[list[str]] = None
        self.acmqtti_broker: Optional[str] = None
        self.acmqtti_broker_tls_ca_cert: Optional[Path] = None
        self.acmqtti_broker_username: Optional[str] = None

        self.wgs84: Optional[tuple[wgs84.Coord, wgs84.Coord, wgs84.Coord]] = (
            None
        )
        self.map_width = 0.0
        self.map_height = 0.0

    def load(self, path: Path) -> None:
        try:
            with open(path, "r") as f:
                c = json.load(f)
                configuration: dict[str, Any] = c["configuration"]
                assert isinstance(configuration, dict)

                stored_modes = configuration.get("modes")
                assert isinstance(stored_modes, list)
                for mode in stored_modes:
                    assert isinstance(mode, str)
                    if mode not in [str(x) for x in self.modes]:
                        raise Exception(f"Unsupported mode: {mode}")
                self.modes = stored_modes

                stored_factors = configuration.get("factors")
                assert isinstance(stored_factors, list)
                for factor in stored_factors:
                    assert isinstance(factor, str)
                    if factor not in self.factors.keys():
                        raise Exception(f"Unsupported factor: {factor}")
                self.factors = dict(
                    [
                        (key, val)
                        for key, val in QUALITY_FACTORS.items()
                        if val.supported_for(self.modes)
                        and key in stored_factors
                    ]
                )

                locations: list[Location] = []
                stored_stations = c["stations"]
                assert isinstance(stored_stations, list)
                for station in stored_stations:
                    assert isinstance(station, dict)

                    bs_key = station.get("bs_key")
                    assert bs_key is None or isinstance(bs_key, str)

                    v = station.get("description")
                    assert v is None or isinstance(v, str)
                    description = v

                    x = station.get("x")
                    assert isinstance(x, int) or isinstance(x, float)
                    x = float(x)

                    y = station.get("y")
                    assert isinstance(y, int) or isinstance(y, float)
                    y = float(y)

                    location = Location(
                        bs_key=bs_key,
                        is_base_station=True,
                        position=(x, y),
                        description=description,
                    )
                    locations.append(location)

                stored_locations = c["locations"]
                assert isinstance(stored_locations, list)
                for location in stored_locations:
                    assert isinstance(location, dict)

                    results: list[Measurement] = []
                    stored_results = location.get("results")
                    assert isinstance(stored_results, list)
                    for result in stored_results:
                        assert isinstance(result, dict)

                        bs_key = result.get("bs_key")
                        assert isinstance(bs_key, str)

                        ep_key = result.get("ep_key")
                        assert isinstance(ep_key, str)

                        eq_snr = result.get("eq_snr")
                        assert isinstance(eq_snr, int) or isinstance(
                            eq_snr, float
                        )
                        eq_snr = float(eq_snr)

                        rssi = result.get("rssi")
                        assert isinstance(rssi, int) or isinstance(rssi, float)
                        rssi = float(rssi)

                        snr = result.get("snr")
                        assert (
                            snr is None
                            or isinstance(snr, int)
                            or isinstance(snr, float)
                        )
                        snr = float(snr) if snr is not None else None

                        sub = result.get("sub")
                        assert sub is None or isinstance(sub, dict)
                        if sub is not None:
                            rssis = sub.get("rssi")
                            assert isinstance(rssis, list)
                            for ent in rssis:
                                assert (
                                    ent is None
                                    or isinstance(ent, float)
                                    or isinstance(ent, int)
                                )

                            snrs = sub.get("snr")
                            assert isinstance(snrs, list)
                            for ent in snrs:
                                assert (
                                    ent is None
                                    or isinstance(ent, float)
                                    or isinstance(ent, int)
                                )

                            freqs = sub.get("freq")
                            assert isinstance(freqs, list)
                            for ent in freqs:
                                assert (
                                    ent is None
                                    or isinstance(ent, float)
                                    or isinstance(ent, int)
                                )

                            sub = SubMeasurement(
                                [
                                    float(e) if e is not None else None
                                    for e in rssis
                                ],
                                [
                                    float(e) if e is not None else None
                                    for e in snrs
                                ],
                                [
                                    float(e) if e is not None else None
                                    for e in freqs
                                ],
                            )

                        result = Measurement(
                            bs_key,
                            ep_key,
                            eq_snr,
                            rssi,
                            snr,
                            sub_measurement=sub,
                        )
                        results.append(result)

                    x = location.get("x")
                    assert isinstance(x, int) or isinstance(x, float)
                    x = float(x)

                    y = location.get("y")
                    assert isinstance(y, int) or isinstance(y, float)
                    y = float(y)

                    v = location.get("description")
                    assert v is None or isinstance(v, str)
                    description = v

                    location = Location(
                        is_base_station=False,
                        position=(x, y),
                        description=description,
                    )
                    location.measurements = results
                    locations.append(location)

                self.locations = locations

                wgs84_coords = configuration.get("wgs84")
                assert wgs84_coords is None or isinstance(wgs84_coords, list)
                if isinstance(wgs84_coords, list):
                    assert len(wgs84_coords) == 3
                    coord_idx = 0
                    for coord in wgs84_coords:
                        assert isinstance(coord, dict)
                        lat = coord.get("lat")
                        lon = coord.get("lon")
                        assert isinstance(lat, float) or isinstance(lat, int)
                        assert isinstance(lon, float) or isinstance(lon, int)
                        if coord_idx == 0:
                            wgs_bot_left = wgs84.Coord(lat, lon)
                        elif coord_idx == 1:
                            wgs_bot_right = wgs84.Coord(lat, lon)
                        elif coord_idx == 2:
                            wgs_top_left = wgs84.Coord(lat, lon)
                        else:
                            raise Exception("Too many WGS84 coordinates.")
                        coord_idx += 1
                    self.wgs84 = (wgs_bot_left, wgs_bot_right, wgs_top_left)

                v = configuration.get("colormap")
                assert v is None or isinstance(v, str)
                if isinstance(v, str):
                    self.colormap = v

                v = configuration.get("contours")
                assert v is None or isinstance(v, int)
                if isinstance(v, int):
                    self.contours = v

                v = configuration.get("dpi")
                assert v is None or isinstance(v, int)
                if isinstance(v, int):
                    self.dpi = v

                v = configuration.get("extrapolate")
                assert v is None or isinstance(v, bool)
                if isinstance(v, bool):
                    self.extrapolate = v

                v = configuration.get("file_format")
                assert v is None or isinstance(v, str)
                if isinstance(v, str):
                    self.file_format = v

                v = configuration.get("map_path")
                assert isinstance(v, str)
                self.map_path = Path(v)

                v = configuration.get("sub_measurements")
                assert v is None or isinstance(v, bool)
                if v is not None:
                    self.sub_measurements = v

                v = configuration.get("acmqtti_ac_eui")
                assert v is None or isinstance(v, str)
                self.acmqtti_ac_eui = v

                v = configuration.get("acmqtti_ep_euis")
                assert v is None or isinstance(v, list)
                if v is not None:
                    for eui in v:
                        assert isinstance(eui, str)
                self.acmqtti_ep_euis = v

                v = configuration.get("acmqtti_broker")
                assert v is None or isinstance(v, str)
                self.acmqtti_broker = v

                v = configuration.get("acmqtti_broker_tls_ca_cert")
                assert v is None or isinstance(v, str)
                if v is not None:
                    v = Path(v)
                self.acmqtti_broker_tls_ca_cert = v

                v = configuration.get("acmqtti_broker_username")
                assert v is None or isinstance(v, str)
                self.acmqtti_broker_username = v

        except AssertionError as msg:
            print("Invalid value in config:", msg)
            _, _, tb = sys.exc_info()
            traceback.print_tb(tb)  # Fixed format
            exit(1)
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            print("Error loading config:", e)
            if exc_tb is not None:
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(exc_type, fname, exc_tb.tb_lineno)
            exit(1)

    def save(self, path: Path) -> None:
        """
        Saves the current config and locations (with results) at the given path.
        """

        configuration = {
            "colormap": self.colormap,
            "contours": self.contours,
            "dpi": self.dpi,
            "extrapolate": self.extrapolate,
            "factors": [x for x in self.factors.keys()],
            "file_format": self.file_format,
            "modes": [str(x) for x in self.modes],
            "map_path": str(self.map_path),
            "sub_measurements": self.sub_measurements,
        }
        if self.acmqtti_ac_eui is not None:
            configuration["acmqtti_ac_eui"] = self.acmqtti_ac_eui
        if self.acmqtti_ep_euis is not None:
            configuration["acmqtti_ep_euis"] = self.acmqtti_ep_euis
        if self.acmqtti_broker is not None:
            configuration["acmqtti_broker"] = self.acmqtti_broker
        if self.acmqtti_broker_tls_ca_cert is not None:
            configuration["acmqtti_broker_tls_ca_cert"] = str(
                self.acmqtti_broker_tls_ca_cert
            )
        if self.acmqtti_broker_username is not None:
            configuration["acmqtti_broker_username"] = (
                self.acmqtti_broker_username
            )
        if self.wgs84 is not None:
            configuration["wgs84"] = [
                {"lat": self.wgs84[0].lat(), "lon": self.wgs84[0].lon()},
                {"lat": self.wgs84[1].lat(), "lon": self.wgs84[1].lon()},
                {"lat": self.wgs84[2].lat(), "lon": self.wgs84[2].lon()},
            ]

        locations = [
            {
                "x": loc.position[0],
                "y": loc.position[1],
                "results": [
                    {
                        "bs_key": m.bs_key,
                        "ep_key": m.ep_key,
                        "eq_snr": (
                            round(m.eq_snr, 1) if m.eq_snr is not None else None
                        ),
                        "rssi": (
                            round(m.rssi, 1) if m.rssi is not None else None
                        ),
                        "snr": (round(m.snr, 1) if m.snr is not None else None),
                        "sub": (
                            {
                                "rssi": [
                                    round(e, 1) if e is not None else None
                                    for e in m.sub_measurement.rssi
                                ],
                                "snr": [
                                    round(e, 1) if e is not None else None
                                    for e in m.sub_measurement.snr
                                ],
                                "freq": [
                                    round(e, 3) if e is not None else None
                                    for e in m.sub_measurement.freq
                                ],
                            }
                            if m.sub_measurement is not None
                            else None
                        ),
                    }
                    for m in loc.measurements
                ],
            }
            for loc in self.locations
            if not loc.is_base_station
        ]
        stations = [
            {
                "bs_key": loc.bs_key,
                "description": loc.description,
                "x": loc.position[0],
                "y": loc.position[1],
            }
            for loc in self.locations
            if loc.is_base_station
        ]

        config = {
            "configuration": configuration,
            "locations": locations,
            "stations": stations,
        }
        with open(path, "w") as f:
            st = json.dumps(config, indent=2)
            matches: list[str] = []
            matches.extend(
                re.findall(
                    r"\"rssi\": \[(?:\n(?:\s*)-?[0-9.]+[,\n])+\s*\]",
                    st,
                )
            )
            matches.extend(
                re.findall(
                    r"\"snr\": \[(?:\n(?:\s*)-?[0-9.]+[,\n])+\s*\]",
                    st,
                )
            )
            matches.extend(
                re.findall(
                    r"\"freq\": \[(?:\n(?:\s*)-?[0-9.]+[,\n])+\s*\]",
                    st,
                )
            )
            for match in matches:
                st = st.replace(match, match.replace(" ", "").replace("\n", ""))
            f.write(st)
            print(f"Configuration saved at: {path}")

    def validate_or_exit(self) -> None:
        """
        Checks the current config for consistency, and if inconsistencies are
        found, exits the application.
        """

        if not self.map_path.exists():
            print(f"Map file does not exist: {self.map_path}")
            exit(1)

        if (
            self.acmqtti_broker is not None
            and self.acmqtti_broker != ""
            and Mode.ACMQTTI not in self.modes
        ):
            print("MQTT Broker must be set when running ACMQTTI mode.")
            exit(1)

        if self.acmqtti_broker is not None:
            broker = self.acmqtti_broker.split(":")
            if len(broker) != 2:
                print("MQTT Broker must be configured as host:port.")
                exit(1)

            try:
                int(broker[1])
            except Exception as _e:
                print("MQTT Broker must be configured as host:port.")
                exit(1)

            if (
                self.acmqtti_broker_tls_ca_cert is not None
                and not self.acmqtti_broker_tls_ca_cert.exists()
            ):
                print(
                    f"MQTT Broker TLS CA Cert does not exist: {self.acmqtti_broker_tls_ca_cert}"
                )
                exit(1)

        if self.file_format not in SUPPORTED_EXPORT_FILE_FORMATS:
            formats = ", ".join(SUPPORTED_EXPORT_FILE_FORMATS)
            print(f"Invalid export file format. Supported formats: {formats}")
            exit(1)


def init_config(config_path: Path) -> None:
    """
    Initializes a default config file for the application.
    """
    config = State()
    print(f"Supported test modes: {', '.join(map(str, config.modes))}")
    print(f"Supported quality factors: {', '.join(config.factors.keys())}")
    config.save(config_path)


def load_config(config_path: Path) -> State:
    """
    Loads a config file from the given location.
    """
    config = State()
    config.load(config_path)
    return config
