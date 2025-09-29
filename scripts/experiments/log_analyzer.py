from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

try:
	import pandas as pd
except Exception:
	pd = None

try:
	import matplotlib
	matplotlib.use("Agg")
	import matplotlib.pyplot as plt
except Exception as e:
	plt = None

PARAM_RE = re.compile(r"\b([A-Za-z]+):\s*([^,]+)(?:,|$)")
TIME_LINE_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*ms\s*$")
ENERGY_LINE_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*J\s*$")


@dataclass
class Measurement:
	experiment: str
	run_dir: str
	global_index: int
	iteration_index: int
	algorithm: str
	size: int
	threads: int
	power_cap_w: float
	sort_time_ms: float
	energy_j: float
	random_input_time_ms: float
	cumulative_sort_time_ms: float


def parse_parameters(path: Path) -> dict:
	text = path.read_text(encoding="utf-8", errors="ignore")
	params = {}
	for k, v in PARAM_RE.findall(text):
		key = k.strip()
		val = v.strip().rstrip("W")
		if key.lower() in {"size", "threads"}:
			try:
				params[key] = int(val)
			except ValueError:
				pass
		else:
			try:
				params[key] = float(val)
			except ValueError:
				params[key] = val
	norm = {
		"Algorithm": params.get("Algorithm"),
		"Size": int(params.get("Size", -1)),
		"Threads": int(params.get("Threads", -1)),
		"PowerCap": float(params.get("PowerCap", -1.0)),
	}
	return norm


def parse_numeric_lines(path: Path, pattern: re.Pattern) -> List[float]:
	if not path.exists():
		return []
	vals: List[float] = []
	for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
		if not line.strip():
			continue
		m = pattern.match(line)
		if m:
			try:
				vals.append(float(m.group(1)))
			except ValueError:
				pass
	return vals


def detect_algo_files(run_dir: Path) -> tuple[Optional[Path], Optional[Path]]:
	exec_file = energy_file = None
	for f in run_dir.iterdir():
		name = f.name
		if not f.is_file():
			continue
		if name.endswith("_execution_times.log") and not name.startswith("generateRandomInput"):
			exec_file = f
		elif name.endswith("_energy_j.log"):
			energy_file = f
	return exec_file, energy_file


def parse_run(run_dir: Path, experiment_name: str, start_index: int) -> List[Measurement]:
	params_path = run_dir / "parameters.log"
	if not params_path.exists():
		return []
	params = parse_parameters(params_path)
	exec_file, energy_file = detect_algo_files(run_dir)
	if exec_file is None or energy_file is None:
		return []
	algo = exec_file.name.rsplit("_execution_times.log", 1)[0]
	times_ms = parse_numeric_lines(exec_file, TIME_LINE_RE)
	energies_j = parse_numeric_lines(energy_file, ENERGY_LINE_RE)
	random_input_times = parse_numeric_lines(run_dir / "generateRandomInput_execution_times.log", TIME_LINE_RE)
	random_input_time_ms = random_input_times[0] if random_input_times else float("nan")
	n = min(len(times_ms), len(energies_j))
	out: List[Measurement] = []
	cumulative = 0.0
	for i in range(n):
		cumulative += times_ms[i]
		out.append(
			Measurement(
				experiment=experiment_name,
				run_dir=run_dir.name,
				global_index=start_index + i,
				iteration_index=i,
				algorithm=algo,
				size=params.get("Size", -1),
				threads=params.get("Threads", -1),
				power_cap_w=params.get("PowerCap", -1.0),
				sort_time_ms=times_ms[i],
				energy_j=energies_j[i],
				random_input_time_ms=random_input_time_ms,
				cumulative_sort_time_ms=cumulative,
			)
		)
	return out


def collect_experiment(exp_dir: Path) -> List[Measurement]:
	if not exp_dir.exists():
		raise FileNotFoundError(exp_dir)
	logs_dir_candidates = [d for d in (exp_dir / "logs").glob("*") if d.is_dir()]
	run_dirs = sorted(logs_dir_candidates, key=lambda p: p.name)
	measurements: List[Measurement] = []
	global_index = 0
	for rd in run_dirs:
		runs = parse_run(rd, exp_dir.name, global_index)
		measurements.extend(runs)
		global_index += len(runs)
	return measurements


def write_csv(data: List[Measurement], out_csv: Path) -> None:
	out_csv.parent.mkdir(parents=True, exist_ok=True)
	fieldnames = list(asdict(data[0]).keys()) if data else []
	with out_csv.open("w", newline="", encoding="utf-8") as f:
		writer = csv.DictWriter(f, fieldnames=fieldnames)
		writer.writeheader()
		for m in data:
			writer.writerow(asdict(m))


