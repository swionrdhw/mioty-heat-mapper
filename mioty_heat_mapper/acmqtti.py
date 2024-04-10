import datetime
import json
import paho.mqtt.client as mqtt

from paho.mqtt.reasoncodes import ReasonCode
from paho.mqtt.enums import CallbackAPIVersion
from pathlib import Path
from typing import Any, Callable, Optional

from mioty_heat_mapper.measurement import Measurement
from mioty_heat_mapper.misc import with_exception_trace


class AcmqttiConfig:
    def __init__(
        self,
        broker_addr: str, 
        broker_port: int, 
        ac_eui: Optional[str] = None, 
        ep_euis: Optional[list[str]] = None,
        password: Optional[str] = None,
        tls_ca_cert: Optional[Path] = None,
        username: Optional[str] = None,
    ) -> None:
        self.ac_eui = ac_eui if ac_eui is not None else "+"
        self.broker_addr = broker_addr
        self.broker_port = broker_port
        self.ep_euis = ep_euis if ep_euis is not None else ["+"]
        self.password = password
        self.tls_ca_cert = tls_ca_cert
        self.username = username

def measure(config: AcmqttiConfig, record: Callable[[Measurement], None]) -> mqtt.Client:
    topics = [f"mioty/{config.ac_eui}/version"]

    for ep_eui in config.ep_euis:
        topics.append(f"mioty/{config.ac_eui}/v1/{ep_eui}/uplink")
        topics.append(f"mioty/{config.ac_eui}/v1/{ep_eui}/uplinkDuplicate")

    def on_connect(client: mqtt.Client, _2: Any, _3: Any, _4: Any, _5: Any) -> None:
        print(f"--- connected to broker; subscribing to {', '.join(topics)}")
        for topic in topics:
            client.subscribe(topic)

    def on_disconnect(client: mqtt.Client, _2: Any, _3: Any, reason_code: ReasonCode, _5: Any) -> None:
        # if 0<=reason_code <= 5:
        #     reason = DISCONNECT_CODE[reason_code]
        # else:
        #     reason = "Currently unused"
        print(f"--- disconnected from broker; reason: {reason_code}")

    def on_message(client: mqtt.Client, _2: Any, message: mqtt.MQTTMessage) -> None:
        dt = datetime.datetime.now().isoformat(" ", "seconds")
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
            print(f"[{dt}] uplink from {ep_eui}, packetCnt = {p["packetCnt"]}")
            for ul_meta in p["baseStations"]:
                bs_key = str(ul_meta["bsEui"])
                eq_snr = float(ul_meta["eqSnr"]) if ul_meta["eqSnr"] is not None else None
                rssi = float(ul_meta["rssi"]) if ul_meta["rssi"] is not None else None
                snr = float(ul_meta["snr"]) if ul_meta["snr"] is not None else None
                record(Measurement(bs_key, ep_eui, eq_snr, rssi, snr))

    mqtt_client = mqtt.Client(CallbackAPIVersion.VERSION2)
    if config.username is not None and config.password is not None:
        mqtt_client.username_pw_set(config.username, config.password)
    if config.tls_ca_cert is not None:
        mqtt_client.tls_set(str(config.tls_ca_cert))
    
    # We use `with_exception_trace` to ensure that exceptions in the handlers are printed
    # to the console. Without this, exceptions would not produce any output.
    mqtt_client.on_connect = with_exception_trace(on_connect)
    mqtt_client.on_disconnect = with_exception_trace(on_disconnect)
    mqtt_client.on_message = with_exception_trace(on_message)
    mqtt_client.loop_start()
    mqtt_client.connect(config.broker_addr, config.broker_port)

    return mqtt_client
