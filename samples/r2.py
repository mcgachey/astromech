from __future__ import annotations

import asyncio

from astromech import R2_Unit, Personality

async def test_r2():
  async with R2_Unit(
    "F7:E6:74:95:E5:53", 
    personality=Personality('navy_blue')
  ) as droid:
    beep = droid.personality.sounds[2]
    await asyncio.gather(
      droid.play(beep, wait=True),
      droid.move_forward(beep.ms)
    )

    beep = droid.personality.sounds[7]
    await asyncio.gather(
      droid.play(droid.personality.sounds[15], wait=True),
      droid.look_around()
    )

    beep = droid.personality.sounds[7]
    await asyncio.gather(
      droid.play(beep, wait=True),
      droid.spin_clockwise(speed=0xff, duration_ms=beep.ms),
    )

    beep = droid.personality.sounds[14]
    await asyncio.gather(
      droid.play(beep),
      droid.move_backward(beep.ms)
    )

if __name__ == '__main__':
  asyncio.run(test_r2())
