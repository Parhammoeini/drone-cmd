# main.py
import json
import time
import logging

from drone import DroneController
from llm import plan_next_commands
from metrics import Metrics  # <-- Imported your standalone metrics module

# ── Logging Configuration (Redirected to keep console clear) ────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("drone.log", mode="w", encoding="utf-8"),
        logging.StreamHandler()  # Keeps terminal inputs clean from overlapping loops
    ]
)
log = logging.getLogger(__name__)
logging.getLogger("djitellopy").setLevel(logging.WARNING)


# ── Command executor ─────────────────────────────────────────────────────────

MOVE_SETTLE_TIME = 2.0

def execute_command(drone: DroneController, cmd: dict) -> bool:
    c = cmd.get("cmd")
    log.info(f"▶  {cmd}")
    t_start = time.perf_counter()

    if   c == "hover":   drone.hover(cmd.get("seconds", 1))
    elif c == "move":
        drone.move(cmd["direction"], cmd["cm"])
        time.sleep(MOVE_SETTLE_TIME)
    elif c == "rotate":
        drone.rotate(cmd["direction"], cmd["degrees"])
        time.sleep(MOVE_SETTLE_TIME)
    elif c == "flip":    drone.flip(cmd["direction"])
    else:
        log.warning(f"Unknown command ignored: {c}")

    exec_ms = (time.perf_counter() - t_start) * 1000
    log.info(f"   ✅ done in {exec_ms:.0f} ms")
    return True


# ── Interactive command loop ──────────────────────────────────────────────────

def interactive_loop(drone: DroneController):
    history = []
    cycle = 0
    
    # Initialize the metrics manager from metrics.py
    metrics_tracker = Metrics()

    print("─" * 50)
    print("  Type commands in plain English. Examples:")
    print("    move forward 1 meter")
    print("    go left 50cm")
    print("    land  (or 'quit')")
    print("  type 'stop' = emergency cut motors")
    print("─" * 50 + "\n")

    while True:
        try:
            user_input = input("🎮 > ").strip()
        except KeyboardInterrupt:
            print()
            print("  (use 'land' to land or 'stop' for emergency cutoff)")
            continue

        if not user_input:
            continue

        if user_input.lower() in ("land", "quit", "exit", "q"):
            print("🛬 Landing...")
            drone.land()
            break

        if user_input.lower() == "stop":
            print("🚨 Emergency stop — cutting motors!")
            drone.emergency()
            break

        cycle += 1

        try:
            telemetry = drone.get_telemetry()
            
            # --- Profile LLM Inference ---
            t0 = time.perf_counter()
            commands, _ = plan_next_commands(user_input, telemetry, history)
            t1 = time.perf_counter()
            
            history.append({"role": "user",      "content": user_input})
            history.append({"role": "assistant", "content": json.dumps({"commands": commands})})

            # --- Profile Drone Physical Movements ---
            t2 = time.perf_counter()
            execution_success = True
            for cmd in commands:
                try:
                    execute_command(drone, cmd)
                except Exception as exec_err:
                    log.error(f"Command execution failed: {exec_err}")
                    execution_success = False
            t3 = time.perf_counter()

            # Record session log entries
            metrics_tracker.record(
                goal=user_input,
                commands=commands,
                llm_time=(t1 - t0),
                exec_time=(t3 - t2),
                success=execution_success
            )

            time.sleep(0.3)

        except KeyboardInterrupt:
            print()
            print("  ⚠️  Interrupted mid-command (background signal). Drone still flying.")
            print("  (type 'land' to land, 'stop' for emergency cutoff)")
            continue

    # Clean display and file dumps upon landing complete
    metrics_tracker.summary()
    metrics_tracker.save()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    drone = DroneController()
    drone.connect()

    try:
        print("\n🚀 Taking off...")
        drone.takeoff()
        time.sleep(2)
        print("✅ Hovering. Ready for commands.\n")

        interactive_loop(drone)

    except KeyboardInterrupt:
        print("\n🛬 Ctrl+C during startup — landing.")
        try:
            drone.land()
        except Exception:
            pass
    except Exception as e:
        log.error(f"❌ {e}")
        try:
            drone.land()
        except Exception:
            pass
        raise