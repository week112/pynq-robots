#pragma once
#include "ap_int.h"
template<int D,int U,int I,int De> struct ap_axiu { ap_uint<D> data; ap_uint<D/8> keep, strb; ap_uint<1> last; };
