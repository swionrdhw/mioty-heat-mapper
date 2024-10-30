from typing import Optional


class SubMeasurement:
    """
    Represent a result with sub-measurement values, specifically mioty subpacket
    information (mioty burst information).
    """

    def __init__(
        self,
        rssi: list[float | None],
        snr: list[float | None],
        freq: list[float | None],
    ) -> None:
        self.rssi = rssi
        self.snr = snr
        self.freq = freq

    def get(self, factor_key: str) -> list[float | None]:
        if factor_key == "rssi":
            return self.rssi
        elif factor_key == "snr":
            return self.snr
        else:
            print(f"Unknown factor key: {factor_key}")
            exit(1)


class Measurement:
    """
    Represents a result with measurement values.
    """

    def __init__(
        self,
        bs_key: str,
        ep_key: str,
        eq_snr: Optional[float],
        rssi: Optional[float],
        snr: Optional[float],
        sub_measurement: Optional[SubMeasurement] = None,
    ) -> None:
        self.bs_key = bs_key
        self.ep_key = ep_key
        self.eq_snr = eq_snr
        self.rssi = rssi
        self.snr = snr
        self.sub_measurement = sub_measurement

    def get(self, factor_key: str) -> Optional[float]:
        if factor_key == "rssi":
            return self.rssi
        elif factor_key == "snr":
            return self.snr
        elif factor_key == "eq_snr":
            return self.eq_snr
        else:
            print(f"Unknown factor key: {factor_key}")
            exit(1)


class Location:
    """
    Represents a network quality measurement.
    """

    def __init__(
        self,
        is_base_station: bool = False,
        bs_key: Optional[str] = None,
        position: tuple[float, float] = (-1, -1),
        description: Optional[str] = None,
    ):
        self.gui_id: Optional[int] = None
        self.is_base_station = is_base_station
        self.bs_key = bs_key
        self.description = description
        self.position = position
        self.measurements: list[Measurement] = []
