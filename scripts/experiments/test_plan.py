import json
import os
from typing import Dict, List, Any
from dataclasses import dataclass
from cpu_info import CPUInfo
import subprocess
import datetime
import shutil
import time
from io import StringIO
import sys

@dataclass
class TestPlan:
    sorting_algorithms: Dict[str, List[str]]
    threads: List[str]
    cores_type: List[str]
    input_size: List[str]
    input_type: List[str]
    thread_affinity: List[str] = None

class TestPlanParser:    
    def __init__(self, logical_processors: int, json_file_path: str = None):
        self.json_file_path = json_file_path
        self.logical_processors = logical_processors
        self.thread_count = None
        self.test_plan = None
        self.test_combinations = []
        self.cpu_info = None
        self.experiment_log_dir = None
        self.is_server_cpu = False

    # INFO

    def __str__(self):
        if not self.test_plan:
            raise RuntimeError("Test plan not loaded. Call load_test_plan() first.")
        
        summary = []
        summary.append(f"\n=== {self.json_file_path} ===")
        summary.append(f"Parallel Algorithms: {len(self.test_plan.sorting_algorithms.get('parallel', []))}")
        summary.append(f"Single-threaded Algorithms: {len(self.test_plan.sorting_algorithms.get('single_threaded', []))}")
        summary.append(f"Thread Configurations: {len(self.test_plan.threads)}")
        summary.append(f"Core Type Configurations: {len(self.test_plan.cores_type)}")
        summary.append(f"Input Sizes: {len(self.test_plan.input_size)}")
        summary.append(f"Input Types: {len(self.test_plan.input_type)}")
        
        total_combinations = (
            len(self.get_all_algorithms()) *
            len(self.test_plan.threads) *
            len(self.test_plan.cores_type) *
            len(self.test_plan.input_size) *
            len(self.test_plan.input_type)
        )
        summary.append(f"Total Test Combinations: {total_combinations}")
        return "\n".join(summary)

    def get_all_algorithms(self) -> List[str]:
        if not self.test_plan:
            raise RuntimeError("Test plan not loaded. Call load_test_plan() first.")
        all_algorithms = []
        all_algorithms.extend(self.test_plan.sorting_algorithms.get('parallel', []))
        all_algorithms.extend(self.test_plan.sorting_algorithms.get('single_threaded', []))
        return all_algorithms
    
    def get_parallel_algorithms(self) -> List[str]:
        if not self.test_plan:
            raise RuntimeError("Test plan not loaded. Call load_test_plan() first.")
        return self.test_plan.sorting_algorithms.get('parallel', [])
    
    def get_single_threaded_algorithms(self) -> List[str]:
        if not self.test_plan:
            raise RuntimeError("Test plan not loaded. Call load_test_plan() first.")
        
        return self.test_plan.sorting_algorithms.get('single_threaded', [])

    def get_thread_counts(self, total_cores: int) -> List[int]:
        if not self.test_plan:
            raise RuntimeError("Test plan not loaded. Call load_test_plan() first.")
        
        thread_counts = []
        for thread_spec in self.test_plan.threads:
            count = self.convert_thread_percentage_to_count(thread_spec, total_cores)
            thread_counts.append(count)
        return thread_counts

    def _get_max_threads_for_core_type(self, core_type: str) -> int:
        if not self.cpu_info:
            raise RuntimeError("CPU info not set. Call set_cpu_info() first.")

        if core_type == "ONLY EFFICIENT":
            return self.cpu_info.num_efficiency_cores
        elif core_type == "ONLY PERFORMANCE":
            return self.cpu_info.num_performance_cores * 2
        elif core_type == "50% PERFORMANCE":
            p_cores = max(1, int(self.cpu_info.num_performance_cores * 0.5)) * 2
            return p_cores
        elif core_type == "25% EFFICIENT 75% PERFORMANCE":
            e_cores = max(1, int(self.cpu_info.num_efficiency_cores * 0.25))
            p_cores = max(1, int(self.cpu_info.num_performance_cores * 0.75)) * 2
            return e_cores + p_cores
        elif core_type == "50% EFFICIENT 50% PERFORMANCE":
            e_cores = max(1, int(self.cpu_info.num_efficiency_cores * 0.5))
            p_cores = max(1, int(self.cpu_info.num_performance_cores * 0.5)) * 2
            return e_cores + p_cores
        elif core_type == "75% EFFICIENT 25% PERFORMANCE":
            e_cores = max(1, int(self.cpu_info.num_efficiency_cores * 0.75))
            p_cores = max(1, int(self.cpu_info.num_performance_cores * 0.25)) * 2
            return e_cores + p_cores
        elif core_type == "100% EFFICIENT 100% PERFORMANCE":
            return self.cpu_info.num_efficiency_cores + (self.cpu_info.num_performance_cores * 2)
        else:
            raise ValueError(f"Unknown core type: {core_type}")
        
    def get_test_combinations(self) -> List[Dict[str, Any]]:
        if not self.test_combinations:
            return self._generate_test_combinations()
        return self.test_combinations

    def print_all_combinations(self, format_type: str = "table") -> None:
        combinations = self.get_test_combinations()
        
        if not combinations:
            print("No test combinations available.")
            return
        
        print(f"\n=== All Test Combinations ({len(combinations)} total) ===")
        
        if format_type == "table":
            self._print_combinations_table(combinations)
        elif format_type == "list":
            self._print_combinations_list(combinations)
        elif format_type == "compact":
            self._print_combinations_compact(combinations)
        else:
            raise ValueError("format_type must be 'table', 'list', or 'compact'")
        
    def _print_combinations_table(self, combinations: List[Dict[str, Any]]) -> None:
        headers = ['#', 'Algorithm', 'Threads', 'Core Type', 'Input Size', 'Input Type', 'Thread Affinity']
        widths = [len(h) for h in headers]
        
        for i, combo in enumerate(combinations):
            widths[0] = max(widths[0], len(str(i + 1)))
            widths[1] = max(widths[1], len(combo['algorithm']))
            widths[2] = max(widths[2], len(str(combo['threads'])))
            widths[3] = max(widths[3], len(combo['core_type']))
            widths[4] = max(widths[4], len(combo['input_size']))
            widths[5] = max(widths[5], len(combo['input_type']))
            widths[6] = max(widths[6], len(combo.get('thread_affinity', 'close')))
        
        header_row = " | ".join(h.ljust(w) for h, w in zip(headers, widths))
        print(header_row)
        print("-" * len(header_row))
        
        for i, combo in enumerate(combinations):
            row = [
                str(i + 1).ljust(widths[0]),
                combo['algorithm'].ljust(widths[1]),
                str(combo['threads']).ljust(widths[2]),
                combo['core_type'].ljust(widths[3]),
                combo['input_size'].ljust(widths[4]),
                combo['input_type'].ljust(widths[5]),
                combo.get('thread_affinity', 'close').ljust(widths[6])
            ]
            print(" | ".join(row))
    
    def print_combinations_summary(self) -> None:
        combinations = self.get_test_combinations()
        
        if not combinations:
            print("No test combinations available.")
            return
        
        print(f"\n=== Test Combinations Summary ===")
        print(f"Total combinations: {len(combinations)}")
        
        algo_counts = {}
        thread_counts = {}
        core_counts = {}
        size_counts = {}
        type_counts = {}
        affinity_counts = {}
        
        for combo in combinations:
            algo_counts[combo['algorithm']] = algo_counts.get(combo['algorithm'], 0) + 1
            thread_counts[combo['threads']] = thread_counts.get(combo['threads'], 0) + 1
            core_counts[combo['core_type']] = core_counts.get(combo['core_type'], 0) + 1
            size_counts[combo['input_size']] = size_counts.get(combo['input_size'], 0) + 1
            type_counts[combo['input_type']] = type_counts.get(combo['input_type'], 0) + 1
            affinity = combo.get('thread_affinity', 'close')
            affinity_counts[affinity] = affinity_counts.get(affinity, 0) + 1
        
        print(f"\nBy Algorithm:")
        for algo, count in sorted(algo_counts.items()):
            print(f"  {algo}: {count}")
        
        print(f"\nBy Thread Count:")
        for threads, count in sorted(thread_counts.items()):
            print(f"  {threads}: {count}")
        
        print(f"\nBy Core Type:")
        for core, count in sorted(core_counts.items()):
            print(f"  {core}: {count}")
        
        print(f"\nBy Input Size:")
        for size, count in sorted(size_counts.items()):
            print(f"  {size}: {count}")
        
        print(f"\nBy Input Type:")
        for itype, count in sorted(type_counts.items()):
            print(f"  {itype}: {count}")
            
        print(f"\nBy Thread Affinity:")
        for affinity, count in sorted(affinity_counts.items()):
            print(f"  {affinity}: {count}")

