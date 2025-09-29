#ifndef TESTS_HPP
#define TESTS_HPP

#include "utility.hpp"
#include "quicksort.hpp"
#include "mergesort.hpp"
#include "radixsort.hpp"
#include "countingsort.hpp"
#include "bitonicsort.hpp"

void runOne(std::vector<int>& v, std::vector<int>& input, std::string sort_name)
    {
        std::function<void(std::vector<int>&)> sort;

        if (sort_name == "qs") {
            sort = [](std::vector<int>& v) { quicksort(v); };
        } else if (sort_name == "qs_parallel") {
            sort = [](std::vector<int>& v) { quicksort_parallel(v); };
        } else if (sort_name == "qs_parallel_cutoff") {
            sort = [](std::vector<int>& v) { quicksort_parallel_cutoff(v); };
        } else if (sort_name == "qs_x86_simd") {
            sort = [](std::vector<int>& v) { quicksort_x86_simd(v);};
            #ifdef XSS_USE_OPENMP
                sort_name = "qs_parallel_x86_simd";
            #endif // XSS_USE_OPENMP
        } else if (sort_name == "stl") {
            sort = [](std::vector<int>& v) { std::sort(v.begin(), v.end()); };
        } else if (sort_name == "ms") {
            sort = [](std::vector<int>& v) { mergesort(v); };
        } else if (sort_name == "ms_parallel") {
            sort = [](std::vector<int>& v) { mergesort_parallel(v); };
        } else if (sort_name == "rs") {
            sort = [](std::vector<int>& v) { radixsort(v); };
        } else if (sort_name == "rs_parallel") {
            sort = [](std::vector<int>& v) { radixsort_parallel(v); };
        } else if (sort_name == "cs") {
            sort = [](std::vector<int>& v) { countingsort(v); };
        } else if (sort_name == "cs_parallel") {
            sort = [](std::vector<int>& v) { countingsort_parallel(v); };
        } else if (sort_name == "bs") {
            sort = [](std::vector<int>& v) { bitonicsort(v); };
        } else if (sort_name == "bs_parallel") {
            sort = [](std::vector<int>& v) { bitonicsort_parallel(v); };
        }

    using ms = std::chrono::duration<double, std::milli>;
                int runCount = 10;
                if (sort_name == "bs_parallel")
                {
                        runCount = 2;
                }
        std::vector<ms> executionTime(static_cast<size_t>(runCount));
        std::vector<double> energyJ(static_cast<size_t>(runCount), 0.0);
        std::cout<< "Running " << sort_name << " " <<  runCount << " times\n";
        bool energy_ok_global = true;
        for(int i = 0; i < runCount; i++)
        {
            auto [ok_before, e_before] = Utility::readPackageEnergyUJ();
            executionTime[i] = Utility::measureExecutionTime(sort_name,
                                [&]() {
                                    sort(v);
                                });
            auto [ok_after, e_after] = Utility::readPackageEnergyUJ();

            bool energy_ok = ok_before && ok_after;
            if (energy_ok) {
                if (e_after >= e_before)
                    energyJ[i] = (e_after - e_before) / 1e6;
                else
                    energyJ[i] = ((std::numeric_limits<uint64_t>::max() - e_before) + e_after + 1) / 1e6;
            } else {
                energy_ok_global = false;
                energyJ[i] = 0.0;
            }

            Utility::log_energy_sample(sort_name, energyJ[i], energy_ok);

            if (Utility::debug_mode) {
                Utility::validateSort(v);
            }
            v.assign(input.begin(), input.end());
        }
        ms total = std::accumulate(executionTime.begin(), executionTime.end(), ms(0));
        ms mean = total / runCount;
        auto executionTimeComparator = [](const ms& a, const ms& b) { return a.count() < b.count(); };
        auto minIt = std::min_element(executionTime.begin(), executionTime.end(),
                                  executionTimeComparator);
        auto maxIt = std::max_element(executionTime.begin(), executionTime.end(),
                                  executionTimeComparator);
        ms min = *minIt;
        ms max = *maxIt;
        ms uncertainty = (max - min) / 2;

        std::cout << "Mean: " << mean.count() << " ms\n";
        std::cout << "Uncertainty: " << uncertainty.count() << " ms\n";
        if (energy_ok_global) {
            double totalE = std::accumulate(energyJ.begin(), energyJ.end(), 0.0);
            double meanE = totalE / runCount;
            double minE = *std::min_element(energyJ.begin(), energyJ.end());
            double maxE = *std::max_element(energyJ.begin(), energyJ.end());
            std::cout << "Energy per run (J):";
            for (int i = 0; i < runCount; ++i) std::cout << " " << energyJ[i];
            std::cout << "\nMean energy: " << meanE << " J (min " << minE << " J, max " << maxE << " J)\n";
        } else {
            std::cout << "Energy: not available (set ENERGY_FILE env var or ensure RAPL sysfs present)\n";
        }
    }

    void runAll(std::vector<int>& v, std::vector<int>& input)
    {
        Utility::measureExecutionTime("quicksort", 
        [&]() {
            quicksort(v);
        });
        if (Utility::debug_mode) {
            Utility::validateSort(v);
        }
        v.assign(input.begin(), input.end());

        Utility::measureExecutionTime("quicksort_parallel", 
        [&]() {
            quicksort_parallel(v);
        });
        if (Utility::debug_mode) {
            Utility::validateSort(v);
        }
        v.assign(input.begin(), input.end());

        Utility::measureExecutionTime("quicksort_parallel_cutoff", 
        [&]() {
            quicksort_parallel_cutoff(v);
        });
        if (Utility::debug_mode) {
            Utility::validateSort(v);
        }
        v.assign(input.begin(), input.end());

        std::string quicksort_x86_simd_name = "quicksort_x86_simd";
        #ifdef XSS_USE_OPENMP
            quicksort_x86_simd_name = "qs_parallel_x86_simd";
        #endif // XSS_USE_OPENMP
        Utility::measureExecutionTime(quicksort_x86_simd_name, 
        [&]() {
            quicksort_x86_simd(v);
        });
        if (Utility::debug_mode) {
            Utility::validateSort(v);
        }
        v.assign(input.begin(), input.end());

        Utility::measureExecutionTime("std::sort", 
        [&]() {
            std::sort(v.begin(), v.end());
        });
        if (Utility::debug_mode) {
            Utility::validateSort(v);
        }
        v.assign(input.begin(), input.end());

        Utility::measureExecutionTime("mergesort", 
        [&]() {
            mergesort(v);
        });
        if (Utility::debug_mode) {
            Utility::validateSort(v);
        }
        v.assign(input.begin(), input.end());

        Utility::measureExecutionTime("mergesort_parallel", 
        [&]() {
            mergesort_parallel(v);
        });
        if (Utility::debug_mode) {
            Utility::validateSort(v);
        }
        v.assign(input.begin(), input.end());

        Utility::measureExecutionTime("radixsort", 
        [&]() {
            radixsort(v);
        });
        if (Utility::debug_mode) {
            Utility::validateSort(v);
        }
        v.assign(input.begin(), input.end());

        Utility::measureExecutionTime("radixsort_parallel", 
        [&]() {
            radixsort_parallel(v);
        });
        if (Utility::debug_mode) {
            Utility::validateSort(v);
        }
        v.assign(input.begin(), input.end());

        Utility::measureExecutionTime("countingsort", 
        [&]() {
            countingsort(v);
        });
        if (Utility::debug_mode) {
            Utility::validateSort(v);
        }
        v.assign(input.begin(), input.end());

        Utility::measureExecutionTime("countingsort_parallel", 
        [&]() {
            countingsort_parallel(v);
        });
        if (Utility::debug_mode) {
            Utility::validateSort(v);
        }
        v.assign(input.begin(), input.end());

        Utility::measureExecutionTime("bitonicsort", 
        [&]() {
            bitonicsort(v);
        });
        if (Utility::debug_mode) {
            Utility::validateSort(v);
        }
        v.assign(input.begin(), input.end());

        Utility::measureExecutionTime("bitonicsort_parallel", 
        [&]() {
            bitonicsort_parallel(v);
        });
        if (Utility::debug_mode) {
            Utility::validateSort(v);
        }
        v.assign(input.begin(), input.end());
    }

#endif //TESTS_HPP