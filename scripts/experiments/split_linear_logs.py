from __future__ import annotations

import argparse
import ast
import re
import shutil
from itertools import islice
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

PARAMS_RE = re.compile(r"PowerCap:\s*([0-9]+(?:\.[0-9]+)?)")
ALG_RE = re.compile(r"Algorithm:\s*([A-Za-z0-9_]+)")
THREADS_RE = re.compile(r"Threads:\s*([0-9]+)")
SIZE_RE = re.compile(r"Size:\s*([0-9]+)")


@dataclass
class RunMeta:
    path: Path
    timestamp: str
    power_cap: float
    algorithm: Optional[str]
    threads: Optional[int]
    size: Optional[int]


@dataclass
class Config:
    raw: Dict[str, Any]
    index: int

    def sanitized_name(self) -> str:
        def sanitize(val: Any) -> str:
            return str(val).replace(" ", "_").replace("/", "_").replace("%", "pct")

        return f"{sanitize(self.raw['algorithm'])}_{sanitize(self.raw['threads'])}_{sanitize(self.raw['core_type'])}_{sanitize(self.raw['input_size'])}_{sanitize(self.raw['input_type'])}_{sanitize(self.raw.get('thread_affinity','close'))}"


def parse_all_combinations(path: Path) -> List[Config]:
    if not path.exists():
        raise FileNotFoundError(f"all_combinations.txt not found: {path}")
    configs: List[Config] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            idx_part, dict_part = line.split(':', 1)
            idx = int(idx_part.strip())
            dict_str = dict_part.strip()
            brace_pos = dict_str.find('{')
            if brace_pos > 0:
                dict_str = dict_str[brace_pos:]
            data = ast.literal_eval(dict_str)
            if isinstance(data, dict):
                configs.append(Config(raw=data, index=idx))
        except Exception:
            continue
    configs.sort(key=lambda c: c.index)
    return configs


def parse_parameters_file(p: Path) -> RunMeta:
    text = p.read_text(encoding="utf-8", errors="ignore")
    m_power = PARAMS_RE.search(text)
    m_alg = ALG_RE.search(text)
    m_threads = THREADS_RE.search(text)
    m_size = SIZE_RE.search(text)
    power = float(m_power.group(1)) if m_power else float('nan')
    alg = m_alg.group(1) if m_alg else None
    threads = int(m_threads.group(1)) if m_threads else None
    size = int(m_size.group(1)) if m_size else None
    run_dir = p.parent
    return RunMeta(path=run_dir, timestamp=run_dir.name, power_cap=power, algorithm=alg, threads=threads, size=size)


def collect_runs(logs_dir: Path) -> List[RunMeta]:
    run_dirs = [d for d in logs_dir.iterdir() if d.is_dir()]
    run_dirs.sort(key=lambda d: d.name)
    runs: List[RunMeta] = []
    for rd in run_dirs:
        params = rd / 'parameters.log'
        if not params.exists():
            continue
        try:
            runs.append(parse_parameters_file(params))
        except Exception:
            continue
    return runs


def group_runs_by_configuration(runs: List[RunMeta], max_power: Optional[float]) -> List[List[RunMeta]]:
    if not runs:
        return []
    if max_power is None:
        powers = sorted(r.power_cap for r in runs if r.power_cap == r.power_cap)
        if not powers:
            raise ValueError("No valid power caps found.")
        candidate = max(powers)
        max_power = candidate
    groups: List[List[RunMeta]] = []
    current: List[RunMeta] = []
    seen_lower = False

    for r in runs:
        boundary = False
        if current:
            if r.power_cap == max_power and seen_lower:
                boundary = True
        if boundary:
            groups.append(current)
            current = [r]
            seen_lower = False
        else:
            current.append(r)
            if r.power_cap < max_power:
                seen_lower = True
    if current:
        groups.append(current)
    return groups


def copy_run(src_run: Path, dest_runs_root: Path) -> None:
    dest = dest_runs_root / src_run.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src_run, dest)


