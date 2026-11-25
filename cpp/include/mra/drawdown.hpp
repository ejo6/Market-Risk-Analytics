#pragma once

// Drawdown: the fall from the highest value reached so far. VaR describes one
// bad day; drawdown describes a bad stretch, which is what an investor lives
// through.

#include "mra/types.hpp"

namespace mra {

struct DrawdownStats {
    double max_drawdown;      // positive fraction: 0.34 = fell 34% from a peak
    Index peak;               // index into returns of the peak before the worst fall (-1 = the start)
    Index trough;             // index into returns of the bottom of the worst fall
    Index longest_underwater; // most consecutive days spent below a previous peak
};

// From a daily simple-return series (oldest first):
//   W_t = prod_{s <= t} (1 + r_s),  with W_{-1} = 1 (the starting value)
//   M_t = max(1, max_{s <= t} W_s)  the running peak, including the start
//   DD_t = 1 - W_t / M_t
//   max_drawdown = max_t DD_t
//
// Edge cases: a series that never falls gives peak = trough = 0; a loss on
// day 0 gives peak = -1; a streak still underwater at the end counts.
// Parity target: np.cumprod / np.maximum.accumulate (tests/python).
[[nodiscard]] DrawdownStats drawdown_stats(const VectorRef& returns);

}  // namespace mra
