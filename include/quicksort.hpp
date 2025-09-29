#ifndef QUICKSORT_HPP
#define QUICKSORT_HPP

#include <vector>
#include <omp.h>
#include "x86simdsort-static-incl.h"

template <typename T>
using it = typename std::vector<T>::iterator;

template <typename T>
it<T> partition(it<T> begin, it<T> end) {
    auto pivot = *(end - 1);
    auto i = begin - 1;
    for (auto j = begin; j < end - 1; ++j) {
        if (*j <= pivot) {
            ++i;
            std::swap(*i, *j);
        }
    }
    std::swap(*(i + 1), *(end - 1));
    return i + 1;
}

template <typename T>
void quicksort(it<T> begin, it<T> end) {
    if (begin >= end -1) {
        return;
    }
    auto pivot = partition<T>(begin,end);
    
    quicksort<T>(begin, pivot);
    quicksort<T>(pivot + 1, end);
}

template <typename T>
void quicksort_parallel(it<T> begin, it<T> end) {
    if (begin >= end -1) {
        return;
    }
    auto pivot = partition<T>(begin,end);
    
    #pragma omp task
    quicksort_parallel<T>(begin, pivot);
    #pragma omp task
    quicksort_parallel<T>(pivot + 1, end);
}

template <typename T>
void quicksort_parallel_cutoff(it<T> begin, it<T> end) {
    if (begin >= end -1) {
        return;
    }
    auto pivot = partition<T>(begin,end);

    auto range = std::distance(begin, end);
    
    if (range >= 10000) {
        #pragma omp task
        quicksort_parallel_cutoff<T>(begin, pivot);
        #pragma omp task
        quicksort_parallel_cutoff<T>(pivot + 1, end);
    }
    else {
        quicksort<T>(begin, pivot);
        quicksort<T>(pivot + 1, end);
    }
}


template <typename T>
void quicksort(std::vector<T>& vec) {
    if(!vec.empty()){
        quicksort<T>(vec.begin(), vec.end());
    }
}

template <typename T>
void quicksort_parallel(std::vector<T>& vec) {
    if(!vec.empty()){
        #pragma omp parallel
        {
            #pragma omp single
            quicksort_parallel<T>(vec.begin(), vec.end());
            #pragma omp taskwait
        }
    }
}

template <typename T>
void quicksort_parallel_cutoff(std::vector<T>& vec) {
    if(!vec.empty()){
        #pragma omp parallel
        {
            #pragma omp single
            quicksort_parallel_cutoff<T>(vec.begin(), vec.end());
            #pragma omp taskwait
        }
    }
}

template <typename T>
void quicksort_x86_simd(std::vector<T>& vec) {
    if(!vec.empty()){
        x86simdsortStatic::qsort(vec.data(), vec.size());
    }
}

#endif // QUICKSORT_HPP