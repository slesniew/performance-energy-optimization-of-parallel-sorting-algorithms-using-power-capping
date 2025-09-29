#ifndef COUNTINGSORT_HPP
#define COUNTINGSORT_HPP

#include <vector>
#include <type_traits>
#include <limits>
#include <cstdint>
#include <algorithm>
#include <cstring>
#include <omp.h>

template <typename T>
static inline typename std::enable_if<std::is_unsigned<T>::value, uint32_t>::type
to_key32(T v) {
    static_assert(sizeof(T) <= 4, "This full-range counting sort supports 32-bit keys.");
    return static_cast<uint32_t>(v);
}

template <typename T>
static inline typename std::enable_if<std::is_signed<T>::value, uint32_t>::type
to_key32(T v) {
    static_assert(sizeof(T) <= 4, "This full-range counting sort supports 32-bit keys.");
    return static_cast<uint32_t>(static_cast<int32_t>(v)) ^ 0x80000000u;
}

template <typename T>
void countingsort(std::vector<T>& vec) {
    static_assert(std::is_integral<T>::value, "countingsort requires an integral type");
    if (vec.empty()) return;

    T min_val = vec[0];
    T max_val = vec[0];
    for (size_t i = 1; i < vec.size(); ++i) {
        if (vec[i] < min_val) min_val = vec[i];
        else if (vec[i] > max_val) max_val = vec[i];
    }

    using Wide = long long;
    Wide range_wide = static_cast<Wide>(max_val) - static_cast<Wide>(min_val) + 1;
    if (range_wide <= 0) return;

    const Wide MAX_RANGE = 200000000;
    if (range_wide > MAX_RANGE) {
        std::sort(vec.begin(), vec.end());
        return;
    }

    size_t range = static_cast<size_t>(range_wide);
    std::vector<size_t> counts(range, 0);

    for (auto v : vec) {
        counts[static_cast<size_t>(static_cast<Wide>(v) - static_cast<Wide>(min_val))]++;
    }

    size_t idx = 0;
    for (size_t r = 0; r < range; ++r) {
        size_t c = counts[r];
        T value = static_cast<T>(static_cast<Wide>(min_val) + static_cast<Wide>(r));
        for (size_t k = 0; k < c; ++k) vec[idx++] = value;
    }
}

template <typename T>
void countingsort_parallel_full32(std::vector<T>& a) {
    static_assert(std::is_integral<T>::value, "countingsort requires integral type");
    static_assert(sizeof(T) <= 4, "full32 counting sort supports 32-bit keys only");
    const size_t n = a.size();
    if (n < 2) return;

    constexpr unsigned K = 16;
    constexpr uint32_t WINDOW = 1u << K;
    constexpr uint32_t NBINS  = 1u << (32 - K);

    const int P = omp_get_max_threads();

    std::vector<size_t> H(static_cast<size_t>(P) * NBINS, 0);

    #pragma omp parallel
    {
        const int tid = omp_get_thread_num();
        size_t* hloc = H.data() + static_cast<size_t>(tid) * NBINS;

        #pragma omp for schedule(static)
        for (long long i = 0; i < static_cast<long long>(n); ++i) {
            uint32_t k = to_key32(a[static_cast<size_t>(i)]);
            uint32_t bin = k >> K;
            ++hloc[bin];
        }
    }

    std::vector<size_t> Htot(NBINS, 0), starts(NBINS + 1, 0);
    #pragma omp parallel for schedule(static)
    for (long long b = 0; b < static_cast<long long>(NBINS); ++b) {
        size_t s = 0;
        for (int t = 0; t < P; ++t) s += H[static_cast<size_t>(t) * NBINS + static_cast<size_t>(b)];
        Htot[static_cast<size_t>(b)] = s;
    }
    for (uint32_t b = 0; b < NBINS; ++b) starts[b + 1] = starts[b] + Htot[b];

    std::vector<size_t> thread_off(static_cast<size_t>(P) * NBINS, 0);
    std::memcpy(thread_off.data(), starts.data(), NBINS * sizeof(size_t));
    for (int t = 1; t < P; ++t) {
        size_t* prev  = thread_off.data() + static_cast<size_t>(t - 1) * NBINS;
        size_t* cur   = thread_off.data() + static_cast<size_t>(t) * NBINS;
        const size_t* hprev = H.data() + static_cast<size_t>(t - 1) * NBINS;
        #pragma omp parallel for schedule(static)
        for (long long b = 0; b < static_cast<long long>(NBINS); ++b)
            cur[static_cast<size_t>(b)] = prev[static_cast<size_t>(b)] + hprev[static_cast<size_t>(b)];
    }

    std::vector<T> tmp(n);
    #pragma omp parallel
    {
        const int tid = omp_get_thread_num();
        size_t* off = thread_off.data() + static_cast<size_t>(tid) * NBINS;

        #pragma omp for schedule(static)
        for (long long i = 0; i < static_cast<long long>(n); ++i) {
            T v = a[static_cast<size_t>(i)];
            uint32_t k = to_key32(v);
            uint32_t bin = k >> K;
            size_t pos = off[bin]++;
            tmp[pos] = v;
        }
    }

    #pragma omp parallel for schedule(static)
    for (long long bb = 0; bb < static_cast<long long>(NBINS); ++bb) {
        size_t beg = starts[static_cast<size_t>(bb)];
        size_t end = starts[static_cast<size_t>(bb) + 1];
        size_t len = end - beg;
        if (len == 0) continue;

        std::vector<size_t> cnt(WINDOW, 0);

        for (size_t i = beg; i < end; ++i) {
            uint32_t k = to_key32(tmp[i]);
            ++cnt[k & (WINDOW - 1)];
        }
        size_t run = 0;
        for (uint32_t x = 0; x < WINDOW; ++x) {
            size_t c = cnt[x];
            cnt[x] = run;
            run += c;
        }
        for (size_t i = beg; i < end; ++i) {
            T v = tmp[i];
            uint32_t k = to_key32(v);
            uint32_t idx = k & (WINDOW - 1);
            size_t pos = beg + cnt[idx]++;
            a[pos] = v;
        }
    }
}

