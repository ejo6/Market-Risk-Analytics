#include "mra/drawdown.hpp"

#include <stdexcept>
#include <algorithm>

namespace mra {

DrawdownStats drawdown_stats(const VectorRef& returns) {
    if (returns.size() == 0) throw std::invalid_argument("return series is empty");
    
    // No drawdown until we've actually seen one
    DrawdownStats dds{0.0, 0, 0, 0};

    double wealth = 1.0; // current value of $1 invested at the start
    double peak_wealth = 1.0; // highest wealth so far, including the start
    Index peak_idx = -1; // where peak_wealth was last updated
    Index streak = 0; // Curr run of days below peak wealth
    
    for (Index t = 0; t < returns.size(); t++) {
        wealth *= 1 + returns[t];

        // Are we at an all time high?
        if (wealth >= peak_wealth) {
            peak_wealth = wealth; 
            peak_idx = t; 
            streak = 0;
            continue;
        }

        // If not:
        const double drawdown = 1.0 - wealth / peak_wealth;
        if (drawdown > dds.max_drawdown) {
            dds.max_drawdown = drawdown; 
            dds.peak = peak_idx; 
            dds.trough = t;
        }
        
        dds.longest_underwater = std::max(dds.longest_underwater, ++streak);
    }
    return dds;
}

}  // namespace mra