# UTILITY

    def load_test_plan(self, json_file_path: str = None) -> TestPlan:
        file_path = json_file_path or self.json_file_path
        
        if not file_path:
            raise ValueError("No JSON file path provided")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Test plan file not found: {file_path}")
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            required_fields = ['sorting_algorithms', 'threads', 'cores_type', 'input_size', 'input_type', 'thread_affinity']
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field in test plan: {field}")
            
            self.test_plan = TestPlan(
                sorting_algorithms=data['sorting_algorithms'],
                threads=data['threads'],
                cores_type=data['cores_type'],
                input_size=data['input_size'],
                input_type=data['input_type'],
                thread_affinity=data['thread_affinity']
            )
            self.thread_count = self.get_thread_counts(self.logical_processors)
            self._generate_test_combinations()

            return self.test_plan
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")
        except Exception as e:
            raise RuntimeError(f"Error loading test plan: {e}")
    
    def convert_thread_percentage_to_count(self, thread_spec: str, total_cores: int) -> int:
        if thread_spec.endswith('%'):
            percentage = int(thread_spec[:-1])
            return max(1, int(total_cores * percentage / 100))
        else:
            return int(thread_spec)
        
    def _adjust_thread_count_for_core_type(self, thread_count: int, core_type: str) -> int:
        max_threads = self._get_max_threads_for_core_type(core_type)
        return min(thread_count, max_threads)
    
    def _generate_test_combinations(self) -> List[Dict[str, Any]]:
        if not self.test_plan:
            raise RuntimeError("Test plan not loaded. Call load_test_plan() first.")
        
        if not self.cpu_info:
            raise RuntimeError("CPU info not set. Call set_cpu_info() first.")
        
        combinations = []
        all_algorithms = self.get_all_algorithms()
        thread_counts = self.get_thread_counts(self.logical_processors)

        for algorithm in all_algorithms:
            for thread_count in thread_counts:
                for core_type in self.test_plan.cores_type:
                    adjusted_thread_count = self._adjust_thread_count_for_core_type(thread_count, core_type)
                    
                    for input_size in self.test_plan.input_size:
                        for input_type in self.test_plan.input_type:
                            for affinity in self.test_plan.thread_affinity:
                                combination = {
                                    'algorithm': algorithm,
                                    'threads': adjusted_thread_count,
                                    'core_type': core_type,
                                    'input_size': input_size,
                                    'input_type': input_type,
                                    'thread_affinity': affinity
                                }
                                combinations.append(combination)
        
        self.test_combinations = combinations
        return combinations

    def set_cpu_info(self, cpu_info: 'CPUInfo', is_server_cpu: bool = False) -> None:
        if not isinstance(cpu_info, CPUInfo):
            raise ValueError("cpu_info must be an instance of CPUInfo")
        self.cpu_info = cpu_info
        self.is_server_cpu = is_server_cpu

    def _input_class_to_size(self, input_size: str) -> int:
        if input_size == "S":
            return 2**27 
        elif input_size == "M":
            return 2**29
        elif input_size == "L":
            return 2**31
        elif input_size == "XL":
            return 2**33
        
    def _taskset_args_for_core_type(self, core_type: str) -> List[str]:
        if not self.cpu_info:
            raise RuntimeError("CPU info not set. Call set_cpu_info() first.")
        
        p_core_end = (self.cpu_info.num_performance_cores * 2) - 1
        e_core_start = self.cpu_info.num_performance_cores * 2
        e_core_end = e_core_start + self.cpu_info.num_efficiency_cores - 1
        
        if core_type == "ONLY EFFICIENT":
            return [f"{e_core_start}-{e_core_end}"]
        elif core_type == "ONLY PERFORMANCE":
            return [f"0-{p_core_end}"]
        elif core_type == "50% PERFORMANCE":
            p_cores_to_use = max(1, int(self.cpu_info.num_performance_cores * 0.5)) * 2
            return [f"0-{p_cores_to_use - 1}"]
        elif core_type == "25% EFFICIENT 75% PERFORMANCE":
            e_cores_to_use = max(1, int(self.cpu_info.num_efficiency_cores * 0.25))
            p_cores_to_use = max(1, int(self.cpu_info.num_performance_cores * 0.75)) * 2
            p_range = f"0-{p_cores_to_use - 1}"
            e_range = f"{e_core_start}-{e_core_start + e_cores_to_use - 1}"
            return [f"{p_range},{e_range}"]
        elif core_type == "50% EFFICIENT 50% PERFORMANCE":
            e_cores_to_use = max(1, int(self.cpu_info.num_efficiency_cores * 0.5))
            p_cores_to_use = max(1, int(self.cpu_info.num_performance_cores * 0.5)) * 2
            p_range = f"0-{p_cores_to_use - 1}"
            e_range = f"{e_core_start}-{e_core_start + e_cores_to_use - 1}"
            return [f"{p_range},{e_range}"]
        elif core_type == "75% EFFICIENT 25% PERFORMANCE":
            e_cores_to_use = max(1, int(self.cpu_info.num_efficiency_cores * 0.75))
            p_cores_to_use = max(1, int(self.cpu_info.num_performance_cores * 0.25)) * 2
            p_range = f"0-{p_cores_to_use - 1}"
            e_range = f"{e_core_start}-{e_core_start + e_cores_to_use - 1}"
            return [f"{p_range},{e_range}"]
        elif core_type == "100% EFFICIENT 100% PERFORMANCE":
            p_range = f"0-{p_core_end}"
            e_range = f"{e_core_start}-{e_core_end}"
            return [f"{p_range},{e_range}"]
        else:
            raise ValueError(f"Unknown core type: {core_type}")