template <typename T>
void countingsort_parallel(std::vector<T>& vec) {
    static_assert(std::is_integral<T>::value, "countingsort requires an integral type");
    if (vec.empty()) return;

    const size_t n = vec.size();

    T min_val = vec[0];
    T max_val = vec[0];
    #pragma omp parallel for reduction(min:min_val) reduction(max:max_val)
    for (long long i = 0; i < static_cast<long long>(n); ++i) {
        T v = vec[static_cast<size_t>(i)];
        if (v < min_val) min_val = v;
        if (v > max_val) max_val = v;
    }

    using Wide = long long;
    Wide range_wide = static_cast<Wide>(max_val) - static_cast<Wide>(min_val) + 1;
    if (range_wide <= 0) return;

    const Wide MAX_RANGE = 200000000;
    if (range_wide > MAX_RANGE) {
        countingsort_parallel_full32(vec);
        return;
    }

    size_t range = static_cast<size_t>(range_wide);

    int threads = omp_get_max_threads();
    std::vector<size_t> all(static_cast<size_t>(threads) * range, 0);
    #pragma omp parallel
    {
        int tid = omp_get_thread_num();
        size_t* lc = all.data() + static_cast<size_t>(tid) * range;

        #pragma omp for schedule(static)
        for (long long i = 0; i < static_cast<long long>(n); ++i) {
            auto idx = static_cast<size_t>(
                static_cast<Wide>(vec[static_cast<size_t>(i)]) - static_cast<Wide>(min_val)
            );
            ++lc[idx];
        }
    }

    std::vector<size_t> counts(range, 0);
    #pragma omp parallel for schedule(static)
    for (long long r = 0; r < static_cast<long long>(range); ++r) {
        size_t s = 0;
        for (int t = 0; t < threads; ++t) s += all[static_cast<size_t>(t) * range + static_cast<size_t>(r)];
        counts[static_cast<size_t>(r)] = s;
    }

    std::vector<size_t> starts(range, 0);
    if (range > 0) {
        size_t running = 0;
        for (size_t r = 0; r < range; ++r) {
            starts[r] = running;
            running += counts[r];
        }
    }

    std::vector<T> output(n);
    #pragma omp parallel for schedule(static)
    for (long long r = 0; r < static_cast<long long>(range); ++r) {
        size_t count = counts[static_cast<size_t>(r)];
        if (count == 0) continue;
        size_t start = starts[static_cast<size_t>(r)];
        T value = static_cast<T>(static_cast<Wide>(min_val) + static_cast<Wide>(r));
        for (size_t k = 0; k < count; ++k) output[start + k] = value;
    }

    vec.swap(output);
}

#endif // COUNTINGSORT_HPP