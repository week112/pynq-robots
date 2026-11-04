// preproc : 640x480 BGR888 -> 320x240 RGB888  (2x2 box average + channel swap), AXI-Stream in/out, 32-bit words
//   input  : raw frame bytes B,G,R,B,G,R... row-major, packed little-endian into 32-bit words (same as numpy memory)
//   output : 320x240 frame, bytes R,G,B,... packed the same way, TLAST on the final word
//   rounding (sum+2)>>2  == OpenCV INTER_AREA for exact 2x downscale
#include "preproc.h"

void preproc(hls::stream<word_t> &in, hls::stream<word_t> &out)
{
#pragma HLS INTERFACE axis port=in
#pragma HLS INTERFACE axis port=out
#pragma HLS INTERFACE ap_ctrl_none port=return

    ap_uint<32> lineA[WORDS_IN];

    for (int r = 0; r < OH; r++) {
        // even source row: store
        for (int i = 0; i < WORDS_IN; i++) {
#pragma HLS PIPELINE II=1
            lineA[i] = in.read().data;
        }
        // odd source row: stream through, 6 words (8 pixels) of each row -> 3 output words (4 pixels)
        for (int h = 0; h < WORDS_IN / 6; h++) {
#pragma HLS PIPELINE II=6
            ap_uint<8> ba[24], bb[24];
            for (int j = 0; j < 6; j++) {
                ap_uint<32> a = lineA[6 * h + j];
                ap_uint<32> b = in.read().data;
                for (int k = 0; k < 4; k++) {
                    ba[4 * j + k] = a.range(8 * k + 7, 8 * k);
                    bb[4 * j + k] = b.range(8 * k + 7, 8 * k);
                }
            }
            ap_uint<8> ob[12];
            for (int q = 0; q < 4; q++) {
                for (int ch = 0; ch < 3; ch++) {
                    ap_uint<10> s = ba[6 * q + ch] + ba[6 * q + 3 + ch] + bb[6 * q + ch] + bb[6 * q + 3 + ch];
                    ap_uint<8> v = (s + 2) >> 2;
                    ob[3 * q + (2 - ch)] = v;           // BGR -> RGB
                }
            }
            for (int w = 0; w < 3; w++) {
                word_t o;
                o.data = (ap_uint<32>(ob[4 * w + 3]) << 24) | (ap_uint<32>(ob[4 * w + 2]) << 16) |
                         (ap_uint<32>(ob[4 * w + 1]) << 8) | ap_uint<32>(ob[4 * w]);
                o.keep = 0xF; o.strb = 0xF;
                o.last = (r == OH - 1 && h == WORDS_IN / 6 - 1 && w == 2) ? 1 : 0;
                out.write(o);
            }
        }
    }
}
