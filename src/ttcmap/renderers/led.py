"""Pack map state using the selected board mapping.

LED i uses byte i // 8, bit i % 8 (LSB-first). See docs/FIRMWARE_API.md.
"""

import hashlib
import json

from ttcmap.config import get_settings
from ttcmap.map.state import MapState
from ttcmap.map.topology import safe_json_path


def load_led_map(name: str) -> dict | None:
    path = safe_json_path(get_settings().led_maps_path, name, "LED map")
    if not path.exists():
        return None
    return json.loads(path.read_text())


def pack_bits(on: list[int], led_count: int) -> bytes:
    packed = bytearray((led_count + 7) // 8)
    for index in on:
        packed[index // 8] |= 1 << (index % 8)
    return bytes(packed)


def render_led_state(state: MapState, led_map: dict) -> dict:
    on = [led["index"] for led in led_map["leds"] if state.stationsWithTrains.get(led["station"])]
    packed = pack_bits(on, led_map["ledCount"])

    return {
        "generatedAt": state.generatedAt,
        "source": state.source,
        "map": led_map["name"],
        "ledCount": led_map["ledCount"],
        "on": on,
        "bits": packed.hex(),
        "_packed": packed,
    }


def etag_for(packed: bytes, led_map_name: str) -> str:
    """Content-addressed so the ESP32 can skip frames that did not change."""
    digest = hashlib.sha256(led_map_name.encode() + b"\x00" + packed).hexdigest()[:16]
    return f'"{digest}"'
