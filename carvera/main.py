import asyncio
import json

import advertiser
import proxy
from carvera.config import Config


async def main():
    config = None
    try:
        with open("/data/options.json") as config_file:
            config: Config = json.load(config_file)
    except FileNotFoundError:
        config = {
            "carvera_ip": "192.168.2.138",
            "carvera_port": 2222,
            "reconnect_delay": 1,
            "homeassistant_ip": "192.168.2.148",
            "proxy_port": 2222,
            "advertisement_interval": 1,
            "name": "proxy"
        }
    advertising_task = asyncio.create_task(advertiser.broadcast_udp(config))
    cnc_proxy = proxy.CnCProxy(
        config["carvera_ip"],
        config["carvera_port"],
        config["proxy_port"],
        config["reconnect_delay"],
    )
    proxy_task = asyncio.create_task(cnc_proxy.start())
    await asyncio.gather(advertising_task, proxy_task)


if __name__ == "__main__":
    asyncio.run(main())
