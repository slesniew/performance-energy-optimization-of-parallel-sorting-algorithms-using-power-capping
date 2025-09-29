import argparse, json, csv, math
from pathlib import Path
from typing import List, Dict, Any, Tuple

def read_agg(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            try:
                r["power_cap_w"] = float(r.get("power_cap_w","nan"))
                r["sort_time_ms"] = float(r.get("sort_time_ms","nan"))
                r["energy_j"] = float(r.get("energy_j","nan"))
            except Exception:
                continue
            rows.append(r)
    return rows

def last10_median(values: List[float]) -> float:
    vals = [v for v in values if v == v]
    if not vals:
        return float('nan')
    slice_vals = vals[-10:] if len(vals) > 10 else vals
    sv = sorted(slice_vals)
    m = len(sv)
    if m % 2: return sv[m//2]
    return 0.5*(sv[m//2 -1] + sv[m//2])

def group_by_power(rows: List[Dict[str, Any]]) -> Dict[float, Dict[str, Any]]:
    per: Dict[float, Dict[str, Any]] = {}
    bucket: Dict[float, List[Dict[str, Any]]] = {}
    for r in rows:
        cap = r["power_cap_w"]
        if cap != cap:
            continue
        bucket.setdefault(cap, []).append(r)
    for cap, rs in bucket.items():
        times = [x["sort_time_ms"] for x in rs if x["sort_time_ms"] == x["sort_time_ms"]]
        energies = [x["energy_j"] for x in rs if x["energy_j"] == x["energy_j"]]
        per[cap] = {
            "n": len(rs),
            "median_time_ms": last10_median(times),
            "median_energy_j": last10_median(energies) if energies else float('nan'),
        }
    return per

def pareto_front(points: List[Tuple[float,float]]) -> List[Tuple[float,float]]:
    pts = [(t,e) for t,e in points if t==t and e==e]
    pts.sort()
    front = []
    best_e = math.inf
    for t,e in pts:
        if e < best_e:
            front.append((t,e))
            best_e = e
    return front

def compute_auc_relative(power_caps: List[float], median_time: Dict[float,float]) -> float:
    if not power_caps:
        return float('nan')
    caps_sorted = sorted(power_caps, reverse=True)
    valid = [(c, median_time[c]) for c in caps_sorted if median_time[c]==median_time[c]]
    if not valid:
        return float('nan')
    t_ref = valid[0][1]
    if t_ref <= 0:
        return float('nan')
    max_power = valid[0][0]
    pts = [(c/max_power, t/t_ref) for c,t in valid]
    auc = 0.0
    for (x1,y1),(x2,y2) in zip(pts[:-1], pts[1:]):
        auc += 0.5*(y1+y2)*abs(x1-x2)
    return auc

def normalize(values: List[float]) -> Dict[float,float]:
    valid = [v for v in values if v==v]
    if not valid:
        return {}
    mn, mx = min(valid), max(valid)
    span = mx - mn if mx > mn else 1.0
    return {v: (v - mn)/span for v in set(values)}

def analyze_config(dir_path: Path) -> Dict[str, Any]:
    agg = dir_path / "aggregated_measurements.csv"
    if not agg.exists():
        return {}
    rows = read_agg(agg)
    if not rows:
        return {}
    per = group_by_power(rows)
    if not per:
        return {}
    caps = sorted(per.keys())
    name = dir_path.name
    if "_S_INT_" in name:
        size_class = "S"
    elif "_M_INT_" in name:
        size_class = "M"
    else:
        try:
            dataset_size_val = int(float(rows[0].get("size", "nan")))
        except Exception:
            dataset_size_val = None
        size_class = "S" if (dataset_size_val is not None and dataset_size_val < 500_000_000) else "M"
    try:
        dataset_size = int(float(rows[0].get("size", "nan")))
    except Exception:
        dataset_size = None
    max_power = max(caps)
    min_power = min(caps)
    fastest_cap = min(caps, key=lambda c: per[c]["median_time_ms"])
    lowest_energy_cap = min(caps, key=lambda c: per[c]["median_energy_j"] if per[c]["median_energy_j"]==per[c]["median_energy_j"] else math.inf)
    pts = [(per[c]["median_time_ms"], per[c]["median_energy_j"]) for c in caps]
    front = pareto_front(pts)
    front_caps = []
    used = set()
    for t,e in front:
        for c in caps:
            if c in used: continue
            if abs(per[c]["median_time_ms"] - t) < 1e-12 and abs(per[c]["median_energy_j"] - e) < 1e-12:
                front_caps.append(c)
                used.add(c)
                break
    scaling_ratio = float('nan')
    mt_max = per[max_power]["median_time_ms"]
    mt_min = per[min_power]["median_time_ms"]
    if mt_max==mt_max and mt_min==mt_min and mt_max>0:
        scaling_ratio = mt_min / mt_max
    auc_rel = compute_auc_relative(caps, {c: per[c]["median_time_ms"] for c in caps})
    energy_at_max = per[max_power]["median_energy_j"]
    fastest_median_time = min(per[c]["median_time_ms"] for c in caps)
    norm_time_map = normalize([per[c]["median_time_ms"] for c in front_caps])
    norm_energy_map = normalize([per[c]["median_energy_j"] for c in front_caps if per[c]["median_energy_j"]==per[c]["median_energy_j"]])
    pareto_points = []
    for c in front_caps:
        t = per[c]["median_time_ms"]
        e = per[c]["median_energy_j"]
        nt = norm_time_map.get(t, float('nan'))
        ne = norm_energy_map.get(e, float('nan'))
        score = nt + ne if nt==nt and ne==ne else float('nan')
        pareto_points.append({
            "power_cap_w": c,
            "median_time_ms": t,
            "median_energy_j": e,
            "norm_time": nt,
            "norm_energy": ne,
            "tradeoff_score": score
        })
    pareto_points_sorted = sorted(pareto_points, key=lambda x: (x["tradeoff_score"] if x["tradeoff_score"]==x["tradeoff_score"] else math.inf))
    best_tradeoff = pareto_points_sorted[0] if pareto_points_sorted else None
    return {
        "config": dir_path.name,
    "size_class": size_class,
    "dataset_size": dataset_size,
        "power_caps": caps,
        "per_cap": per,
        "fastest_cap": fastest_cap,
        "fastest_cap_median_time_ms": per[fastest_cap]["median_time_ms"],
        "lowest_energy_cap": lowest_energy_cap,
        "lowest_energy_median_j": per[lowest_energy_cap]["median_energy_j"],
        "pareto_front_caps": front_caps,
        "pareto_points": pareto_points_sorted,
        "best_pareto_tradeoff": best_tradeoff,
        "max_power": max_power,
        "min_power": min_power,
        "max_power_median_time_ms": mt_max,
        "min_power_median_time_ms": mt_min,
        "fastest_median_time_ms": fastest_median_time,
        "scaling_ratio": scaling_ratio,
        "auc_relative": auc_rel,
        "energy_at_max_power_j": energy_at_max,
    }

def rank_configs(configs: List[Dict[str, Any]]) -> Dict[str, Any]:
    usable = [c for c in configs if c]
    def safe_min(metric):
        vals = [c for c in usable if c.get(metric)==c.get(metric)]
        return min(vals, key=lambda x: x[metric]) if vals else None
    best_fast_at_max = safe_min("max_power_median_time_ms")
    best_fastest_any = safe_min("fastest_median_time_ms")
    best_scaling = safe_min("scaling_ratio")
    best_auc = safe_min("auc_relative")
    best_energy_max = safe_min("energy_at_max_power_j")
    comp_metrics = []
    for c in usable:
        fields = ["max_power_median_time_ms","scaling_ratio","auc_relative"]
        if any(c.get(f)!=c.get(f) for f in fields):
            continue
        comp_metrics.append(c)
    def norm_field(field):
        vals = [c[field] for c in comp_metrics]
        mn, mx = min(vals), max(vals)
        span = mx - mn if mx > mn else 1.0
        return {c["config"]: (c[field]-mn)/span for c in comp_metrics}
    if comp_metrics:
        nf_time = norm_field("max_power_median_time_ms")
        nf_scal = norm_field("scaling_ratio")
        nf_auc = norm_field("auc_relative")
        for c in comp_metrics:
            c["composite_score"] = nf_time[c["config"]] + nf_scal[c["config"]] + nf_auc[c["config"]]
        best_composite = min(comp_metrics, key=lambda x: x["composite_score"])
    else:
        best_composite = None
    return {
        "best": {
            "fast_at_max": best_fast_at_max,
            "fastest_any_cap": best_fastest_any,
            "scaling": best_scaling,
            "auc_relative": best_auc,
            "energy_at_max_power": best_energy_max,
            "composite": best_composite
        }
    }

def main():
    ap = argparse.ArgumentParser(description="Analyze split configuration folders for per-powercap performance & energy (Pareto + rankings).")
    ap.add_argument("--root", required=True, help="Root directory z konfiguracjami (np. logs_analyzed/qs_split)")
    ap.add_argument("--out", help="Katalog wyjściowy (domyślnie <root>/__summary__)")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"Root nie istnieje: {root}")
        return 1
    out_dir = Path(args.out).resolve() if args.out else root / "__summary__"
    out_dir.mkdir(parents=True, exist_ok=True)

    configs_data: List[Dict[str, Any]] = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        agg = d / "aggregated_measurements.csv"
        if agg.exists():
            res = analyze_config(d)
            if res:
                configs_data.append(res)
                (out_dir / f"{d.name}.pareto.json").write_text(json.dumps({
                    "config": d.name,
                    "pareto_points": res["pareto_points"],
                    "best_tradeoff": res["best_pareto_tradeoff"]
                }, indent=2), encoding="utf-8")
                sc = res.get("size_class")
                if sc in ("S","M"):
                    (out_dir / f"{d.name}.pareto.{sc}.json").write_text(json.dumps({
                        "config": d.name,
                        "size_class": sc,
                        "pareto_points": res["pareto_points"],
                        "best_tradeoff": res["best_pareto_tradeoff"]
                    }, indent=2), encoding="utf-8")

    (out_dir / "per_config_summary.json").write_text(json.dumps(configs_data, indent=2), encoding="utf-8")
    by_size = {"S": [c for c in configs_data if c.get("size_class") == "S"],
               "M": [c for c in configs_data if c.get("size_class") == "M"]}
    for sc, lst in by_size.items():
        (out_dir / f"per_config_summary.{sc}.json").write_text(json.dumps(lst, indent=2), encoding="utf-8")

    fieldnames = [
        "config","max_power","min_power",
        "max_power_median_time_ms","min_power_median_time_ms",
        "fastest_median_time_ms","scaling_ratio","auc_relative",
        "energy_at_max_power_j",
        "fastest_cap","lowest_energy_cap",
        "fastest_cap_median_time_ms","lowest_energy_median_j",
        "best_pareto_tradeoff_power_cap_w","best_pareto_tradeoff_median_time_ms",
        "best_pareto_tradeoff_median_energy_j","best_pareto_tradeoff_score"
    ]
    with (out_dir / "per_config_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for c in configs_data:
            bp = c.get("best_pareto_tradeoff") or {}
            w.writerow({
                "config": c["config"],
                "max_power": c["max_power"],
                "min_power": c["min_power"],
                "max_power_median_time_ms": c["max_power_median_time_ms"],
                "min_power_median_time_ms": c["min_power_median_time_ms"],
                "fastest_median_time_ms": c["fastest_median_time_ms"],
                "scaling_ratio": c["scaling_ratio"],
                "auc_relative": c["auc_relative"],
                "energy_at_max_power_j": c["energy_at_max_power_j"],
                "fastest_cap": c["fastest_cap"],
                "lowest_energy_cap": c["lowest_energy_cap"],
                "fastest_cap_median_time_ms": c["fastest_cap_median_time_ms"],
                "lowest_energy_median_j": c["lowest_energy_median_j"],
                "best_pareto_tradeoff_power_cap_w": bp.get("power_cap_w"),
                "best_pareto_tradeoff_median_time_ms": bp.get("median_time_ms"),
                "best_pareto_tradeoff_median_energy_j": bp.get("median_energy_j"),
                "best_pareto_tradeoff_score": bp.get("tradeoff_score"),
            })
    for sc, lst in by_size.items():
        with (out_dir / f"per_config_metrics.{sc}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames + ["size_class","dataset_size"])
            w.writeheader()
            for c in lst:
                bp = c.get("best_pareto_tradeoff") or {}
                w.writerow({
                    "config": c["config"],
                    "max_power": c["max_power"],
                    "min_power": c["min_power"],
                    "max_power_median_time_ms": c["max_power_median_time_ms"],
                    "min_power_median_time_ms": c["min_power_median_time_ms"],
                    "fastest_median_time_ms": c["fastest_median_time_ms"],
                    "scaling_ratio": c["scaling_ratio"],
                    "auc_relative": c["auc_relative"],
                    "energy_at_max_power_j": c["energy_at_max_power_j"],
                    "fastest_cap": c["fastest_cap"],
                    "lowest_energy_cap": c["lowest_energy_cap"],
                    "fastest_cap_median_time_ms": c["fastest_cap_median_time_ms"],
                    "lowest_energy_median_j": c["lowest_energy_median_j"],
                    "best_pareto_tradeoff_power_cap_w": bp.get("power_cap_w"),
                    "best_pareto_tradeoff_median_time_ms": bp.get("median_time_ms"),
                    "best_pareto_tradeoff_median_energy_j": bp.get("median_energy_j"),
                    "best_pareto_tradeoff_score": bp.get("tradeoff_score"),
                    "size_class": c.get("size_class"),
                    "dataset_size": c.get("dataset_size"),
                })

    global_rank = rank_configs(configs_data)
    (out_dir / "global_best.json").write_text(json.dumps(global_rank, indent=2), encoding="utf-8")
    for sc, lst in by_size.items():
        if lst:
            (out_dir / f"global_best.{sc}.json").write_text(json.dumps(rank_configs(lst), indent=2), encoding="utf-8")

    print(f"Gotowe. Wyniki w: {out_dir}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())