from __future__ import annotations

import asyncio
import sys

from astromech import R2_Unit, Personality

R2T2 = "F7:E6:74:95:E5:53"

async def beep(beep_number: int):
  async with R2_Unit(R2T2, Personality('navy_blue')) as droid:
    await droid.play(droid.personality.sounds[beep_number])

if __name__ == '__main__':
  asyncio.run(beep(int(sys.argv[1])))
