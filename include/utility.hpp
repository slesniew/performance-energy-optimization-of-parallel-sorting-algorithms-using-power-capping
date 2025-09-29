#ifndef UTILITY_HPP
#define UTILITY_HPP

#include <vector>
#include <random>
#include <utility>
#include <chrono>
#include <functional>
#include <iostream>
#include <array>
#include <fstream>
#include <iomanip>
#include <filesystem>
#include <omp.h>
#include <cstdint>
#include <atomic>
#include <fstream>
#include <cstdlib>
#include <sstream>
#include <optional>

namespace Utility{
    inline std::string log_dir_path;
    inline bool debug_mode = false;

    inline void log_energy_sample(const std::string& funcName, double joules, bool available) {
        if (log_dir_path.empty()) return;
        const std::string fileName = log_dir_path + "/" + funcName + "_energy_j.log";
        std::ofstream f(fileName, std::ios::app);
        if (!f.is_open()) return;
        if (available) {
            f << std::fixed << std::setprecision(6) << joules << " J\n";
        } else {
            f << "N/A\n";
        }
    }

    std::string detectEnergyFile() {
        const char* env = std::getenv("ENERGY_FILE");
        if (env && *env) return env;
        const char* candidates[] = {
            "/sys/class/powercap/intel-rapl:0/energy_uj",
            "/sys/class/powercap/intel-rapl:0:0/energy_uj"
        };
        for (auto p : candidates) {
            std::ifstream f(p);
            if (f.good()) return p;
        }
        return {};
    }

    std::pair<bool, uint64_t> readPackageEnergyUJ() {
        static const std::string path = detectEnergyFile();
        if (path.empty()) return {false, 0};
        std::ifstream in(path);
        if (!in) return {false, 0};
        uint64_t val = 0;
        in >> val;
        if (!in) return {false, 0};
        return {true, val};
    }

    inline void init_log_dir() {
        auto now = std::chrono::system_clock::now();
        std::time_t t = std::chrono::system_clock::to_time_t(now);
        std::tm tm = *std::localtime(&t);

        std::ostringstream oss;
        oss << "logs/"
            << std::put_time(&tm, "%Y-%m-%d_%H-%M-%S");
        log_dir_path = oss.str();
        std::filesystem::create_directories(log_dir_path);
    }


    template <typename T>
    void generateRandomInput(std::vector<T>& data, unsigned int size, std::pair<T, T> range) {
        data.resize(size);
        std::random_device rd;
        std::mt19937 generator(rd());

        if constexpr (std::is_integral_v<T>) {
            std::uniform_int_distribution<T> distribution(range.first, range.second);
            for (unsigned int i = 0; i < size; ++i) {
                data[i] = distribution(generator);
            }
        } else if constexpr (std::is_floating_point_v<T>) {
            std::uniform_real_distribution<T> distribution(range.first, range.second);
            for (unsigned int i = 0; i < size; ++i) {
                data[i] = distribution(generator);
            }
        }
    }

    template <typename Func, typename... Args>
    std::chrono::duration<double, std::milli> measureExecutionTime(const std::string& funcName, Func&& func) {
        auto start = std::chrono::high_resolution_clock::now();

        std::invoke(std::forward<Func>(func));

        auto end = std::chrono::high_resolution_clock::now();

        std::chrono::duration<double, std::milli> duration = end - start;
        std::cout << "Execution time of " << funcName << ": " << duration.count() << " ms" << std::endl;

        const std::string logFileName = log_dir_path + "/" + funcName + "_execution_times.log";
        std::ofstream logFile(logFileName, std::ios::app);
        if (logFile.is_open()) {
            logFile << duration.count() << " ms" << std::endl;
        }

        return duration;
    }

    template <typename T>
    void validateSort(std::vector<T>& data)
    {
        bool isSorted = std::is_sorted(data.begin(), data.end());
        if (isSorted) {
            std::cout << "Vector is sorted correctly\n";
        }
        else {
            std::cout << "Vector is not sorted correctly\n";
        }
    }

