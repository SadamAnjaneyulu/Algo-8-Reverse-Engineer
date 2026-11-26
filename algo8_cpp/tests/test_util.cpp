// Reference values produced by Python/NumPy (tests/gen_util_cases.py); the C++ helpers must reproduce them bit for bit.
#include <cassert>
#include <cmath>
#include <cstdio>
#include "algo8/util.hpp"
using namespace a8;
int main() {
    int bad = 0;
    if (py_round2(0.0) != 0.0) { std::printf("round2 0.0\n"); ++bad; }
    if (py_round2(0.005) != 0.01) { std::printf("round2 0.005\n"); ++bad; }
    if (py_round2(0.015) != 0.01) { std::printf("round2 0.015\n"); ++bad; }
    if (py_round2(0.025) != 0.03) { std::printf("round2 0.025\n"); ++bad; }
    if (py_round2(1.005) != 1.0) { std::printf("round2 1.005\n"); ++bad; }
    if (py_round2(2.675) != 2.67) { std::printf("round2 2.675\n"); ++bad; }
    if (py_round2(24.35) != 24.35) { std::printf("round2 24.35\n"); ++bad; }
    if (py_round2(19999.995) != 19999.99) { std::printf("round2 19999.995\n"); ++bad; }
    if (py_round2(0.30000000000000004) != 0.3) { std::printf("round2 0.30000000000000004\n"); ++bad; }
    if (py_round2(123.456789) != 123.46) { std::printf("round2 123.456789\n"); ++bad; }
    if (py_round2(0.045) != 0.04) { std::printf("round2 0.045\n"); ++bad; }
    if (py_round2(0.055) != 0.06) { std::printf("round2 0.055\n"); ++bad; }
    if (py_round2(1234.5649999) != 1234.56) { std::printf("round2 1234.5649999\n"); ++bad; }
    if (py_round2(1234.565) != 1234.57) { std::printf("round2 1234.565\n"); ++bad; }
    if (py_floordiv(7.3, 0.4) != 18.0) { std::printf("floordiv 7.3 0.4\n"); ++bad; }
    if (py_floordiv(1.2, 0.4) != 2.0) { std::printf("floordiv 1.2 0.4\n"); ++bad; }
    if (py_floordiv(0.8, 0.4) != 2.0) { std::printf("floordiv 0.8 0.4\n"); ++bad; }
    if (py_floordiv(2.0, 0.4) != 4.0) { std::printf("floordiv 2.0 0.4\n"); ++bad; }
    if (py_floordiv(10.0, 0.2) != 49.0) { std::printf("floordiv 10.0 0.2\n"); ++bad; }
    if (py_floordiv(0.6000000000000001, 0.2) != 3.0) { std::printf("floordiv 0.6000000000000001 0.2\n"); ++bad; }
    if (py_floordiv(45.0, 2.5) != 18.0) { std::printf("floordiv 45.0 2.5\n"); ++bad; }
    if (py_floordiv(3.3, 1.1) != 2.0) { std::printf("floordiv 3.3 1.1\n"); ++bad; }
    if (py_floordiv(9.9, 3.3) != 3.0) { std::printf("floordiv 9.9 3.3\n"); ++bad; }
    if (py_floordiv(12.5, 0.05) != 249.0) { std::printf("floordiv 12.5 0.05\n"); ++bad; }
    if (py_floordiv(0.12, 0.04) != 2.0) { std::printf("floordiv 0.12 0.04\n"); ++bad; }
    if (py_floordiv(5.0, 0.05) != 99.0) { std::printf("floordiv 5.0 0.05\n"); ++bad; }
    { double fp[4] = {33.06, 15.93, 65.44, 8.17}; double v = interp4(58.0, fp); double e = 11.184210526315788; if (!(v == e || (v != v && e != e))) { std::printf("interp 58\n"); ++bad; } }
    { double fp[4] = {10.32, 58.7, 91.06, 22.26}; double v = interp4(1.0, fp); double e = 12.739; if (!(v == e || (v != v && e != e))) { std::printf("interp 1\n"); ++bad; } }
    { double fp[4] = {43.93, 7.92, 9.98, 43.03}; double v = interp4(59.0, fp); double e = 43.03; if (!(v == e || (v != v && e != e))) { std::printf("interp 59\n"); ++bad; } }
    { double fp[4] = {13.26, 23.1, 63.12, 94.82}; double v = interp4(59.0, fp); double e = 94.82; if (!(v == e || (v != v && e != e))) { std::printf("interp 59\n"); ++bad; } }
    { double fp[4] = {58.97, 5.91, 22.89, 56.11}; double v = interp4(19.0, fp); double e = 8.562999999999995; if (!(v == e || (v != v && e != e))) { std::printf("interp 19\n"); ++bad; } }
    { double fp[4] = {29.67, 15.28, 12.66, 31.54}; double v = interp4(5.0, fp); double e = 26.0725; if (!(v == e || (v != v && e != e))) { std::printf("interp 5\n"); ++bad; } }
    { double fp[4] = {18.89, 58.58, 64.25, 37.87}; double v = interp4(58.0, fp); double e = 39.258421052631576; if (!(v == e || (v != v && e != e))) { std::printf("interp 58\n"); ++bad; } }
    { double fp[4] = {71.5, 56.87, 62.28, 50.15}; double v = interp4(58.0, fp); double e = 50.78842105263158; if (!(v == e || (v != v && e != e))) { std::printf("interp 58\n"); ++bad; } }
    { double fp[4] = {43.33, 32.1, 58.97, 45.87}; double v = interp4(21.0, fp); double e = 33.4435; if (!(v == e || (v != v && e != e))) { std::printf("interp 21\n"); ++bad; } }
    { double fp[4] = {25.59, 18.8, 78.2, 9.1}; double v = interp4(21.0, fp); double e = 21.77; if (!(v == e || (v != v && e != e))) { std::printf("interp 21\n"); ++bad; } }
    { double fp[4] = {5.0, NaN, 6.0, 7.0}; double v = interp4(10.0, fp); double e = NaN; if (!(v == e || (v != v && e != e))) { std::printf("interp 10\n"); ++bad; } }
    if (py_round_int(0.5) != 0) { std::printf("round_int 0.5\n"); ++bad; }
    if (py_round_int(1.5) != 2) { std::printf("round_int 1.5\n"); ++bad; }
    if (py_round_int(2.5) != 2) { std::printf("round_int 2.5\n"); ++bad; }
    if (py_round_int(2.4999) != 2) { std::printf("round_int 2.4999\n"); ++bad; }
    if (py_round_int(3.5) != 4) { std::printf("round_int 3.5\n"); ++bad; }
    if (py_round_int(-0.5) != 0) { std::printf("round_int -0.5\n"); ++bad; }
    std::printf(bad ? "FAILED %d\n" : "util tests passed\n", bad);
    return bad ? 1 : 0;
}
