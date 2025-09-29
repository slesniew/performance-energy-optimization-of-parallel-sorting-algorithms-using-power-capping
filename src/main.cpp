#include <iostream>
#include <vector>
#include <limits>
#include <utility>
#include <algorithm>
#include <string>
#include <sstream>
#include "tests.hpp"

#define DEFAULT_INPUT_SIZE 100000000

int main(int argc, char* argv[])
{
    for (int i = 1; i < argc; ++i) {
        if (std::string(argv[i]) == "--help" || std::string(argv[i]) == "-h") {
            Utility::print_help();
            return 0;
        }
    }

    if (argc < 2) {
        std::cerr << "Error: Not enough arguments.\n";
        Utility::print_help();
        return 1;
    }

    std::string mode = argv[1];
    std::string algorithm;
    unsigned long size = DEFAULT_INPUT_SIZE;
    int num_threads = 0;

    int argi = 2;
    if (mode == "bench") {
        if (argc < 3) {
            std::cerr << "Error: 'bench' mode requires an algorithm name.\n";
            Utility::print_help();
            return 1;
        }
        algorithm = argv[2];
        argi = 3;
    }

    for (int i = argi; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--size") {
            if (i + 1 >= argc) {
                std::cerr << "Error: --size requires a value.\n";
                return 1;
            }
            std::istringstream iss(argv[++i]);
            if (!(iss >> size) || size == 0) {
                std::cerr << "Error: Invalid value for --size.\n";
                return 1;
            }
        } else if (arg == "--threads") {
            if (i + 1 >= argc) {
                std::cerr << "Error: --threads requires a value.\n";
                return 1;
            }
            std::istringstream iss(argv[++i]);
            if (!(iss >> num_threads) || num_threads <= 0) {
                std::cerr << "Error: Invalid value for --threads.\n";
                return 1;
            }
        } else if (arg == "--debug") {
            Utility::debug_mode = true;
            std::cout << "Debug mode enabled: Sort validation will be performed.\n";
        } else {
            std::cerr << "Error: Unknown argument: " << arg << "\n";
            Utility::print_help();
            return 1;
        }
    }

    const auto range = std::make_pair(std::numeric_limits<int>::min(), std::numeric_limits<int>::max());


    if (mode == "bench" && algorithm.find("parallel") != std::string::npos) {
        unsigned int threads_count = (num_threads > 0) ? num_threads : omp_get_num_procs();
        omp_set_num_threads(threads_count);
        std::cout << "Running with " << threads_count << " threads.\n";
    }

    Utility::init_log_dir();

    std::vector<int> input;
    std::cout << "Generating random input vector of size " << size << " from values (" << range.first << ";" << range.second << ")...\n";
    Utility::measureExecutionTime("generateRandomInput",
        [&]() {
            Utility::generateRandomInput<int>(input, size, range);
        });
    std::vector<int> v(input);

    std::cout << "Mode: " << mode;
    if (mode == "bench") std::cout << ", Algorithm: " << algorithm;
    std::cout << std::endl;

    Utility::log_parameters(mode, algorithm, size, num_threads);

    if (mode == "all") {
        runAll(v, input);
    } else if (mode == "bench") {
        runOne(v, input, algorithm);
    } else {
        std::cerr << "Error: Unknown mode '" << mode << "'.\n";
        Utility::print_help();
        return 1;
    }

    return 0;
}