def write_parquet_if_possible(data: List[Measurement], out_parquet: Path) -> None:
	if pd is None or not data:
		return
	df = pd.DataFrame([asdict(m) for m in data])
	try:
		df.to_parquet(out_parquet, index=False)
	except Exception:
		pass


def plot_powercap_timeline(data: List[Measurement], out_path: Path, title_override: str | None = None) -> None:
	if plt is None or not data:
		return
	grouped: dict[float, List[Measurement]] = {}
	for m in data:
		grouped.setdefault(m.power_cap_w, []).append(m)
	trimmed: dict[float, List[Measurement]] = {cap: ms[-10:] for cap, ms in grouped.items()}
	keep_ids = {id(m) for ms in trimmed.values() for m in ms}
	filtered: List[Measurement] = [m for m in data if id(m) in keep_ids]

	cumulative_global = 0.0
	xs: List[float] = []
	ys: List[float] = []
	colors: List[float] = []
	for m in filtered:
		cumulative_global += m.sort_time_ms
		xs.append(cumulative_global / 1000.0)
		ys.append(m.power_cap_w)
		colors.append(m.power_cap_w)

	plt.figure(figsize=(11, 4.8))
	sc = plt.scatter(
		xs,
		ys,
		c=colors,
		cmap="viridis",
		s=36,
		alpha=0.9,
		edgecolors="black",
		linewidths=0.3,
		marker="o",
	)
	plt.colorbar(sc, label="Power Cap (W)")
	plt.xlabel("Time (s)")
	plt.ylabel("Power cap (W)")
	if title_override:
		plt.title(title_override)
	plt.grid(alpha=0.25, linestyle=":")

	out_path.parent.mkdir(parents=True, exist_ok=True)
	plt.tight_layout()
	plt.savefig(out_path)
	plt.close()


def plot_powercap_boxplot(data: List[Measurement], out_path: Path, title_override: str | None = None) -> None:
	if plt is None or not data:
		return
	grouped_full: dict[float, List[Measurement]] = {}
	for m in data:
		grouped_full.setdefault(m.power_cap_w, []).append(m)
	grouped_trimmed_ms: dict[float, List[float]] = {cap: [mm.sort_time_ms for mm in ms[-10:]] for cap, ms in grouped_full.items()}
	caps = sorted(grouped_trimmed_ms.keys())
	values_seconds = [[v / 1000.0 for v in grouped_trimmed_ms[c]] for c in caps]
	plt.figure(figsize=(10, 5))
	try:
		plt.boxplot(values_seconds, tick_labels=[f"{c:.3g}" for c in caps], showfliers=False)
	except TypeError:
		plt.boxplot(values_seconds, labels=[f"{c:.3g}" for c in caps], showfliers=False)
	plt.xlabel("Power cap (W)")
	plt.ylabel("Time (s)")
	if title_override:
		plt.title(title_override)
	all_vals = [v for sub in values_seconds for v in sub]
	if all_vals:
		mn, mx = min(all_vals), max(all_vals)
		if mx > 0 and mn > 0 and mx / mn > 8:
			plt.yscale('log')
			plt.ylabel("Time (s, log scale)")
	plt.grid(axis="y", alpha=0.3, linestyle=":")
	out_path.parent.mkdir(parents=True, exist_ok=True)
	plt.tight_layout()
	plt.savefig(out_path)
	plt.close()


def plot_cumulative_energy(data: List[Measurement], out_path: Path, title_override: str | None = None) -> None:

	if plt is None or not data:
		return
	grouped: dict[float, List[Measurement]] = {}
	for m in data:
		grouped.setdefault(m.power_cap_w, []).append(m)
	keep_ids = {id(m) for ms in grouped.values() for m in ms[-10:]}
	filtered: List[Measurement] = [m for m in data if id(m) in keep_ids]

	cumulative_time_s: List[float] = []
	cumulative_energy_j: List[float] = []
	cum_t = 0.0
	cum_e = 0.0
	prev_cap: float | None = None
	change_indices: List[int] = []
	for m in filtered:
		cum_t += m.sort_time_ms / 1000.0
		cum_e += m.energy_j
		cumulative_time_s.append(cum_t)
		cumulative_energy_j.append(cum_e)
		if prev_cap is None:
			prev_cap = m.power_cap_w
		elif m.power_cap_w != prev_cap:
			change_indices.append(len(cumulative_time_s) - 1)
			prev_cap = m.power_cap_w

	plt.figure(figsize=(11, 5.0))
	plt.plot(cumulative_time_s, cumulative_energy_j, color="#1f77b4", linewidth=1.3)
	plt.scatter(cumulative_time_s, cumulative_energy_j, s=30, color="#1f77b4", edgecolors="black", linewidths=0.25, alpha=0.9)

	for idx in change_indices:
		plt.axvline(cumulative_time_s[idx], color="#888", linestyle=":", linewidth=0.8, alpha=0.7)

	y_max = max(cumulative_energy_j) if cumulative_energy_j else 0.0
	y_min = min(cumulative_energy_j) if cumulative_energy_j else 0.0
	label_y = y_min + 0.03 * (y_max - y_min if y_max > y_min else 1.0)
	used_positions: List[float] = []
	span = cumulative_time_s[-1] if cumulative_time_s else 1.0
	for idx in change_indices:
		x = cumulative_time_s[idx]
		cap_val = filtered[idx].power_cap_w
		while any(abs(x - ox) < 0.01 * span for ox in used_positions):
			x += 0.005 * span
		used_positions.append(x)
		plt.text(x, label_y, f"{cap_val:.3g}W", rotation=90, va="bottom", ha="center", fontsize=7, color="#333", bbox=dict(facecolor='white', alpha=0.5, edgecolor='none', pad=0.5))

	plt.xlabel("Time (s)")
	plt.ylabel("Cumulative energy (J)")
	if title_override:
		plt.title(title_override)
	plt.grid(alpha=0.3, linestyle=":")
	plt.tight_layout()
	out_path.parent.mkdir(parents=True, exist_ok=True)
	plt.savefig(out_path)
	plt.close()


