from __future__ import annotations

import asyncio
import enum
from pathlib import Path
from typing import cast, List, Optional
import yaml
from bleak import BleakScanner, BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic

from astromech import BB_Unit, Personality, _dump_bytes

def _notification_callback(data: bytearray):
  print(f"Incoming Notification: {_dump_bytes(data)}")


async def test_bb():
  async with BB_Unit(
    'E6:1C:86:B3:BD:AE',
    personality=Personality('navy_blue')
  ) as droid:
    droid.listen_for_notifications(_notification_callback)

    await droid.set_audio_group(0)    
    await asyncio.gather(
      droid.turn_head_clockwise(duration_ms=2000),
      droid.play_sound_from_current_group(0),
    )

if __name__ == '__main__':
  asyncio.run(test_bb())
