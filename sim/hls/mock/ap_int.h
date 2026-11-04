#pragma once
#include <cstdint>
template<int N> struct ap_uint {
    uint64_t v;
    static constexpr uint64_t M = (N >= 64) ? ~0ULL : ((1ULL << N) - 1);
    ap_uint(uint64_t x = 0) : v(x & M) {}
    template<int K> ap_uint(const ap_uint<K>& o) : v(o.v & M) {}
    operator uint64_t() const { return v; }
    ap_uint<N> range(int hi, int lo) const { return ap_uint<N>((v >> lo) & ((1ULL << (hi - lo + 1)) - 1)); }
};
