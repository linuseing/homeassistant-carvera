from typing import TypedDict


class Config(TypedDict):
    carvera_ip: str
    carvera_port: int
    reconnect_delay: float
    homeassistant_ip: str
    proxy_port: int
    advertisement_interval: int
    name: str
