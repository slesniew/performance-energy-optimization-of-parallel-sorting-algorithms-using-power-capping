from __future__ import annotations
import argparse, csv, math, re, json
from pathlib import Path
from typing import List, Dict, Any
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COMMON_PREFIX = "qs_parallel_"

def load_metrics(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            try:
                e = r.get("best_pareto_tradeoff_median_energy_j")
                t = r.get("best_pareto_tradeoff_median_time_ms")
                if e is None or t is None:
                    continue
                e_val = float(e) if e != '' else float('nan')
                t_val = float(t) if t != '' else float('nan')
            except Exception:
                continue
            if math.isnan(e_val) or math.isnan(t_val):
                continue
            r["energy_j"] = e_val
            r["time_ms"] = t_val
            rows.append(r)
    return rows

def shorten(name: str) -> str:
    if name.startswith(COMMON_PREFIX):
        return name[len(COMMON_PREFIX):]
    return name

def plot_class(rows: List[Dict[str, Any]], size_class: str, out_dir: Path, dpi: int, style: str,
               fastest_ref: Dict[str, float] | None, efficient_ref: Dict[str, float] | None):
    if not rows:
        print(f"No rows for class {size_class}")
        return
    xs = [r['energy_j'] for r in rows]
    ys = [r['time_ms'] for r in rows]
    configs = [r['config'] for r in rows]

    if style == 'dark':
        plt.style.use('dark_background')
    else:
        plt.style.use('default')

    fig, ax = plt.subplots(figsize=(8,6))
    sc = ax.scatter(xs, ys, c='tab:blue', edgecolors='white', linewidths=0.5, alpha=0.85)
    ax.set_xlabel('Energy (J)')
    ax.set_ylabel('Time (ms)')
    ax.set_title(f'Pareto Tradeoff Points (class {size_class})')
    ax.grid(True, linestyle='--', alpha=0.3)

    order = sorted([(ys[i], xs[i], i) for i in range(len(xs))])
    alphabet = [chr(ord('a')+k) for k in range(26)]
    for seq, (_, _, idx) in enumerate(order):
        if seq < len(alphabet):
            label = alphabet[seq]
        else:
            label = alphabet[seq % 26] + str(seq//26)
        ax.annotate(label, (xs[idx], ys[idx]), textcoords='offset points',
                    xytext=(0,-10), ha='center', va='top', fontsize=8, fontweight='bold')

    handles_labels = []
    if fastest_ref and all(k in fastest_ref for k in ('time_ms','energy_j')):
        fx = fastest_ref['energy_j']; fy = fastest_ref['time_ms']
        lbl_fast = f"Fastest (t={fy:.0f} ms, E={fx:.1f} J)"
        h_fast = ax.scatter([fx],[fy], c='red', marker='x', s=90, linewidths=2)
        ax.annotate('F', (fx,fy), textcoords='offset points', xytext=(6,-10), fontsize=8, color='red', fontweight='bold')
        handles_labels.append((h_fast, lbl_fast))

    if efficient_ref and all(k in efficient_ref for k in ('time_ms','energy_j')):
        ex = efficient_ref['energy_j']; ey = efficient_ref['time_ms']
        lbl_eff = f"Lowest energy (t={ey:.0f} ms, E={ex:.1f} J)"
        marker = 'o'
        color = 'green'
        if fastest_ref and abs(ex - fastest_ref['energy_j']) < 1e-9 and abs(ey - fastest_ref['time_ms']) < 1e-9:
            lbl_eff = 'Fastest & lowest energy'
        h_eff = ax.scatter([ex],[ey], c=color, marker=marker, s=70, edgecolors='black', linewidths=0.8)
        ax.annotate('E', (ex,ey), textcoords='offset points', xytext=(6,8), fontsize=8, color=color, fontweight='bold')
        handles_labels.append((h_eff, lbl_eff))

    if handles_labels:
        hs, ls = zip(*handles_labels)
        ax.legend(hs, ls, loc='best', fontsize=8, frameon=True)

    out_png = out_dir / f"pareto_scatter_{size_class}.png"
    fig.tight_layout()
    fig.savefig(out_png, dpi=dpi)
    plt.close(fig)
    print(f"Saved {out_png}")


def main():
    ap = argparse.ArgumentParser(description='Plot energy vs time of best Pareto tradeoff per config for each size class.')
    ap.add_argument('--root', required=True, help='Root folder (e.g. logs_analyzed/qs_split)')
    ap.add_argument('--summary-dir', help='Summary directory (default <root>/__summary__)')
    ap.add_argument('--style', choices=['light','dark'], default='light')
    ap.add_argument('--dpi', type=int, default=150)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    summary = Path(args.summary_dir).resolve() if args.summary_dir else root / '__summary__'
    if not summary.is_dir():
        raise SystemExit(f'Summary directory not found: {summary}')

    def derive_fastest_reference(sc: str):
        metrics_path = summary / f'per_config_metrics.{sc}.csv'
        if not metrics_path.exists():
            return None
        target = None
        with metrics_path.open('r', encoding='utf-8') as f:
            rdr = csv.DictReader(f)
            for r in rdr:
                val = r.get('fastest_cap_median_time_ms')
                cap = r.get('fastest_cap')
                cfg = r.get('config')
                if not (val and cap and cfg):
                    continue
                try:
                    t_val = float(val); cap_val = float(cap)
                except Exception:
                    continue
                if t_val != t_val:
                    continue
                if target is None or t_val < target['t']:
                    target = {'config': cfg, 'cap': cap_val, 't': t_val}
        if target is None:
            return None
        gb_path = summary / f'global_best.{sc}.json'
        time_val = None
        energy_val = None
        if gb_path.exists():
            try:
                gb = json.loads(gb_path.read_text(encoding='utf-8'))
                best_block = gb.get('best', {})
                for entry in best_block.values():
                    if isinstance(entry, dict) and entry.get('config') == target['config']:
                        per_cap = entry.get('per_cap', {})
                        cap_data = per_cap.get(str(target['cap']))
                        if cap_data:
                            time_val = cap_data.get('median_time_ms')
                            energy_val = cap_data.get('median_energy_j')
                            break
            except Exception as e:
                print(f"Warning: cannot parse global_best for {sc}: {e}")
        if energy_val is None or time_val is None:
            pcs_path = summary / f'per_config_summary.{sc}.json'
            if pcs_path.exists():
                try:
                    arr = json.loads(pcs_path.read_text(encoding='utf-8'))
                    for entry in arr:
                        if entry.get('config') == target['config']:
                            per_cap = entry.get('per_cap', {})
                            cap_data = per_cap.get(str(target['cap']))
                            if cap_data:
                                time_val = time_val if time_val is not None else cap_data.get('median_time_ms')
                                energy_val = energy_val if energy_val is not None else cap_data.get('median_energy_j')
                            break
                except Exception as e:
                    print(f"Warning: cannot parse per_config_summary for {sc}: {e}")
        if energy_val is None or time_val is None:
            return None
        return {
            'config': target['config'],
            'cap': target['cap'],
            'time_ms': float(time_val),
            'energy_j': float(energy_val)
        }

    def derive_efficient_reference(sc: str):
        metrics_path = summary / f'per_config_metrics.{sc}.csv'
        if not metrics_path.exists():
            return None
        target = None
        with metrics_path.open('r', encoding='utf-8') as f:
            rdr = csv.DictReader(f)
            for r in rdr:
                e_val = r.get('lowest_energy_median_j')
                cap = r.get('lowest_energy_cap')
                cfg = r.get('config')
                if not (e_val and cap and cfg):
                    continue
                try:
                    energy = float(e_val); cap_val = float(cap)
                except Exception:
                    continue
                if energy != energy:
                    continue
                if target is None or energy < target['energy_j']:
                    target = {'config': cfg, 'cap': cap_val, 'energy_j': energy}
        if target is None:
            return None
        gb_path = summary / f'global_best.{sc}.json'
        time_val = None
        energy_val = None
        if gb_path.exists():
            try:
                gb = json.loads(gb_path.read_text(encoding='utf-8'))
                best_block = gb.get('best', {})
                for entry in best_block.values():
                    if isinstance(entry, dict) and entry.get('config') == target['config']:
                        per_cap = entry.get('per_cap', {})
                        cap_data = per_cap.get(str(target['cap']))
                        if cap_data:
                            time_val = cap_data.get('median_time_ms')
                            energy_val = cap_data.get('median_energy_j')
                            break
            except Exception:
                pass
        if energy_val is None or time_val is None:
            pcs_path = summary / f'per_config_summary.{sc}.json'
            if pcs_path.exists():
                try:
                    arr = json.loads(pcs_path.read_text(encoding='utf-8'))
                    for entry in arr:
                        if entry.get('config') == target['config']:
                            per_cap = entry.get('per_cap', {})
                            cap_data = per_cap.get(str(target['cap']))
                            if cap_data:
                                time_val = time_val if time_val is not None else cap_data.get('median_time_ms')
                                energy_val = energy_val if energy_val is not None else cap_data.get('median_energy_j')
                            break
                except Exception:
                    pass
        if energy_val is None or time_val is None:
            return None
        return {
            'config': target['config'],
            'cap': target['cap'],
            'time_ms': float(time_val),
            'energy_j': float(energy_val)
        }

    for sc in ['S','M']:
        csv_path = summary / f'per_config_metrics.{sc}.csv'
        rows = load_metrics(csv_path)
        fastest_ref = derive_fastest_reference(sc)
        efficient_ref = derive_efficient_reference(sc)
        plot_class(rows, sc, summary, args.dpi, args.style, fastest_ref, efficient_ref)

if __name__ == '__main__':
    main()
