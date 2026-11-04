#pragma once
#include <queue>
namespace hls { template<class T> struct stream { std::queue<T> q; void write(const T&x){q.push(x);} T read(){T x=q.front();q.pop();return x;} bool empty(){return q.empty();} }; }