def perform_split(exp_root: Path, dest_root: Path, dry_run: bool, max_power: Optional[float]) -> None:
    combinations_path = exp_root / 'all_combinations.txt'
    configs = parse_all_combinations(combinations_path)
    if not configs:
        raise RuntimeError("No configurations parsed from all_combinations.txt")

    logs_dir = exp_root / 'logs'
    if not logs_dir.exists():
        raise FileNotFoundError(f"logs directory not found: {logs_dir}")

    runs = collect_runs(logs_dir)
    if not runs:
        raise RuntimeError("No runs (parameters.log files) found under logs/")

    groups = group_runs_by_configuration(runs, max_power)

    print(f"Detected {len(runs)} runs.")
    print(f"Detected {len(groups)} configuration groups from power cap boundaries.")
    print(f"There are {len(configs)} configurations in all_combinations.txt.")

    if len(groups) > len(configs):
        print("Warning: More groups than configurations; extra groups will be ignored.")
    if len(groups) < len(configs):
        print("Warning: Fewer groups than configurations; some configs have no runs.")

    dest_root.mkdir(parents=True, exist_ok=True)

    original_cfg_dirs = [d for d in exp_root.iterdir() if d.is_dir() and d.name not in {"logs", dest_root.name, "split_configs"}]

    def find_original_cfg_dir(cfg: Config) -> Optional[Path]:
        def first_key(d: Dict[str, Any], *keys: str) -> Optional[str]:
            for k in keys:
                if k in d and d[k] is not None:
                    return str(d[k])
            return None

        algo = first_key(cfg.raw, 'algorithm', 'algo', 'alg') or ''
        threads = first_key(cfg.raw, 'threads', 'thread_count', 'nthreads') or ''
        core_type = first_key(cfg.raw, 'core_type', 'coreType')
        input_type = first_key(cfg.raw, 'input_type', 'inputType')
        thread_affinity = first_key(cfg.raw, 'thread_affinity', 'affinity', 'pinning')

        if not algo or not threads:
            return None

        base_need = f"_{threads}_"
        candidates = []
        for cand in original_cfg_dirs:
            name = cand.name
            if algo not in name:
                continue
            if base_need not in name:
                continue
            opt_matches = 0
            for val in (core_type, input_type, thread_affinity):
                if val and val in name:
                    opt_matches += 1
            starts = 1 if name.startswith(f"{algo}_{threads}_") else 0
            candidates.append((opt_matches, starts, len(name), name, cand))

        if not candidates:
            return None
        candidates.sort(key=lambda t: (-t[0], -t[1], -t[2], t[3]))
        return candidates[0][4]

    ARTIFACT_FILES = [
        "power_log.csv",
        "power_log.png",
        "result_Et.png",
        "result.csv",
        "result.png",
    ]

    for i, group in enumerate(groups):
        if i >= len(configs):
            break
        cfg = configs[i]
        cfg_name = cfg.sanitized_name()
        cfg_dir = dest_root / cfg_name
        logs_subdir = cfg_dir / 'logs'
        if not dry_run:
            logs_subdir.mkdir(parents=True, exist_ok=True)
        first = group[0]
        powers = [r.power_cap for r in group]
        print(f"[Config {cfg.index}] -> {cfg_name}: {len(group)} runs, power caps sample={powers[:6]} ... last={powers[-1]}" )
        if dry_run:
            continue
        for r in group:
            copy_run(r.path, logs_subdir)
        manifest = cfg_dir / 'SPLIT_MANIFEST.txt'
        manifest.write_text(
            "Configuration (from all_combinations):\n"
            f"{cfg.raw}\n\n"
            f"Source experiment root: {exp_root}\n"
            f"Runs included ({len(group)}):\n" + "\n".join(r.timestamp for r in group) + "\n",
            encoding='utf-8'
        )
        orig_dir = find_original_cfg_dir(cfg)
        if orig_dir is None:
            print(f"  [WARN] No matching original config directory found for {cfg_name} (algo={cfg.raw.get('algorithm')} threads={cfg.raw.get('threads')})")
        else:
            for fname in ARTIFACT_FILES:
                src = orig_dir / fname
                if not src.exists():
                    continue
                dst = cfg_dir / fname
                try:
                    shutil.copy2(src, dst)
                except Exception as e:
                    print(f"  [WARN] Failed to copy {src} -> {dst}: {e}")

    print("Done." + (" (dry run)" if dry_run else ""))
    print(f"Split configurations written under: {dest_root}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Split continuous experiment logs into per-configuration directories")
    parser.add_argument('experiment_dir', help='Path to experiment root containing all_combinations.txt and logs/')
    parser.add_argument('--dest-root', help='Destination root for split configuration directories (default: <experiment_dir>/split_configs)')
    parser.add_argument('--max-power', type=float, default=None, help='Explicit max power cap value (auto-detected if omitted)')
    parser.add_argument('--dry-run', action='store_true', help='Only show what would be done, no copying')
    args = parser.parse_args(argv)

    exp_root = Path(args.experiment_dir).resolve()
    if not exp_root.exists():
        print(f"Experiment directory not found: {exp_root}")
        return 1
    dest_root = Path(args.dest_root).resolve() if args.dest_root else exp_root / 'split_configs'

    try:
        perform_split(exp_root, dest_root, dry_run=args.dry_run, max_power=args.max_power)
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
