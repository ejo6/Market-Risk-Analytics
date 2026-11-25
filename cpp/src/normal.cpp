#include "mra/normal.hpp"

#include <cmath>
#include <stdexcept>

namespace mra {

namespace {

constexpr double kSqrt2 = 1.41421356237309504880;
constexpr double kSqrt2Pi = 2.50662827463100050242;

// Acklam's coefficients: a/b for the central region, c/d for the tails
constexpr double a[] = {-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
                        1.383577518672690e+02,  -3.066479806614716e+01, 2.506628277459239e+00};
constexpr double b[] = {-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
                        6.680131188771972e+01,  -1.328068155288572e+01};
constexpr double c[] = {-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
                        -2.549732539343734e+00, 4.374664141464968e+00,  2.938163982698783e+00};
constexpr double d[] = {7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
                        3.754408661907416e+00};

// Below kPLow (or above 1 - kPLow) the tail approximation is used
constexpr double kPLow = 0.02425;

// Tail rational function C(q) / D(q), shared by both tails
double tail(double q) {
    return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
           ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0);
}

}  // namespace

double normal_pdf(double x) { return std::exp(-0.5 * x * x) / kSqrt2Pi; }

double normal_cdf(double x) { return 0.5 * std::erfc(-x / kSqrt2); }

double inverse_normal_cdf(double p) {
    if (!(p > 0.0 && p < 1.0)) throw std::invalid_argument("inverse_normal_cdf needs p in (0, 1)");

    double x;
    if (p < kPLow) {
        x = tail(std::sqrt(-2.0 * std::log(p)));
    } else if (p > 1.0 - kPLow) {
        x = -tail(std::sqrt(-2.0 * std::log1p(-p)));  // log1p: exact for p near 1
    } else {
        const double q = p - 0.5;
        const double r = q * q;
        x = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q /
            (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0);
    }

    // One Halley step (Newton with a curvature correction) against the exact
    // CDF: takes Acklam's ~1e-9 to ~1e-15.
    const double e = normal_cdf(x) - p;
    const double u = e * kSqrt2Pi * std::exp(0.5 * x * x);
    return x - u / (1.0 + 0.5 * x * u);
}

}  // namespace mra
