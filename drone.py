import time
import logging
from djitellopy import Tello

log = logging.getLogger(__name__)


class DroneController:
    def __init__(self):
        self.tello = Tello()
        self.is_flying = False

    def connect(self):
        self.tello.connect()
        log.info(f"✅ Connected. Battery: {self.tello.get_battery()}%")

    def get_telemetry(self) -> dict:
        return {
            "battery": self.tello.get_battery(),
            "height":  self.tello.get_height(),
            "pitch":   self.tello.get_pitch(),
            "roll":    self.tello.get_roll(),
            "yaw":     self.tello.get_yaw(),
        }

    def takeoff(self):
        self.tello.takeoff()
        self.is_flying = True

    def land(self):
        self.tello.land()
        self.is_flying = False

    def emergency(self):
        self.tello.emergency()
        self.is_flying = False

    def move(self, direction: str, cm: int):
        assert direction in ("forward", "back", "left", "right", "up", "down")
        assert 20 <= cm <= 500
        getattr(self.tello, f"move_{direction}")(cm)

    def rotate(self, direction: str, degrees: int):
        assert direction in ("cw", "ccw")
        assert 1 <= degrees <= 360
        if direction == "cw":
            self.tello.rotate_clockwise(degrees)
        else:
            self.tello.rotate_counter_clockwise(degrees)

    def flip(self, direction: str):
        assert direction in ("l", "r", "f", "b")
        self.tello.flip(direction)

    def hover(self, seconds: float):
        time.sleep(seconds)