    void print_help() {
        std::cout << "Usage: ./sort <mode> <algorithm> [--size <N>]\n"
                << "  <mode>         : all | bench\n"
                << "  <algorithm>    :\n"
                << "      qs                - QuickSort (basic)\n"
                << "      qs_parallel       - QuickSort (parallel)\n"
                << "      qs_parallel_cutoff- QuickSort (parallel with cutoff)\n"
                << "      qs_x86_simd       - QuickSort (x86 SIMD)\n"
                << "      stl               - C++ Standard Library sort (std::sort)\n"
                << "      ms                - MergeSort (basic)\n"
                << "      ms_parallel       - MergeSort (parallel)\n"
                << "      rs                - RadixSort (basic)\n"
                << "      rs_parallel       - RadixSort (parallel)\n"
                << "      cs                - CountingSort (basic, integral types)\n"
                << "      cs_parallel       - CountingSort (parallel, integral types)\n"
                << "      bs                - BitonicSort (basic)\n"
                << "      bs_parallel       - BitonicSort (parallel)\n"
                << "  --size <N>     : (optional) number of elements to sort (default: 100000000)\n"
                << "  --threads <N>  : (optional) number of threads for parallel algorithms\n"
                << "  --debug        : (optional) validate sort results\n"
                << "  --help, -h     : Show this help message\n"
                << "\n"
                << "Examples:\n"
                << "  ./sort bench qs_parallel --size 5000000\n"
                << "  ./sort all\n"
                << "  ./sort --help\n"
                << "\n"
                << "Notes:\n"
                << "  - 'all' mode runs all algorithms in sequence.\n"
                << "  - 'bench' mode runs the selected algorithm 10 times and reports timing statistics.\n";
    }

        inline double read_current_power_cap_w() {
            if (const char* envW = std::getenv("POWER_CAP_W"); envW && *envW) {
                try {
                    return std::stod(envW);
                } catch (...) {}
            }
            auto read_uw_file = [](const std::string& path) -> std::optional<uint64_t> {
                std::ifstream f(path);
                if (!f.is_open()) return std::nullopt;
                uint64_t v=0;
                f >> v;
                if (!f) return std::nullopt;
                return v;
            };
            if (const char* envFile = std::getenv("POWER_CAP_FILE"); envFile && *envFile) {
                if (auto v = read_uw_file(envFile); v) return static_cast<double>(*v) / 1e6;
            }
            const char* pl1_candidates[] = {
                "/sys/class/powercap/intel-rapl:0/constraint_0_power_limit_uw",
                "/sys/class/powercap/intel-rapl:0:0/constraint_0_power_limit_uw"
            };
            for (auto p : pl1_candidates) {
                if (auto v = read_uw_file(p); v) return static_cast<double>(*v) / 1e6;
            }
            const char* pl2_candidates[] = {
                "/sys/class/powercap/intel-rapl:0/constraint_1_power_limit_uw",
                "/sys/class/powercap/intel-rapl:0:0/constraint_1_power_limit_uw"
            };
            for (auto p : pl2_candidates) {
                if (auto v = read_uw_file(p); v) return static_cast<double>(*v) / 1e6;
            }
            return -1.0;
    }

    void log_parameters(const std::string& mode, const std::string& algorithm, unsigned long size, int num_threads) {
        std::ofstream param_log(log_dir_path + "/parameters.log", std::ios::app);
        if (param_log.is_open()) {
            param_log << "Mode: " << mode;
            if (!algorithm.empty()) param_log << ", Algorithm: " << algorithm;
            param_log << ", Size: " << size;
            if (num_threads > 0) {
                param_log << ", Threads: " << num_threads;
            } else {
                param_log << ", Threads: all available (" << omp_get_num_procs() << ")";
            }
            double capW = read_current_power_cap_w();
            if (capW >= 0.0) {
                param_log << ", PowerCap: " << std::fixed << std::setprecision(3) << capW << " W";
            } else {
                param_log << ", PowerCap: N/A";
            }
            param_log << std::endl;
        }
    }
}

#endif // UTILITY_HPP