def _copy_root_artifacts(src_root: Path, out_root: Path) -> None:
	artifact_names = [
		"power_log.csv",
		"power_log.png",
		"result_Et.png",
		"result.csv",
		"result.png",
	]
	for name in artifact_names:
		src = src_root / name
		if not src.exists():
			continue
		dst = out_root / name
		try:
			shutil.copy2(src, dst)
		except Exception as e:
			print(f"[WARN] Failed copying artifact {src} -> {dst}: {e}")


def plot_relative_slowdown(data: List[Measurement], out_path: Path, title_override: str | None = None) -> None:
	if plt is None or not data:
		return
	grouped: dict[float, list[float]] = {}
	for m in data:
		grouped.setdefault(m.power_cap_w, []).append(m.sort_time_ms)
	grouped = {cap: vals[-10:] for cap, vals in grouped.items() if vals}
	if not grouped:
		return
	import statistics as _st
	values_sec: dict[float, list[float]] = {cap: [v/1000.0 for v in vals] for cap, vals in grouped.items()}
	medians_sec = {cap: _st.median(vals) for cap, vals in values_sec.items()}
	fastest = min(medians_sec.values())
	caps = sorted(values_sec.keys(), reverse=True)
	values_lists = [values_sec[c] for c in caps]
	plt.figure(figsize=(10,5))
	try:
		plt.boxplot(values_lists, tick_labels=[f"{c:.3g}" for c in caps], showfliers=False)
	except TypeError:
		plt.boxplot(values_lists, labels=[f"{c:.3g}" for c in caps], showfliers=False)
	plt.xlabel("Power cap (W)")
	plt.ylabel("Time (s)")
	if title_override:
		plt.title(title_override)
	global_max = max(max(vs) for vs in values_lists) if values_lists else 0.0
	if global_max > 0:
		plt.ylim(0, global_max * 1.12)
	headroom = global_max * 0.04
	for i, c in enumerate(caps, start=1):
		factor = medians_sec[c] / fastest if fastest > 0 else float('nan')
		label_y = max(values_lists[i-1]) + headroom * 0.2
		if label_y > global_max * 1.08:
			label_y = global_max * 1.08
		plt.text(i, label_y, f"{factor:.2f}×", ha='center', va='bottom', fontsize=7)
	plt.grid(axis='y', alpha=0.3, linestyle=':')
	plt.tight_layout()
	out_path.parent.mkdir(parents=True, exist_ok=True)
	plt.savefig(out_path)
	plt.close()


def aggregate_and_sort(measurements: List[Measurement]) -> List[Measurement]:
	return sorted(measurements, key=lambda m: (m.experiment, m.global_index))


