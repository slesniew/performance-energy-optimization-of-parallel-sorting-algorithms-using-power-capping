import psutil
import os

class CPUInfo:
    def __init__(self):
        self.num_physical_cores = psutil.cpu_count(logical=False)
        self.num_logical_processors = psutil.cpu_count(logical=True)
        self.num_efficiency_cores = 0
        self.num_performance_cores = 0
        self.max_power_uw = 0
        self._detect_cores()
        self._detect_max_power()

    def __str__(self):
        summary = (
            f"Total Cores: {self.num_physical_cores}\n"
            f"Total Threads: {self.num_logical_processors}\n"
            f"# of Performance-cores: {self.num_performance_cores}\n"
            f"# of Efficient-cores: {self.num_efficiency_cores}\n"
            f"Hybrid Architecture: {self.num_efficiency_cores > 0}\n"
        )
        return summary

    def _detect_cores(self):
        try:
            atom_path = "/sys/devices/cpu_atom/cpus"
            core_path = "/sys/devices/cpu_core/cpus"
            
            if os.path.exists(atom_path) and os.path.exists(core_path):
                with open(atom_path, 'r') as f:
                    atom_cpus = f.read().strip()
                
                with open(core_path, 'r') as f:
                    core_cpus = f.read().strip()
                
                self.num_efficiency_cores = self._count_cpus_in_range(atom_cpus)
                self.num_performance_cores = int(self._count_cpus_in_range(core_cpus)/2)

        except Exception as e:
            print(f"Error reading sysfs: {e}")

    def _detect_max_power(self):
        try:
            max_power_path = "/sys/class/powercap/intel-rapl/intel-rapl:0/constraint_0_max_power_uw"
            
            if os.path.exists(max_power_path):
                with open(max_power_path, 'r') as f:
                    self.max_power_uw = int(f.read().strip())
            else:
                current_limit_path = "/sys/class/powercap/intel-rapl/intel-rapl:0/constraint_0_power_limit_uw"
                if os.path.exists(current_limit_path):
                    with open(current_limit_path, 'r') as f:
                        self.max_power_uw = int(f.read().strip())
                    print("Warning: Using current power limit as max power (max_power_uw not available)")
                else:
                    print("Warning: Intel RAPL not available - max power unknown")
                    self.max_power_uw = 0
                    
        except Exception as e:
            print(f"Error reading RAPL max power: {e}")
            self.max_power_uw = 0

    def _count_cpus_in_range(self, cpu_range_str):
        if not cpu_range_str:
            return 0
        
        count = 0
        ranges = cpu_range_str.split(',')
        for cpu_range in ranges:
            cpu_range = cpu_range.strip()
            if '-' in cpu_range:
                start, end = map(int, cpu_range.split('-'))
                count += (end - start + 1)
            else:
                count += 1
        return count