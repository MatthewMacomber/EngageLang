#include <stdint.h>
#include <math.h>

double c_hypot(double a, double b) {
    return sqrt(a * a + b * b);
}

int64_t c_factorial(int64_t n) {
    if (n <= 1) return 1;
    int64_t result = 1;
    for (int64_t i = 2; i <= n; i++) {
        result *= i;
    }
    return result;
}

int64_t c_sum_range(int64_t start, int64_t end) {
    int64_t sum = 0;
    for (int64_t i = start; i <= end; i++) {
        sum += i;
    }
    return sum;
}

