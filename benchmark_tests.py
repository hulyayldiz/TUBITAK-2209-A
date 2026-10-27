"""Compatibility entrypoint for reproducible, shared-code validation."""
from validation import evaluate_synthetic, main


def run_benchmark(scenario="normal", model_type="hybrid", duration_steps=1200, seed=42):
    result = evaluate_synthetic(seed, scenario, duration_steps)
    metrics = result["layers"][model_type]
    hits = [value for value in metrics["episode_ttd_s"] if value is not None]
    return (None if metrics["recall"] is None else metrics["recall"] * 100,
            None if metrics["false_alarm_rate"] is None else metrics["false_alarm_rate"] * 100,
            sum(hits)/len(hits) if hits else None)


if __name__ == "__main__":
    main()
