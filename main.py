import json
import time
import logging
import signal

from drone import DroneController
from llm import plan_next_commands
from safety import SafetyWatchdog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


# ── Command executor ─────────────────────────────────────────────────────────

# Seconds to wait after each move/rotate so drone physically completes it
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


# ── Latency printer ──────────────────────────────────────────────────────────

def print_latency(cycle: int, lat: dict):
    print(f"\n{'─'*50}")
    print(f"  📊 Cycle {cycle} Latency")
    print(f"{'─'*50}")
    print(f"  LLM inference  : {lat['llm_ms']:>8.1f} ms")
    print(f"  JSON parse     : {lat['parse_ms']:>8.2f} ms")
    print(f"  Total          : {lat['total_ms']:>8.1f} ms")
    if lat.get("prompt_tokens"):
        print(f"  Prompt tokens  : {lat['prompt_tokens']}")
        print(f"  Completion tok : {lat['completion_tokens']}")
        print(f"  Tokens/sec     : {lat['tokens_per_sec']}")
    print(f"{'─'*50}\n")


def print_summary(latencies: list):
    if not latencies:
        return
    llm_times   = [l["llm_ms"]   for l in latencies]
    total_times = [l["total_ms"] for l in latencies]
    print(f"\n{'═'*50}")
    print(f"  📈 Session Summary ({len(latencies)} LLM calls)")
    print(f"{'═'*50}")
    print(f"  LLM avg  : {sum(llm_times)/len(llm_times):>8.1f} ms")
    print(f"  LLM min  : {min(llm_times):>8.1f} ms")
    print(f"  LLM max  : {max(llm_times):>8.1f} ms")
    print(f"  Total avg: {sum(total_times)/len(total_times):>8.1f} ms")
    print(f"{'═'*50}\n")


# ── Interactive command loop ──────────────────────────────────────────────────

def interactive_loop(drone: DroneController):
    history       = []
    all_latencies = []
    cycle         = 0

    print("─" * 50)
    print("  Type commands in plain English. Examples:")
    print("    move forward 1 meter")
    print("    go left 50cm")
    print("    make a 1 meter square")
    print("    flip forward")
    print("    rotate 180 degrees")
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

        # Wrap the entire command-processing block so that a spurious
        # KeyboardInterrupt from a djitellopy background thread doesn't
        # silently trigger a landing. User must type "land"/"stop" to exit.
        try:
            telemetry = drone.get_telemetry()
            log.info(f"🔋 Battery: {telemetry['battery']}%  Height: {telemetry['height']} cm")

            commands, latency = plan_next_commands(user_input, telemetry, history)
            latency["cycle"] = cycle
            all_latencies.append(latency)
            print_latency(cycle, latency)

            history.append({"role": "user",      "content": user_input})
            history.append({"role": "assistant", "content": json.dumps({"commands": commands})})

            for cmd in commands:
                execute_command(drone, cmd)

            time.sleep(0.3)

        except KeyboardInterrupt:
            # Background-thread signal fired during SDK/LLM work — ignore, don't land.
            print()
            print("  ⚠️  Interrupted mid-command (background signal). Drone still flying.")
            print("  (type 'land' to land, 'stop' for emergency cutoff)")
            continue

    print_summary(all_latencies)


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
        # Ctrl+C during takeoff only — the loop handles its own.
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