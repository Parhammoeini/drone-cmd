# metrics.py
import time
import json
from datetime import datetime

class Metrics:
    def __init__(self):
        self.session_start = time.time()
        self.records = []

    def record(self, goal, commands, llm_time, exec_time, success):
        self.records.append({
            "timestamp": datetime.now().isoformat(),
            "goal": goal,
            "commands": commands,
            "llm_latency_ms": round(llm_time * 1000, 2),
            "execution_time_ms": round(exec_time * 1000, 2),
            "total_ms": round((llm_time + exec_time) * 1000, 2),
            "success": success,
            "num_commands": len(commands)
        })

    def summary(self):
        if not self.records:
            print("No data recorded.")
            return
        
        llm_times = [r["llm_latency_ms"] for r in self.records]
        exec_times = [r["execution_time_ms"] for r in self.records]
        total_times = [r["total_ms"] for r in self.records]
        successes = [r["success"] for r in self.records]

        print("\n" + "="*50)
        print("📊 PERFORMANCE SUMMARY")
        print("="*50)
        print(f"Total commands issued : {len(self.records)}")
        print(f"Success rate          : {sum(successes)}/{len(successes)} ({round(sum(successes)/len(successes)*100)}%)")
        print(f"Avg LLM latency       : {round(sum(llm_times)/len(llm_times))}ms")
        print(f"Min/Max LLM latency   : {min(llm_times)}ms / {max(llm_times)}ms")
        print(f"Avg execution time    : {round(sum(exec_times)/len(exec_times))}ms")
        print(f"Avg total latency     : {round(sum(total_times)/len(total_times))}ms")
        print(f"Session duration      : {round(time.time() - self.session_start)}s")
        print("="*50)

    def save(self, filename=None):
        if filename is None:
            filename = f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w") as f:
            json.dump({
                "summary": {
                    "session_start": datetime.fromtimestamp(self.session_start).isoformat(),
                    "total_goals": len(self.records),
                },
                "records": self.records
            }, f, indent=2)
        print(f"💾 Metrics saved to {filename}")