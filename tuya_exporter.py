#!/usr/bin/env python3
import os
import time
import logging
from typing import List

import click
import tinytuya
import attr

from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

log = logging.getLogger(__name__)
consoleHandler = logging.StreamHandler()
log.setLevel(logging.WARNING)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
consoleHandler.setFormatter(formatter)
log.addHandler(consoleHandler)

tinytuya.log.setLevel(logging.WARNING)
tinytuya.log.addHandler(consoleHandler)


@attr.s(auto_attribs=True)
class DeviceConfig:
    name: str
    ip: str
    device_id: str
    local_key: str

    @classmethod
    def parse(cls) -> "DeviceConfig":
        device_local_key_file = "DEVICE_LOCAL_KEY_FILE"
        if device_local_key_file in os.environ:
            local_key_file = open(os.environ[device_local_key_file])
            local_key = local_key_file.read()
            local_key_file.close()
        else:
            local_key = os.environ["DEVICE_LOCAL_KEY"]

        return cls(
            name=os.environ["DEVICE_LABEL"],
            ip=os.environ["DEVICE_IP"],
            device_id=os.environ["DEVICE_ID"],
            local_key=local_key,
        )


class Collector:
    def __init__(self, configs: List[DeviceConfig]):
        self.configs = configs

    def collect(self):
        current_gauge = GaugeMetricFamily(
            "tuya_current_amps", "Current in amps.", labels=["name"], unit='amps'
        )
        power_gauge = GaugeMetricFamily(
            "tuya_power_watts", "Power in watts.", labels=["name"], unit='watts'
        )
        voltage_gauge = GaugeMetricFamily(
            "tuya_voltage_volts", "Voltage in volts.", labels=["name"], unit='volts'
        )
        for config in self.configs:
            log.info('device config: %r', config)
            device = tinytuya.OutletDevice(config.device_id, config.ip, config.local_key)

            device.set_version(3.4)
            device.set_socketTimeout(2)
            device.updatedps([18, 19, 20])

            data = device.status()

            log.debug('data: %r', data)

            if not data.get("Error"):
                current_gauge.add_metric([config.name], float(data.get("dps", {}).get("18", 0)) / 1000.0)
                power_gauge.add_metric([config.name], float(data.get("dps", {}).get("19", 0)) / 10.0)
                voltage_gauge.add_metric([config.name], float(data.get("dps", {}).get("20", 0)) / 10.0)
            else:
                log.error("Failed to get device status: %s", data.get("Error"))
        yield current_gauge
        yield power_gauge
        yield voltage_gauge


@click.command()
@click.option("--port", help="Port to run the Prometheus exporter on.", default=9185)
def main(port):
    device_configs = [DeviceConfig.parse()]
    collector = Collector(device_configs)

    REGISTRY.register(collector)

    start_http_server(port)

    while True:
        time.sleep(0.1)


if __name__ == "__main__":
    main()
