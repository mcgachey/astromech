from __future__ import annotations

import asyncio
import enum
from pathlib import Path
from typing import cast, List, Optional
import yaml
from bleak import BleakScanner, BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic

class Personality(object):
  def __init__(self, name: str):
    with open(Path(__file__).parent / 'config' / 'personalities' / f"{name}.yml") as f:
      config = yaml.safe_load(f)
    self.sounds = [Sound(x['group'], x['sound'], x['ms']) for x in config['sounds']]

class Sound(object):
  def __init__(self, group: int, sound: int, ms: int):
    self.group = group
    self.sound = sound
    self.ms = ms

class DiscoveredDevice(object):
  def __init__(self, mac_address: str, name: str):
    self.mac_address = mac_address
    self.name = name

  def __str__(self):
    return f"{self.name}: {self.mac_address}"

async def scan(bt_names: Optional[List[str]] = None) -> List[DiscoveredDevice]:
  devices: List[DiscoveredDevice] = []
  names = bt_names if bt_names else ['DROID']
  for d in await BleakScanner.discover():
    if d.name in names:
      print(f"Found droid {d.name}: {d.details}")
      devices.append(DiscoveredDevice(mac_address=d.details['props']['Address'], name=d.name))
  return devices

class Direction(enum.Enum):
  LEFT = 0x00
  RIGHT = 0x80
  FORWARD = 0x00
  BACKWARD = 0x80

class Motor(enum.Enum):
  LEFT = 0x00
  RIGHT = 0x01
  HEAD = 0x02

class Astromech(object):
  def __init__(
      self, 
      droid_type: str,
      mac_address: str, 
      personality: Personality
    ):
    with open(Path(__file__).parent / 'config' / 'droids' / f"{droid_type}.yml") as f:
      config = yaml.safe_load(f)
    self._wheel_ramp_time = config['wheels']['motor_ramp_time']
    self._wheel_speed = config['wheels']['speed']
    self._head_ramp_time = config['head']['motor_ramp_time']
    self._head_speed = config['head']['speed']
    self.mac_address = mac_address
    self.personality = personality
    self._client: BleakClient
    self._notification_listeners = []

  async def __aenter__(self) -> Astromech:
    self._client = BleakClient(self.mac_address)
    await self._client.connect()
    await self._client.start_notify(
      self._client.services.characteristics[10], 
      self._notification_callback
    )
    await self._execute(bytearray([0x22, 0x20, 0x01]))
    await self._execute(bytearray([0x22, 0x20, 0x01]))
    return self

  async def __aexit__(self, exception_type, exception_value, exception_traceback):
    if self._client and self._client.is_connected:
      await self._client.disconnect()

  def _notification_callback(self, sender: BleakGATTCharacteristic, data: bytearray):
    for c in self._notification_listeners:
      c(data)

  def listen_for_notifications(self, callback):
    self._notification_listeners.append(callback)

  async def set_audio_group(self, group_id: int):
    return await self._execute(self._audio_command(0x1f, group_id))

  async def play_sound_from_current_group(self, sound_id: int):
    return await self._execute(self._audio_command(0x18, sound_id))

  async def play(self, sound: Sound, wait: bool = False):
    await self.set_audio_group(sound.group)
    await self.play_sound_from_current_group(sound.sound)
    if wait:
      await asyncio.sleep(float(sound.ms) / 1000.0)

  async def _move_wheels(
      self, 
      left_direction: Direction, 
      right_direction: Direction,
      duration_ms: int,
      left_speed: Optional[int], 
      right_speed: Optional[int],
      ramp_time: Optional[int],
    ):
    print(f"Left speed: {left_speed}, right speed: {right_speed}")
    await self._execute(self._motor_command(left_direction, Motor.LEFT, left_speed, ramp_time))
    await self._execute(self._motor_command(right_direction, Motor.RIGHT, right_speed, ramp_time))
    await self.stop(delay_ms=duration_ms)

  async def stop(self, delay_ms: int = 0):
    await asyncio.sleep(delay_ms / 1000)
    await self._execute(self._motor_command(Direction.FORWARD, Motor.LEFT, 0))
    await self._execute(self._motor_command(Direction.FORWARD, Motor.RIGHT, 0))

  def _audio_command(self, cmd: int, param: Optional[int] = None):
    command_data = bytearray([0x44, 0x00, cmd])
    if param is not None:
      command_data.append(param)
    return self._command(0x0f, command_data)

  def _motor_command(
      self,
      direction: Direction, 
      motor: Motor, 
      speed: int | None = None, 
      ramp_time: int | None = None,
      delay_after: int = 0,
    ):
    speed_value = speed if speed is not None else self._head_speed if motor == Motor.HEAD else self._wheel_speed
    ramp_value = ramp_time if ramp_time is not None else self._head_ramp_time if motor == Motor.HEAD else self._wheel_ramp_time
    command_data = bytearray([direction.value | motor.value, speed_value])
    command_data += _int_to_bytes(ramp_value)
    command_data += _int_to_bytes(delay_after)
    return self._command(0x05, command_data)

  def _command(self, command_id: int, command_data: bytearray):
    data = bytearray()
    data.append(0x1f + 4 + len(command_data))
    data.append(0x42)
    data.append(command_id)
    data.append(0x40 + len(command_data))
    data += command_data  
    return data

  async def _execute(self, command: bytearray):
    print(f"Sending {_dump_bytes(command)}")
    response = await self._client.write_gatt_char(
      self._client.services.characteristics[13], command, 
      response=True,
    )
    if response:
      print(f"Response: {response}")
    return response

