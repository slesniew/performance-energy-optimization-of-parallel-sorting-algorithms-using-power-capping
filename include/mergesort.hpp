#ifndef MERGESORT_HPP
#define MERGESORT_HPP

#include <vector>
#include <omp.h>

#define THRESHOLD 5000

template <typename T>
using it = typename std::vector<T>::iterator;

template <typename T>
void merge(std::vector<T>& vec, std::vector<T>& tmp, it<T> first, it<T> middle, it<T> last) {
    std::copy(first, last, tmp.begin() + std::distance(vec.begin(), first));

    auto left = tmp.begin() + std::distance(vec.begin(), first);
    auto right = tmp.begin() + std::distance(vec.begin(), middle);
    auto left_end = tmp.begin() + std::distance(vec.begin(), middle);
    auto right_end = tmp.begin() + std::distance(vec.begin(), last);
    auto dest = first;

    while (left < left_end && right < right_end) {
        if (*left < *right) {
            *dest++ = *left++;
        } else {
            *dest++ = *right++;
        }
    }
    while (left < left_end) {
        *dest++ = *left++;
    }
    while (right < right_end) {
        *dest++ = *right++;
    }
}

template <typename T>
void mergesort(std::vector<T>& vec, std::vector<T>& tmp, it<T> first, it<T> last) {
    auto n = std::distance(first, last);
    if (n > 1){
        it<T> middle = first + n/2;
        mergesort(vec, tmp, first, middle);
        mergesort(vec, tmp, middle, last);
        merge(vec, tmp, first, middle, last);
    }
}

template <typename T>
void mergesort_parallel(std::vector<T>& vec, std::vector<T>& tmp, it<T> first, it<T> last) {
    auto n = std::distance(first, last);
    if (n > 1){
        it<T> middle = first + n/2;
        if(n < THRESHOLD) {
            mergesort(vec, tmp, first, middle);
            mergesort(vec, tmp, middle, last);
        }
        else {
            #pragma omp task shared(vec,tmp)
            mergesort_parallel(vec, tmp, first, middle);
            #pragma omp task shared(vec,tmp)
            mergesort_parallel(vec, tmp, middle, last);
            #pragma omp taskwait
        }
        merge(vec, tmp, first, middle, last);
    }
}

template <typename T>
void mergesort(std::vector<T>& vec) {
    if(!vec.empty()){
        std::vector<T> tmp(vec.size());
        mergesort<T>(vec, tmp, vec.begin(), vec.end());
    }
}

template <typename T>
void mergesort_parallel(std::vector<T>& vec) {
    if (vec.empty()) return;
    std::vector<T> tmp(vec.size());
    #pragma omp parallel
    {
        #pragma omp single nowait
        {
            mergesort_parallel<T>(vec, tmp, vec.begin(), vec.end());
        }
    }
}

#endif // MERGESORT_HPP