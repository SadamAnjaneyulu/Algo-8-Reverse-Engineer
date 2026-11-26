// Numeric helpers that reproduce Python/NumPy semantics exactly (so the C++ engine is order-for-order identical to the Python reference).
#pragma once
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <string>
namespace a8 {
constexpr double NaN = std::numeric_limits<double>::quiet_NaN();
inline bool isnan_(double x) { return x != x; }
// Python round(x, 2): correctly rounded decimal expansion (round-half-even on the exact binary value)
inline double py_round2(double x) { char b[64]; std::snprintf(b, sizeof b, "%.2f", x); return std::strtod(b, nullptr); }
// Python float floor division x // y
inline double py_floordiv(double vx, double wx) {
    double mod = std::fmod(vx, wx); double div = (vx - mod) / wx;
    if (mod != 0.0) { if ((wx < 0) != (mod < 0)) { mod += wx; div -= 1.0; } }
    double fd;
    if (div != 0.0) { fd = std::floor(div); if (div - fd > 0.5) fd += 1.0; }
    else fd = std::copysign(0.0, vx / wx);
    return fd;
}
// Python round(x) for floats -> int (ties to even)
inline long py_round_int(double x) { return (long)std::nearbyint(x); }
// numpy.interp for xs = {0,20,40,59} (right/left clamp, NaN handling of numpy >= 1.17)
inline double interp4(double x, const double fp[4]) {
    static const double xs[4] = {0.0, 20.0, 40.0, 59.0};
    if (isnan_(x)) return x;
    if (x >= xs[3]) return fp[3];
    if (x < xs[0]) return fp[0];
    int j = 0; while (j < 2 && x >= xs[j + 1]) ++j;                     // xs[j] <= x < xs[j+1], j in {0,1,2}
    double slope = (fp[j + 1] - fp[j]) / (xs[j + 1] - xs[j]);
    double r = slope * (x - xs[j]) + fp[j];
    if (isnan_(r)) { r = slope * (x - xs[j + 1]) + fp[j + 1]; if (isnan_(r) && fp[j] == fp[j + 1]) r = fp[j]; }
    return r;
}
}  // namespace a8
