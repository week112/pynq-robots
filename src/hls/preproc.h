#ifndef PREPROC_H
#define PREPROC_H
#include <ap_int.h>
#include <hls_stream.h>
#include <ap_axi_sdata.h>

typedef ap_axiu<32, 0, 0, 0> word_t;
const int W = 640, H = 480;
const int OW = 320, OH = 240;
const int WORDS_IN = W * 3 / 4;     // 480 words per source row
const int WORDS_OUT = OW * 3 / 4;   // 240 words per output row

void preproc(hls::stream<word_t> &in, hls::stream<word_t> &out);
#endif
