from __future__ import annotations
import argparse, csv, json, math
from pathlib import Path
from typing import Dict, Any, List, Optional

def load_rows(metrics_csv: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not metrics_csv.exists():
        return out
    with metrics_csv.open('r', encoding='utf-8') as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            out.append(r)
    return out

def find_fastest_ref(rows: List[Dict[str, Any]], summary_dir: Path, size_class: str) -> Optional[Dict[str, Any]]:
    fastest = None
    for r in rows:
        t = r.get('fastest_cap_median_time_ms')
        cap = r.get('fastest_cap')
        cfg = r.get('config')
        if not (t and cap and cfg):
            continue
        try:
            t_val = float(t); cap_val = float(cap)
        except Exception:
            continue
        if t_val != t_val:
            continue
        if fastest is None or t_val < fastest['time_ms']:
            fastest = {'config': cfg, 'cap': cap_val, 'time_ms': t_val}
    if fastest is None:
        return None
    gb_path = summary_dir / f'global_best.{size_class}.json'
    energy_val = None
    time_val = None
    if gb_path.exists():
        try:
            gb = json.loads(gb_path.read_text(encoding='utf-8'))
            best_block = gb.get('best', {})
            for entry in best_block.values():
                if isinstance(entry, dict) and entry.get('config') == fastest['config']:
                    per_cap = entry.get('per_cap', {})
                    cap_data = per_cap.get(str(fastest['cap']))
                    if cap_data:
                        time_val = cap_data.get('median_time_ms')
                        energy_val = cap_data.get('median_energy_j')
                        break
        except Exception:
            pass
    if energy_val is None or time_val is None:
        pcs_path = summary_dir / f'per_config_summary.{size_class}.json'
        if pcs_path.exists():
            try:
                arr = json.loads(pcs_path.read_text(encoding='utf-8'))
                for entry in arr:
                    if entry.get('config') == fastest['config']:
                        per_cap = entry.get('per_cap', {})
                        cap_data = per_cap.get(str(fastest['cap']))
                        if cap_data:
                            time_val = time_val if time_val is not None else cap_data.get('median_time_ms')
                            energy_val = energy_val if energy_val is not None else cap_data.get('median_energy_j')
                        break
            except Exception:
                pass
    if energy_val is None or time_val is None:
        return None
    fastest['energy_j'] = float(energy_val)
    fastest['time_ms'] = float(time_val)
    return fastest

def summarize(rows: List[Dict[str, Any]], fastest: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    ft = fastest['time_ms']
    fe = fastest['energy_j']
    for r in rows:
        pt = r.get('best_pareto_tradeoff_median_time_ms')
        pe = r.get('best_pareto_tradeoff_median_energy_j')
        pc = r.get('best_pareto_tradeoff_power_cap_w')
        cfg = r.get('config')
        if not (pt and pe and pc and cfg):
            continue
        try:
            pt_val = float(pt); pe_val = float(pe); pc_val = float(pc)
        except Exception:
            continue
        if any(math.isnan(x) for x in (pt_val, pe_val, pc_val)):
            continue
        time_pct = 100.0 * (pt_val - ft) / ft if ft else float('nan')
        energy_pct = 100.0 * (pe_val - fe) / fe if fe else float('nan')
        out.append({
            'config': cfg,
            'pareto_cap': pc_val,
            'pareto_time_ms': pt_val,
            'pareto_energy_j': pe_val,
            'time_pct': time_pct,
            'energy_pct': energy_pct
        })
    out.sort(key=lambda x: (x['time_pct'], x['energy_pct']))
    alphabet = [chr(ord('a')+k) for k in range(26)]
    for i, item in enumerate(out):
        if i < len(alphabet):
            label = alphabet[i]
        else:
            label = alphabet[i % 26] + str(i//26)
        item['label'] = label
    return out

def write_text(path: Path, entries: List[Dict[str, Any]], fastest: Dict[str, Any]):
    with path.open('w', encoding='utf-8') as f:
        f.write('# Pareto tradeoff vs fastest reference\n')
        f.write(f"# Fastest config={fastest['config']} cap={fastest['cap']} time_ms={fastest['time_ms']:.3f} energy_j={fastest['energy_j']:.3f}\n")
        header = [
            'rank','label','config','pareto_cap','pareto_time_ms','pareto_energy_j',
            'time_pct','energy_pct','fastest_time_ms','fastest_energy_j','fastest_config','fastest_cap'
        ]
        f.write('\t'.join(header) + '\n')
        for idx, e in enumerate(entries, start=1):
            f.write('\t'.join([
                str(idx),
                e['label'],
                e['config'],
                f"{e['pareto_cap']:.1f}",
                f"{e['pareto_time_ms']:.3f}",
                f"{e['pareto_energy_j']:.3f}",
                f"{e['time_pct']:+.2f}%",
                f"{e['energy_pct']:+.2f}%",
                f"{fastest['time_ms']:.3f}",
                f"{fastest['energy_j']:.3f}",
                fastest['config'],
                f"{fastest['cap']:.1f}"
            ]) + '\n')
    print(f"Wrote {path}")

def main():
    ap = argparse.ArgumentParser(description='Summarize Pareto tradeoff vs fastest reference for each size class.')
    ap.add_argument('--root', required=True, help='Root directory (e.g. logs_analyzed/qs_split)')
    ap.add_argument('--summary-dir', help='Summary directory (default <root>/__summary__)')
    args = ap.parse_args()
    root = Path(args.root).resolve()
    summary_dir = Path(args.summary_dir).resolve() if args.summary_dir else root / '__summary__'
    if not summary_dir.is_dir():
        raise SystemExit(f'Summary dir not found: {summary_dir}')
    for sc in ['S','M']:
        metrics_csv = summary_dir / f'per_config_metrics.{sc}.csv'
        rows = load_rows(metrics_csv)
        if not rows:
            print(f"No rows for {sc}")
            continue
        fastest = find_fastest_ref(rows, summary_dir, sc)
        if not fastest:
            print(f"No fastest reference for {sc}")
            continue
        entries = summarize(rows, fastest)
        out_file = summary_dir / f'pareto_tradeoff_summary_{sc}.txt'
        write_text(out_file, entries, fastest)

if __name__ == '__main__':
    main()
