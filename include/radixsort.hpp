#ifndef RADIXSORT_HPP
#define RADIXSORT_HPP

#include <vector>
#include <cstdint>
#include <algorithm>
#include <type_traits>
#include <limits>

template <typename T>
void radixsort(std::vector<T>& vec) {
    static_assert(std::is_integral<T>::value, "radixsort requires an integral type");
    if (vec.empty()) return;

    using U = typename std::make_unsigned<T>::type;
    constexpr int BITS = 8;
    constexpr int BUCKETS = 1 << BITS;
    constexpr int MASK = BUCKETS - 1;
    constexpr int PASSES = (std::numeric_limits<U>::digits + BITS - 1) / BITS;

    std::vector<U> uvec(vec.size());
    if constexpr (std::is_signed<T>::value) {
        U sign_mask = U(1) << (std::numeric_limits<U>::digits - 1);
        for (size_t i = 0; i < vec.size(); ++i)
            uvec[i] = static_cast<U>(vec[i]) ^ sign_mask;
    } else {
        for (size_t i = 0; i < vec.size(); ++i)
            uvec[i] = static_cast<U>(vec[i]);
    }

    std::vector<U> utmp(uvec.size());

    for (int pass = 0; pass < PASSES; ++pass) {
        int shift = pass * BITS;
        std::vector<size_t> count(BUCKETS, 0);

        for (auto v : uvec)
            ++count[(v >> shift) & MASK];

        std::vector<size_t> pos(BUCKETS, 0);
        for (int i = 1; i < BUCKETS; ++i)
            pos[i] = pos[i - 1] + count[i - 1];

        for (auto v : uvec)
            utmp[pos[(v >> shift) & MASK]++] = v;

        std::swap(uvec, utmp);
    }

    if constexpr (std::is_signed<T>::value) {
        U sign_mask = U(1) << (std::numeric_limits<U>::digits - 1);
        for (size_t i = 0; i < vec.size(); ++i)
            vec[i] = static_cast<T>(uvec[i] ^ sign_mask);
    } else {
        for (size_t i = 0; i < vec.size(); ++i)
            vec[i] = static_cast<T>(uvec[i]);
    }
}

template <typename T>
void radixsort_parallel(std::vector<T>& vec) {
    static_assert(std::is_integral<T>::value, "radixsort requires an integral type");
    if (vec.empty()) return;

    using U = typename std::make_unsigned<T>::type;
    constexpr int BITS = 8;
    constexpr int BUCKETS = 1 << BITS;
    constexpr int MASK = BUCKETS - 1;
    constexpr int PASSES = (std::numeric_limits<U>::digits + BITS - 1) / BITS;

    size_t n = vec.size();
    std::vector<U> uvec(n);

    if constexpr (std::is_signed<T>::value) {
        U sign_mask = U(1) << (std::numeric_limits<U>::digits - 1);
        #pragma omp parallel for simd
        for (size_t i = 0; i < n; ++i)
            uvec[i] = static_cast<U>(vec[i]) ^ sign_mask;
    } else {
        #pragma omp parallel for simd
        for (size_t i = 0; i < n; ++i)
            uvec[i] = static_cast<U>(vec[i]);
    }

    std::vector<U> utmp(n);

    for (int pass = 0; pass < PASSES; ++pass) {
        int shift = pass * BITS;

        std::vector<size_t> count(BUCKETS, 0);

        int threads = omp_get_max_threads();
        std::vector<std::vector<size_t>> local_hist(threads, std::vector<size_t>(BUCKETS, 0));

        #pragma omp parallel
        {
            int tid = omp_get_thread_num();
            auto& local = local_hist[tid];

            #pragma omp for simd
            for (size_t i = 0; i < n; ++i) {
                U val = uvec[i];
                size_t bucket = (val >> shift) & MASK;
                local[bucket]++;
            }
        }

        for (int b = 0; b < BUCKETS; ++b) {
            for (int t = 0; t < threads; ++t) {
                count[b] += local_hist[t][b];
            }
        }

        std::vector<size_t> pos(BUCKETS, 0);
        for (int i = 1; i < BUCKETS; ++i)
            pos[i] = pos[i - 1] + count[i - 1];

        std::vector<std::vector<size_t>> local_pos(threads, std::vector<size_t>(BUCKETS));
        for (int b = 0; b < BUCKETS; ++b) {
            size_t p = pos[b];
            for (int t = 0; t < threads; ++t) {
                local_pos[t][b] = p;
                p += local_hist[t][b];
            }
        }

        #pragma omp parallel
        {
            int tid = omp_get_thread_num();
            auto& lpos = local_pos[tid];

            #pragma omp for simd
            for (size_t i = 0; i < n; ++i) {
                U val = uvec[i];
                size_t b = (val >> shift) & MASK;
                size_t& index = lpos[b];
                utmp[index++] = val;
            }
        }

        std::swap(uvec, utmp);
    }

    if constexpr (std::is_signed<T>::value) {
        U sign_mask = U(1) << (std::numeric_limits<U>::digits - 1);
        #pragma omp parallel for simd
        for (size_t i = 0; i < n; ++i)
            vec[i] = static_cast<T>(uvec[i] ^ sign_mask);
    } else {
        #pragma omp parallel for simd
        for (size_t i = 0; i < n; ++i)
            vec[i] = static_cast<T>(uvec[i]);
    }
}

#endif // RADIXSORT_HPP