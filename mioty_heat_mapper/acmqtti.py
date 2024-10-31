import datetime
import json
import paho.mqtt.client as mqtt

from paho.mqtt.reasoncodes import ReasonCode
from paho.mqtt.enums import CallbackAPIVersion
from pathlib import Path
from typing import Any, Callable, Optional

from mioty_heat_mapper import wgs84
from mioty_heat_mapper.measurement import Measurement, SubMeasurement
from mioty_heat_mapper.misc import with_exception_trace


class AcmqttiConfig:
    def __init__(
        self,
        broker_addr: str,
        broker_port: int,
        sub_measurements: bool = False,
        ac_eui: Optional[str] = None,
        ep_euis: Optional[list[str]] = None,
        password: Optional[str] = None,
        tls_ca_cert: Optional[Path] = None,
        wgs84: Optional[wgs84.World] = None,
        username: Optional[str] = None,
    ) -> None:
        self.ac_eui = ac_eui if ac_eui is not None else "+"
        self.broker_addr = broker_addr
        self.broker_port = broker_port
        self.ep_euis = ep_euis if ep_euis is not None else ["+"]
        self.password = password
        self.sub_measurements = sub_measurements
        self.tls_ca_cert = tls_ca_cert
        self.wgs84 = wgs84
        self.username = username


def build_locadis_supply_rss_data_request(m: Measurement) -> dict[str, Any]:
    rss = [
        {
            "id": m.bs_key,
            "channelType": "MIOTY",
            "rssValue": m.rssi,
            "snrValue": m.snr,
            "frequency": None,
        }
    ]
    if m.sub_measurement is not None:
        subs = zip(
            m.sub_measurement.rssi,
            m.sub_measurement.snr,
            m.sub_measurement.freq,
        )
        rss.extend(
            [
                {
                    "id": f"{m.bs_key}_sub_{idx}",
                    "channelType": "MIOTY",
                    "rssValue": ms[0],
                    "snrValue": ms[1],
                    "frequency": ms[2],
                }
                for idx, ms in enumerate(subs)
                if ms[0] is not None and ms[1] is not None
            ]
        )
    return {
        "method": "supplyRssData",
        "params": [
            {"nodeUUID": "ffb0fc73-a71f-4606-a439-dcbec3b76576"},
            {"rss": rss},
            {"timestamp": 0},
        ],
    }


def build_locadis_train_request(lat: float, lon: float) -> dict[str, Any]:
    return {
        "methods": "train",
        "params": [
            {
                "PositionWGS84": {
                    "latitude": lat,
                    "longitude": lon,
                    "northing": "N",
                    "easting": "E",
                    "heightOverGround": 0.0,
                    "geoid": "WGS84",
                    "valid": True,
                    "timestamp": int(
                        datetime.datetime.now(datetime.timezone.utc).timestamp()
                        * 1000
                    ),
                }
            }
        ],
    }


def measure(
    config: AcmqttiConfig,
    record: Callable[[Measurement], None],
    lat_lon: Optional[tuple[float, float]],
) -> mqtt.Client:
    topics = [
        f"mioty/{config.ac_eui}/version",
        "locadis/api_res",
    ]

    for ep_eui in config.ep_euis:
        topics.append(f"mioty/{config.ac_eui}/v1/{ep_eui}/uplink")
        topics.append(f"mioty/{config.ac_eui}/v1/{ep_eui}/uplinkDuplicate")

    def on_connect(
        client: mqtt.Client, _2: Any, _3: Any, _4: Any, _5: Any
    ) -> None:
        print(f"--- connected to broker; subscribing to {', '.join(topics)}")
        for topic in topics:
            client.subscribe(topic)

        if lat_lon is not None:
            print("Issuing Locadis 'train' command...")
            train_request = build_locadis_train_request(lat_lon[0], lat_lon[1])
            client.publish("locadis/api_req", json.dumps(train_request))

    def on_disconnect(
        client: mqtt.Client, _2: Any, _3: Any, reason_code: ReasonCode, _5: Any
    ) -> None:
        # if 0<=reason_code <= 5:
        #     reason = DISCONNECT_CODE[reason_code]
        # else:
        #     reason = "Currently unused"
        print(f"--- disconnected from broker; reason: {reason_code}")

    def on_message(
        client: mqtt.Client, _2: Any, message: mqtt.MQTTMessage
    ) -> None:
        dt = datetime.datetime.now().isoformat(" ", "seconds")

        # Handle messages from locadis.
        if message.topic == "locadis/api_res":
            p = json.loads(message.payload)
            print(f"[{dt}] Locadis response: {p}")
            return

        topic = message.topic.split("/")
        ac_eui = topic[1]
        version = topic[2]
        if version == "version":
            print(f"[{dt}] AC connected with EUI {ac_eui}")
            return

        if message.retain:
            print(f"[{dt}] ignoring retained message")
            return

        ep_eui = topic[3]
        command = topic[4]
        p = json.loads(message.payload)

        if command in ["uplink", "uplinkDuplicate"]:
            cnt = p["packetCnt"]
            print(f"[{dt}] uplink from {ep_eui}, packet {cnt}")
            for ul_meta in p["baseStations"]:
                bs_key = str(ul_meta["bsEui"])
                eq_snr = (
                    float(ul_meta["eqSnr"])
                    if ul_meta["eqSnr"] is not None
                    else None
                )
                rssi = (
                    float(ul_meta["rssi"])
                    if ul_meta["rssi"] is not None
                    else None
                )
                snr = (
                    float(ul_meta["snr"])
                    if ul_meta["snr"] is not None
                    else None
                )
                sub = (
                    ul_meta["subpackets"]
                    if ul_meta["subpackets"] is not None
                    and config.sub_measurements
                    else None
                )
                if sub is not None:
                    assert isinstance(sub, dict)
                    rssis = sub.get("rssi")
                    assert isinstance(rssis, list)
                    snrs = sub.get("snr")
                    assert isinstance(snrs, list)
                    freqs = sub.get("frequency")
                    assert isinstance(freqs, list)
                    sub = SubMeasurement(rssis, snrs, freqs)

                record(
                    Measurement(
                        bs_key, ep_eui, eq_snr, rssi, snr, sub_measurement=sub
                    )
                )

    mqtt_client = mqtt.Client(CallbackAPIVersion.VERSION2)
    if config.username is not None and config.password is not None:
        mqtt_client.username_pw_set(config.username, config.password)
    if config.tls_ca_cert is not None:
        mqtt_client.tls_set(str(config.tls_ca_cert))

    # We use `with_exception_trace` to ensure that exceptions in the handlers
    # are printed to the console. Without this, exceptions would not produce any
    # output.
    mqtt_client.on_connect = with_exception_trace(on_connect)
    mqtt_client.on_disconnect = with_exception_trace(on_disconnect)
    mqtt_client.on_message = with_exception_trace(on_message)
    mqtt_client.loop_start()
    mqtt_client.connect(config.broker_addr, config.broker_port)

    return mqtt_client
