// C-simulation testbench: random frame -> preproc -> compare with straightforward reference
#include <cstdio>
#include <cstdlib>
#include <vector>
#include "preproc.h"

int main()
{
    std::vector<unsigned char> img(H * W * 3), ref(OH * OW * 3);
    unsigned int seed = 12345;
    for (size_t i = 0; i < img.size(); i++) { seed = seed * 1664525u + 1013904223u; img[i] = (seed >> 24) & 0xFF; }
    for (int y = 0; y < OH; y++)
        for (int x = 0; x < OW; x++)
            for (int ch = 0; ch < 3; ch++) {
                int s = img[((2*y)*W + 2*x)*3 + ch] + img[((2*y)*W + 2*x+1)*3 + ch]
                      + img[((2*y+1)*W + 2*x)*3 + ch] + img[((2*y+1)*W + 2*x+1)*3 + ch];
                ref[(y*OW + x)*3 + (2 - ch)] = (s + 2) >> 2;
            }

    hls::stream<word_t> in, out;
    for (int i = 0; i < H * W * 3 / 4; i++) {
        word_t w;
        w.data = (ap_uint<32>(img[4*i+3]) << 24) | (ap_uint<32>(img[4*i+2]) << 16) | (ap_uint<32>(img[4*i+1]) << 8) | img[4*i];
        w.keep = 0xF; w.strb = 0xF; w.last = (i == H * W * 3 / 4 - 1);
        in.write(w);
    }
    preproc(in, out);

    int nout = 0, bad = 0, lastcnt = 0;
    while (!out.empty()) {
        word_t o = out.read();
        for (int k = 0; k < 4; k++) {
            unsigned char v = (o.data >> (8 * k)) & 0xFF;
            if (v != ref[4 * nout + k]) bad++;
        }
        if (o.last) { lastcnt++; if (nout != OH * OW * 3 / 4 - 1) { printf("TLAST at wrong position %d\n", nout); bad++; } }
        nout++;
    }
    printf("output words = %d (expected %d), mismatched bytes = %d, TLAST count = %d\n", nout, OH * OW * 3 / 4, bad, lastcnt);
    if (nout != OH * OW * 3 / 4 || bad || lastcnt != 1) { printf("FAIL\n"); return 1; }
    printf("PASS\n"); return 0;
}
