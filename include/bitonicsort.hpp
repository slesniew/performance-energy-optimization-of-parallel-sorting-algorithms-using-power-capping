#ifndef BITONICSORT_HPP
#define BITONICSORT_HPP

#include <vector>
#include <algorithm>
#include <type_traits>
#include <omp.h>

namespace detail_bitonic {
    inline bool is_power_of_two(std::size_t n) { return n && ((n & (n - 1)) == 0); }

    template <typename T>
    void bitonic_sort_sequential(std::vector<T>& a) {
        const std::size_t n = a.size();
        for (std::size_t k = 2; k <= n; k <<= 1) {
            for (std::size_t j = k >> 1; j > 0; j >>= 1) {
                for (std::size_t i = 0; i < n; ++i) {
                    std::size_t ix = i ^ j;
                    if (ix > i) {
                        bool ascending = ((i & k) == 0);
                        if ((a[i] > a[ix]) == ascending) {
                            std::swap(a[i], a[ix]);
                        }
                    }
                }
            }
        }
    }

    template <typename T>
    void bitonic_sort_parallel_impl(std::vector<T>& a) {
        const std::size_t n = a.size();
        for (std::size_t k = 2; k <= n; k <<= 1) {
            for (std::size_t j = k >> 1; j > 0; j >>= 1) {
                #pragma omp parallel for schedule(static)
                for (long long i = 0; i < static_cast<long long>(n); ++i) {
                    std::size_t ui = static_cast<std::size_t>(i);
                    std::size_t ix = ui ^ j;
                    if (ix > ui) {
                        bool ascending = ((ui & k) == 0);
                        if ((a[ui] > a[ix]) == ascending) {
                            std::swap(a[ui], a[ix]);
                        }
                    }
                }
            }
        }
    }
}

template <typename T>
void bitonicsort(std::vector<T>& vec) {
    if (vec.size() < 2) return;
    if (!detail_bitonic::is_power_of_two(vec.size())) {
        std::sort(vec.begin(), vec.end());
        return;
    }
    detail_bitonic::bitonic_sort_sequential(vec);
}

template <typename T>
void bitonicsort_parallel(std::vector<T>& vec) {
    if (vec.size() < 2) return;
    if (!detail_bitonic::is_power_of_two(vec.size())) {
        std::sort(vec.begin(), vec.end());
        return;
    }
    detail_bitonic::bitonic_sort_parallel_impl(vec);
}

#endif // BITONICSORT_HPP
