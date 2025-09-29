#!/usr/bin/env python3
import json
import os
import argparse
from typing import List

DEFAULT_CLUSTER_NODES = [f"des{n:02d}" for n in range(1, 17)]  # des01..des16


def parse_args():
    p = argparse.ArgumentParser(
        description="Split a large parallel sorting test plan into per-node sub plans."
    )
    p.add_argument("--plan", required=True, help="Input JSON test plan file")
    p.add_argument("--output-dir", required=True, help="Directory to write split plans")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--num-nodes",
        type=int,
        help="Number of nodes to use (taken from ordered cluster list after exclusions)",
    )
    group.add_argument(
        "--nodes",
        help="Explicit comma-separated node list (e.g. des01,des02,des05)",
    )
    p.add_argument(
        "--exclude",
        default="",
        help="Comma-separated nodes to exclude (applied before selection)",
    )
    p.add_argument(
        "--cluster",
        default="",
        help="Override full cluster node list (comma-separated). Default: des01..des16",
    )
    p.add_argument(
        "--allow-empty",
        action="store_true",
        help="Generate empty split files for nodes receiving no threads",
    )
    p.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose logging"
    )
    return p.parse_args()


def select_nodes(args) -> List[str]:
    cluster = (
        [n.strip() for n in args.cluster.split(",") if n.strip()]
        if args.cluster
        else DEFAULT_CLUSTER_NODES
    )
    excl = {n.strip() for n in args.exclude.split(",") if n.strip()}
    cluster = [n for n in cluster if n not in excl]

    if args.nodes:
        requested = [n.strip() for n in args.nodes.split(",") if n.strip()]
        missing = [n for n in requested if n not in cluster]
        if missing:
            raise SystemExit(
                f"Requested nodes not available after exclusions: {', '.join(missing)}"
            )
        return requested

    if args.num_nodes < 1:
        raise SystemExit("--num-nodes must be >= 1")
    if args.num_nodes > len(cluster):
        raise SystemExit(
            f"--num-nodes ({args.num_nodes}) exceeds available nodes ({len(cluster)})"
        )
    return cluster[: args.num_nodes]


def even_split(items: List[int], k: int) -> List[List[int]]:
    n = len(items)
    if k == 0:
        return []
    base = n // k
    rem = n % k
    out = []
    idx = 0
    for i in range(k):
        take = base + (1 if i < rem else 0)
        out.append(items[idx: idx + take])
        idx += take
    return out


def main():
    args = parse_args()

    with open(args.plan, "r") as f:
        plan = json.load(f)

    try:
        sorting_algorithms = plan["sorting_algorithms"]["parallel"]
        threads = plan["threads"]
        input_sizes = plan["input_size"]
    except KeyError as e:
        raise SystemExit(f"Missing key in input plan: {e}")

    if not isinstance(threads, list) or not threads:
        raise SystemExit("Plan 'threads' must be a non-empty list")

    nodes = select_nodes(args)
    k = len(nodes)

    if args.verbose:
        print(f"Selected nodes: {nodes}")
        print(f"Threads count: {len(threads)}")

    thread_splits = even_split(threads, k)

    os.makedirs(args.output_dir, exist_ok=True)

    generated = 0
    for node, node_threads in zip(nodes, thread_splits):
        node_num_part = node[-2:]  # assumes desXX naming
        filename = f"split_test_plan_{node_num_part}.json"
        path = os.path.join(args.output_dir, filename)

        if not node_threads and not args.allow_empty:
            if args.verbose:
                print(f"{node}: no threads assigned (skipping)")
            continue

        node_plan = {
            "sorting_algorithms": {"parallel": sorting_algorithms},
            "threads": node_threads,
            "cores_type": plan.get("cores_type"),
            "input_size": input_sizes,
            "input_type": plan.get("input_type"),
            "thread_affinity": plan.get("thread_affinity"),
        }

        with open(path, "w") as f:
            json.dump(node_plan, f, indent=4)

        generated += 1
        print(f"{node}: wrote {path} (threads: {len(node_threads)})")

    if generated == 0:
        raise SystemExit("No split files generated (all nodes received zero threads?)")

    print(f"Generated {generated} split plan(s) in {args.output_dir}")


if __name__ == "__main__":
    main()