class R2_Unit(Astromech):
  def __init__(self, mac_address, personality):
    super().__init__('r2', mac_address, personality)

  async def __aenter__(self) -> R2_Unit:
    return cast(R2_Unit, await super().__aenter__())

  async def rotate_head(
      self, 
      direction: Direction, 
      speed: Optional[int] = None, 
      ramp_time: Optional[int] = None,
      delay_after: int = 0,
    ):
    return await self._execute(self._motor_command(direction, Motor.HEAD, speed, ramp_time, delay_after))

  async def center_head(
      self, 
      speed: Optional[int] = None, 
      stop_at_center: bool = True,
    ):
    speed_value = speed if speed is not None else self._head_speed
    return await self._execute(self._command(
      0x0f, 
      bytearray([0x44, 0x01, speed_value, 0x00 if stop_at_center else 0x01]))
    )

  async def look_around(self, speed: Optional[int] = None, stop_at_center: bool = True,):
    await self.rotate_head(Direction.LEFT, speed)
    await asyncio.sleep(1.5)
    await self.rotate_head(Direction.RIGHT, speed)
    await asyncio.sleep(1.5)
    if stop_at_center:
      await self.center_head(speed)

  async def move_forward(self, duration_ms: int, speed: Optional[int] = None, ramp_time: Optional[int] = None):
    await self._move_wheels(Direction.FORWARD, Direction.FORWARD, duration_ms, speed, speed, ramp_time)

  async def move_backward(self, duration_ms: int, speed: Optional[int] = None, ramp_time: Optional[int] = None):
    await self._move_wheels(Direction.BACKWARD, Direction.BACKWARD, duration_ms, speed, speed, ramp_time)

  async def spin_clockwise(self, duration_ms: int, speed: Optional[int] = None, ramp_time: Optional[int] = None):
    await self._move_wheels(Direction.FORWARD, Direction.BACKWARD, duration_ms, speed, speed, ramp_time)

  async def spin_counter_clockwise(self, duration_ms: int, speed: Optional[int] = None, ramp_time: Optional[int] = None):
    await self._move_wheels(Direction.BACKWARD, Direction.FORWARD, duration_ms, speed, speed, ramp_time)

  async def turn_clockwise(self, duration_ms: int, speed: Optional[int] = None, ramp_time: Optional[int] = None):
    await self._move_wheels(Direction.FORWARD, Direction.FORWARD, duration_ms, speed, 0, ramp_time)

  async def turn_counter_clockwise(self, duration_ms: int, speed: Optional[int] = None, ramp_time: Optional[int] = None):
    await self._move_wheels(Direction.FORWARD, Direction.FORWARD, duration_ms, 0, speed, ramp_time)

  async def drift_clockwise(self, duration_ms: int, speed: int = 0xa0, ramp_time: Optional[int] = None):
    await self._move_wheels(Direction.FORWARD, Direction.FORWARD, duration_ms, speed, int(float(speed)/2.0), ramp_time)

  async def drift_counter_clockwise(self, duration_ms: int, speed: int = 0xa0, ramp_time: Optional[int] = None):
    await self._move_wheels(Direction.FORWARD, Direction.FORWARD, duration_ms, int(float(speed)/2.0), speed, ramp_time)

class BB_Unit(Astromech):
  def __init__(self, mac_address, personality):
    super().__init__('bb', mac_address, personality)

  async def __aenter__(self) -> BB_Unit:
    return cast(BB_Unit, await super().__aenter__())

  async def move_forward(self, duration_ms: int, speed: Optional[int] = None, ramp_time: Optional[int] = None):
    await self._move_wheels(Direction.FORWARD, Direction.FORWARD, duration_ms, speed, speed, ramp_time)

  async def move_backward(self, duration_ms: int, speed: Optional[int] = None, ramp_time: Optional[int] = None):
    await self._move_wheels(Direction.BACKWARD, Direction.BACKWARD, duration_ms, speed, speed, ramp_time)

  async def turn_head_clockwise(self, duration_ms: int, speed: Optional[int] = None, ramp_time: Optional[int] = None):
    speed_value = speed if speed is not None else self._head_speed
    ramp_value = ramp_time if ramp_time is not None else self._head_ramp_time
    await self._move_wheels(Direction.FORWARD, Direction.BACKWARD, duration_ms, speed_value, speed_value, ramp_value)

  async def turn_head_counter_clockwise(self, duration_ms: int, speed: Optional[int] = None, ramp_time: Optional[int] = None):
    speed_value = speed if speed is not None else self._head_speed
    ramp_value = ramp_time if ramp_time is not None else self._head_ramp_time
    await self._move_wheels(Direction.BACKWARD, Direction.FORWARD, duration_ms, speed_value, speed_value, ramp_value)

def _dump_bytes(data: bytearray):
  return data.hex(bytes_per_sep=1, sep=' ')

def _int_to_bytes(i: int):
  return i.to_bytes(2, 'big')
