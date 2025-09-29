import argparse
import os
import sys
from cpu_info import CPUInfo
from test_plan import TestPlanParser

SCRIPT_DIR = "scripts/experiments/"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run sorting algorithm experiments")
    parser.add_argument("json_file", help="Path to the test plan JSON file")
    parser.add_argument("--is-server-cpu", action="store_true", 
                       help="Indicate if this is a server CPU (Xeon) without P/E cores")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.json_file):
        print(f"Error: Test plan file '{args.json_file}' not found in {SCRIPT_DIR}.")
        sys.exit(1)

    
    cpu_info = CPUInfo()
    print(cpu_info)

    test_plan_parallel= TestPlanParser(cpu_info.num_logical_processors, args.json_file)
    if args.is_server_cpu:
        test_plan_parallel.set_cpu_info(cpu_info, is_server_cpu=True)
    else:
        test_plan_parallel.set_cpu_info(cpu_info)
    test_plan_parallel.load_test_plan()

    print(test_plan_parallel)
    test_plan_parallel.print_all_combinations("table")
    test_plan_parallel.print_combinations_summary()

    test_plan_parallel.run_experiments()