def main(argv: Optional[List[str]] = None) -> int:
	parser = argparse.ArgumentParser(description="Analyze experiment log directories")
	parser.add_argument("log_dirs", nargs="+", help="Paths to experiment directories (timestamp folders under logs/)")
	parser.add_argument("--out-dir", required=True, help="Output directory for artifacts")
	parser.add_argument("--no-plots", action="store_true", help="Skip plot generation")
	parser.add_argument("--json", action="store_true", help="Emit JSON summary of basic stats")
	args = parser.parse_args(argv)

	all_measurements: List[Measurement] = []
	for d in args.log_dirs:
		exp_path = Path(d).resolve()
		if exp_path.is_dir():
			try:
				ms = collect_experiment(exp_path)
			except Exception as e:
				print(f"[WARN] Failed to parse {exp_path}: {e}", file=sys.stderr)
				continue
			all_measurements.extend(ms)
		else:
			print(f"[WARN] Not a directory: {d}", file=sys.stderr)

	if not all_measurements:
		print("No measurements parsed.")
		return 1

	all_measurements = aggregate_and_sort(all_measurements)

	out_dir = Path(args.out_dir).resolve()
	out_dir.mkdir(parents=True, exist_ok=True)

	csv_path = out_dir / "aggregated_measurements.csv"
	write_csv(all_measurements, csv_path)
	write_parquet_if_possible(all_measurements, out_dir / "aggregated_measurements.parquet")

	if not args.no_plots:
		root_exp_dir = Path(args.log_dirs[0])
		candidate_children = [c.name for c in root_exp_dir.iterdir() if c.is_dir() and '_' in c.name]
		title_override = max(candidate_children, key=len) if candidate_children else root_exp_dir.name
		if candidate_children:
			cfg_dir = root_exp_dir / title_override
			if cfg_dir.is_dir():
				dst_dir = out_dir / title_override
				if dst_dir.exists():
					shutil.rmtree(dst_dir)
				shutil.copytree(cfg_dir, dst_dir)
		plot_powercap_timeline(all_measurements, out_dir / "powercap_timeline.png", title_override=title_override)
		plot_cumulative_energy(all_measurements, out_dir / "cumulative_energy.png", title_override=title_override)
		plot_relative_slowdown(all_measurements, out_dir / "relative_slowdown_boxplot.png", title_override=title_override)

	for d in args.log_dirs:
		root = Path(d)
		if root.is_dir():
			_copy_root_artifacts(root, out_dir)

	from statistics import mean, pstdev
	stats_full: dict[float, List[float]] = {}
	for m in all_measurements:
		stats_full.setdefault(m.power_cap_w, []).append(m.sort_time_ms)
	stats_last10: dict[float, List[float]] = {}
	for cap, vals in stats_full.items():
		stats_last10[cap] = vals[-10:]

	def summarize(values: List[float]) -> dict:
		if not values:
			return {"n": 0}
		vals_sorted = sorted(values)
		def percentile(p: float) -> float:
			if not vals_sorted:
				return float('nan')
			k = (len(vals_sorted) - 1) * p
			f = int(k)
			c = min(f + 1, len(vals_sorted) - 1)
			if f == c:
				return vals_sorted[f]
			return vals_sorted[f] + (vals_sorted[c] - vals_sorted[f]) * (k - f)
		return {
			"n": len(values),
			"mean_ms": mean(values),
			"std_ms": pstdev(values) if len(values) > 1 else 0.0,
			"median_ms": percentile(0.5),
			"p10_ms": percentile(0.10),
			"p25_ms": percentile(0.25),
			"p75_ms": percentile(0.75),
			"p90_ms": percentile(0.90),
			"min_ms": vals_sorted[0],
			"max_ms": vals_sorted[-1],
		}

	full_stats_struct = {cap: summarize(vals) for cap, vals in stats_full.items()}
	last10_stats_struct = {cap: summarize(vals) for cap, vals in stats_last10.items()}
	(out_dir / "per_powercap_full_stats.json").write_text(json.dumps(full_stats_struct, indent=2), encoding="utf-8")
	(out_dir / "per_powercap_last10_stats.json").write_text(json.dumps(last10_stats_struct, indent=2), encoding="utf-8")

	stats_csv_path = out_dir / "per_powercap_last10_stats.csv"
	with stats_csv_path.open("w", newline="", encoding="utf-8") as f:
		fieldnames = ["power_cap_w"] + list(next(iter(last10_stats_struct.values())).keys()) if last10_stats_struct else ["power_cap_w"]
		writer = csv.DictWriter(f, fieldnames=fieldnames)
		writer.writeheader()
		for cap, s in sorted(last10_stats_struct.items()):
			row = {"power_cap_w": cap}
			row.update(s)
			writer.writerow(row)

	if args.json:
		stats: dict[float, dict[str, float]] = {}
		per_cap: dict[float, List[float]] = {}
		for m in all_measurements:
			per_cap.setdefault(m.power_cap_w, []).append(m.sort_time_ms)
		for cap, vals in per_cap.items():
			if not vals:
				continue
			stats[cap] = {
				"n": len(vals),
				"mean_ms": sum(vals) / len(vals),
				"min_ms": min(vals),
				"max_ms": max(vals),
			}
		(out_dir / "summary_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

	print(f"Parsed {len(all_measurements)} measurements across {len(set(m.experiment for m in all_measurements))} experiment(s).")
	print(f"CSV: {csv_path}")
	if not args.no_plots:
		print(f"Plots: {out_dir}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