# EXPERIMENT

    def _prepare_experiments(self):
        repro_root = os.getcwd()
        
        logs_dir = os.path.join(repro_root, "logs")
        os.makedirs(logs_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        experiment_log_dir = os.path.join(logs_dir, timestamp)
        os.makedirs(experiment_log_dir, exist_ok=True)

        self.experiment_log_dir = experiment_log_dir

        combinations = self.get_test_combinations()
        combinations_txt_path = os.path.join(experiment_log_dir, "all_combinations.txt")
        with open(combinations_txt_path, "w") as f:
            for i, combo in enumerate(combinations, 1):
                f.write(f"{i}: {combo}\n")

        if self.json_file_path:
            shutil.copy2(self.json_file_path, os.path.join(experiment_log_dir, os.path.basename(self.json_file_path)))

        tools_split_dir = os.path.join(repro_root, "tools/split")
        
        if not os.path.exists(tools_split_dir):
            raise FileNotFoundError(f"Directory not found: {tools_split_dir}")
        
        os.chdir(tools_split_dir)

        return combinations

    def run_experiments(self):
        combinations = self._prepare_experiments()
        start_time = time.time()

        for combo in combinations:
            algorithm = combo['algorithm']
            threads = combo['threads']
            input_size = combo['input_size']
            core_type = combo['core_type']
            input_type = combo['input_type']
            thread_affinity = combo.get('thread_affinity', 'close')
            self._run_experiment(algorithm, threads, core_type, input_size, input_type, thread_affinity)

        end_time = time.time()
        elapsed = end_time - start_time

        if self.experiment_log_dir:
            time_path = os.path.join(self.experiment_log_dir, "experiment_time.txt")
            with open(time_path, "w") as f:
                f.write(f"{elapsed}\n")

    def _run_experiment(self, algorithm: str, threads: int, core_type: str, input_size: str, input_type: str, thread_affinity: str = "close"):
        taskset_args = self._taskset_args_for_core_type(core_type)
        _ = input_type # TODO
        env = os.environ.copy()
        valid_affinity_values = ["close", "spread", "master", "true", "false"]
        if thread_affinity in valid_affinity_values:
            env["OMP_PROC_BIND"] = thread_affinity
        else:
            print(f"Warning: Invalid thread_affinity value '{thread_affinity}', defaulting to 'close'")
            env["OMP_PROC_BIND"] = "close"
        
        cmd = [
            "sudo", "taskset", "--cpu-list"] + taskset_args + [
            "./build/apps/StEP/StEP",
            "./minibenchmarks/openmp/sort",
            "bench",
            algorithm,
            "--threads", str(threads),
            "--size", str(self._input_class_to_size(input_size))
            ]
        print(f"Running with OMP_PROC_BIND={env['OMP_PROC_BIND']}: {' '.join(cmd)}")
        subprocess.run(cmd, env=env, check=True)
        self._handle_after_experiment(algorithm, threads, core_type, input_size, input_type, thread_affinity)

    def _finalize_experiment(self):
        summary_lines = []
        summary_lines.append(str(self.cpu_info) if self.cpu_info else "No CPU info available.")
        summary_lines.append(str(self) if self.test_plan else "No test plan loaded.")
        
        buf = StringIO()
        sys_stdout = sys.stdout
        sys.stdout = buf
        try:
            self.print_all_combinations("table")
            self.print_combinations_summary()
        finally:
            sys.stdout = sys_stdout
        summary_lines.append(buf.getvalue())

        summary_text = "\n".join(summary_lines)
        summary_path = os.path.join(self.experiment_log_dir, "full_summary.txt")
        with open(summary_path, "w") as f:
            f.write(summary_text)

    def _handle_after_experiment(self, algorithm: str, threads: int, core_type: str, input_size: str, input_type: str, thread_affinity: str = "close"):
        cwd = os.getcwd()
        experiment_dirs = [d for d in os.listdir(cwd) if d.startswith("cpu_experiment_") and os.path.isdir(d)]
        if not experiment_dirs:
            print("No cpu_experiment_* directory found after experiment.")
            return

        experiment_dirs.sort(key=lambda d: os.path.getmtime(os.path.join(cwd, d)), reverse=True)
        latest_dir = experiment_dirs[0]
        src = os.path.join(cwd, latest_dir)

        def sanitize(val):
            return str(val).replace(" ", "_").replace("/", "_").replace("%", "pct")

        new_dir_name = f"{sanitize(algorithm)}_{sanitize(threads)}_{sanitize(core_type)}_{sanitize(input_size)}_{sanitize(input_type)}_{sanitize(thread_affinity)}"
        dst = os.path.join(self.experiment_log_dir, new_dir_name)
        
        try:
            shutil.copytree(src, dst)
            print(f"Copied experiment data from {src} to {dst}")
        except Exception as e:
            print(f"Failed to copy {src} to {dst}: {e}")
            return
        
        try:
            shutil.rmtree(src)
            print(f"Cleaned up source directory {src}")
        except Exception as e:
            print(f"Warning: Could not clean up source directory {src}: {e}")
            print("This is not critical - the experiment data was successfully copied.")