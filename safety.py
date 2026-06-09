# safety.py
import signal
import logging

log = logging.getLogger(__name__)


class SafetyWatchdog:
    def __init__(self, drone):
        self.drone = drone

    def start(self):
        # Ctrl+C triggers immediate land
        signal.signal(signal.SIGINT, self._handle_sigint)
        log.info("🛡  Watchdog active — Ctrl+C = land immediately")

    def _handle_sigint(self, signum, frame):
        print("\n🚨 Ctrl+C pressed — landing now!")
        try:
            self.drone.land()
        except Exception:
            try:
                self.drone.emergency()
            except Exception as e:
                log.error(f"Emergency stop failed: {e}")
        raise SystemExit(0)

    def check(self):
        pass  # no abort event needed anymore — SIGINT handles it