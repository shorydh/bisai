#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <map>
#include <random>
#include <set>
#include <sstream>
#include <string>
#include <vector>
#define __aicore__
#define PADV3GRAD_INLINE inline
constexpr int64_t CACHE_ELEMENTS=8192;
enum class HardEvent{V_S,S_V};
template<HardEvent> void Sync(){}
template<class X> X Min(X a,X b){return std::min(a,b);}
struct Data{int64_t totalInput=1,totalOutput=1,mode=2,rank=0;int64_t inputShape[32]{},outputShape[32]{},inputStride[32]{};};
struct OffsetTensor{std::vector<uint32_t>* v;void SetValue(int64_t i,uint32_t x){v->at(i)=x;}};
struct OffsetBuffer{std::vector<uint32_t> v;template<class X> OffsetTensor Get(){return {&v};}};
void Duplicate(OffsetTensor t,uint32_t x,uint32_t n){t.v->assign(n,x);}
namespace PadV3GradIndex {
enum Mode : int64_t { CONSTANT = 0, EDGE = 1, REFLECT = 2, SYMMETRIC = 3, CIRCULAR = 4 };

struct Contributors {
    int64_t first[2];
    int64_t count[2];
    int64_t step;

    PADV3GRAD_INLINE int64_t Size() const { return count[0] + count[1]; }
    PADV3GRAD_INLINE int64_t At(int64_t slot) const
    {
        return slot < count[0] ? first[0] + slot * step
                              : first[1] + (slot - count[0]) * step;
    }
};

PADV3GRAD_INLINE int64_t PositiveMod(int64_t x, int64_t period)
{
    if (x >= 0 && x < period) {
        return x;
    }
    if (x < 0 && x >= -period) {
        return x + period;
    }
    const int64_t r = x % period;
    return r < 0 ? r + period : r;
}

PADV3GRAD_INLINE int64_t AddMod(int64_t a, int64_t b, int64_t period)
{
    return a >= period - b ? a - (period - b) : a + b;
}

PADV3GRAD_INLINE void SetResidue(Contributors &r, int slot, int64_t residue,
                                int64_t inputLength, int64_t front)
{
    r.first[slot] = AddMod(PositiveMod(front, r.step), residue, r.step);
    if (r.first[slot] < inputLength) {
        const int64_t distance = inputLength - 1 - r.first[slot];
        r.count[slot] = distance < r.step ? 1 :
            (distance - r.step < r.step ? 2 : 1 + distance / r.step);
    }
}

// Invert the pad map as at most two disjoint arithmetic progressions.
PADV3GRAD_INLINE Contributors MakeContributors(int64_t outputCoordinate,
                                              int64_t inputLength,
                                              int64_t outputLength,
                                              int64_t front, int64_t mode)
{
    Contributors r{};
    r.step = 1;
    if (inputLength <= 0 || outputLength <= 0 || outputCoordinate < 0 ||
        outputCoordinate >= outputLength) {
        return r;
    }
    if (inputLength == outputLength && front == 0 && mode >= CONSTANT && mode <= CIRCULAR) {
        r.first[0] = outputCoordinate;
        r.count[0] = 1;
        return r;
    }
    if (mode == CONSTANT) {
        if (front <= inputLength - 1 - outputCoordinate && front >= -outputCoordinate) {
            r.first[0] = front + outputCoordinate;
            r.count[0] = 1;
        }
        return r;
    }
    if (outputLength == 1) {
        r.count[0] = inputLength;
        return r;
    }
    if (mode == EDGE) {
        if (outputCoordinate == 0) {
            const int64_t end = front < inputLength - 1 ? front : inputLength - 1;
            r.count[0] = end < 0 ? 0 : end + 1;
        } else if (outputCoordinate == outputLength - 1) {
            if (front <= inputLength - 1 - outputCoordinate) {
                r.first[0] = front < -outputCoordinate ? 0 : front + outputCoordinate;
                r.count[0] = inputLength - r.first[0];
            }
        } else if (front >= -outputCoordinate && front <= inputLength - 1 - outputCoordinate) {
            r.first[0] = front + outputCoordinate;
            r.count[0] = 1;
        }
        return r;
    }
    if (mode == CIRCULAR) {
        r.step = outputLength;
        SetResidue(r, 0, outputCoordinate, inputLength, front);
    } else if (mode == REFLECT) {
        r.step = 2 * (outputLength - 1);
        SetResidue(r, 0, outputCoordinate, inputLength, front);
        if (outputCoordinate != 0 && outputCoordinate != outputLength - 1) {
            SetResidue(r, 1, r.step - outputCoordinate, inputLength, front);
        }
    } else if (mode == SYMMETRIC) {
        r.step = 2 * outputLength;
        SetResidue(r, 0, outputCoordinate, inputLength, front);
        SetResidue(r, 1, r.step - 1 - outputCoordinate, inputLength, front);
    }
    return r;
}
} // namespace PadV3GradIndex
using PadV3GradIndex::Contributors;using PadV3GradIndex::MakeContributors;
namespace F{template<class T>class Planner{public:
Data*data_=nullptr;Contributors outer_[32]{};int64_t position_[32]{},front_[32]{},rank_=0,outerStart_=0,begin_=0,end_=0,base_=0,cachedOuterRow_=-1,cachedOuterBase_=0,inputWidth_=1,outputWidth_=1,maxContributorsObserved=-1;bool cachedOuterValid_=false;OffsetBuffer offsetBuffer_;
void Setup(Data& data,const std::vector<int64_t>& pads,bool contiguous,int64_t begin,int64_t end){data_=&data;cachedOuterRow_=-1;cachedOuterValid_=false;rank_=data.rank;begin_=begin;end_=end;inputWidth_=rank_==0?1:data.inputShape[rank_-1];outputWidth_=rank_==0?1:data.outputShape[rank_-1];for(int64_t d=0;d<rank_;++d){const int64_t index=contiguous?2*d:d;front_[d]=pads.at(index);}offsetBuffer_.v.clear();}
    __aicore__ inline bool InitOuter(int64_t row)
    {
        if (row == cachedOuterRow_) {
            if (!cachedOuterValid_) {
                return false;
            }
            base_ = cachedOuterBase_;
            // A rejected gather can stop NextOuter before it resets the cursor.
            for (int64_t d = rank_ - 2; d >= 0; --d) {
                position_[d] = 0;
            }
            return true;
        }
        // Save the original row before decoding its coordinates below.
        cachedOuterRow_ = row;
        cachedOuterValid_ = false;
        base_ = 0;
        for (int64_t d = rank_ - 2; d >= 0; --d) {
            const int64_t coord = row % data_->outputShape[d];
            row /= data_->outputShape[d];
            outer_[d] = MakeContributors(coord, data_->inputShape[d],
                                          data_->outputShape[d], front_[d], data_->mode);
            position_[d] = 0;
            if (outer_[d].Size() == 0) {
                return false;
            }
            base_ += outer_[d].At(0) * data_->inputStride[d];
        }
        cachedOuterBase_ = base_;
        cachedOuterValid_ = true;
        return true;
    }
    __aicore__ inline bool NextOuter()
    {
        for (int64_t d = rank_ - 2; d >= 0; --d) {
            const int64_t old = outer_[d].At(position_[d]);
            ++position_[d];
            if (position_[d] < outer_[d].Size()) {
                base_ += (outer_[d].At(position_[d]) - old) * data_->inputStride[d];
                return true;
            }
            position_[d] = 0;
            base_ += (outer_[d].At(0) - old) * data_->inputStride[d];
        }
        return false;
    }
    __aicore__ inline bool TryWideCertifiedFlat()
    {
        constexpr int64_t groupSize = 64;
        const int64_t count = end_ - begin_;
        if (rank_ == 0 || data_->totalInput > CACHE_ELEMENTS ||
            data_->totalOutput > 256 || count > 128) {
            return false;
        }
        const int64_t alignElements = 32 / sizeof(T);
        const int64_t sentinel = (data_->totalInput + alignElements - 1) /
                                  alignElements * alignElements;
        auto offsets = offsetBuffer_.Get<uint32_t>();
        Duplicate(offsets, static_cast<uint32_t>(sentinel * sizeof(T)),
                  static_cast<uint32_t>(count * groupSize));
        Sync<HardEvent::V_S>();
        int64_t maxContributors = 0;
        // Expand the outer Cartesian product once per output row. Every column
        // reuses the same ordered bases instead of restarting NextOuter.
        int64_t outerBases[groupSize];
        for (int64_t j = 0; j < count;) {
            const int64_t output = begin_ + j;
            const int64_t row = output / outputWidth_;
            const int64_t column = output % outputWidth_;
            const int64_t run = Min(count - j, outputWidth_ - column);
            int64_t outerCount = 0;
            bool planned = false;
            for (int64_t c = 0; c < run; ++c) {
                const auto last = MakeContributors(column + c, inputWidth_, outputWidth_,
                                                   front_[rank_ - 1], data_->mode);
                const int64_t lastCount = last.Size();
                int64_t pass = 0;
                if (lastCount != 0) {
                    // An entirely empty last-axis interval needs no outer plan.
                    if (!planned) {
                        if (InitOuter(row)) {
                            do {
                                if (outerCount == groupSize) {
                                    Sync<HardEvent::S_V>();
                                    return false;
                                }
                                outerBases[outerCount++] = base_;
                            } while (NextOuter());
                        }
                        planned = true;
                    }
                    if (outerCount != 0 && lastCount > groupSize / outerCount) {
                        Sync<HardEvent::S_V>();
                        return false;
                    }
                    // Keep the original outer-major, last-axis-minor order so
                    // grouped reduction and its numerical certificate are unchanged.
                    for (int64_t outer = 0; outer < outerCount; ++outer) {
                        for (int64_t k = 0; k < lastCount; ++k) {
                            offsets.SetValue((j + c) * groupSize + pass,
                                static_cast<uint32_t>((outerBases[outer] + last.At(k)) * sizeof(T)));
                            ++pass;
                        }
                    }
                }
                if (pass > maxContributors) {
                    maxContributors = pass;
                }
            }
            j += run;
        }
        maxContributorsObserved=maxContributors;
        return true;
    }
std::vector<int64_t> Bases(int64_t row){std::vector<int64_t>v;if(InitOuter(row)){do{v.push_back(base_);if(v.size()>8192)throw std::runtime_error("outer overflow");}while(NextOuter());}return v;}
};}
namespace P{template<class T>class Planner{public:
Data*data_=nullptr;Contributors outer_[32]{};int64_t position_[32]{},front_[32]{},rank_=0,outerStart_=0,begin_=0,end_=0,base_=0,cachedOuterRow_=-1,cachedOuterBase_=0,inputWidth_=1,outputWidth_=1,maxContributorsObserved=-1;bool cachedOuterValid_=false;OffsetBuffer offsetBuffer_;
void Setup(Data& data,const std::vector<int64_t>& pads,bool contiguous,int64_t begin,int64_t end){data_=&data;cachedOuterRow_=-1;cachedOuterValid_=false;rank_=data.rank;begin_=begin;end_=end;inputWidth_=rank_==0?1:data.inputShape[rank_-1];outputWidth_=rank_==0?1:data.outputShape[rank_-1];for(int64_t d=0;d<rank_;++d){const int64_t index=contiguous?2*d:d;front_[d]=pads.at(index);}offsetBuffer_.v.clear();}
    __aicore__ inline void InitOuterPrefix()
    {
        outerStart_ = 0;
        while (outerStart_ < rank_ - 1 && front_[outerStart_] == 0 &&
               data_->inputShape[outerStart_] == data_->outputShape[outerStart_]) {
            ++outerStart_;
        }
    }
    __aicore__ inline bool InitOuter(int64_t row)
    {
        if (row == cachedOuterRow_) {
            if (!cachedOuterValid_) {
                return false;
            }
            base_ = cachedOuterBase_;
            // A rejected gather can stop NextOuter before it resets the cursor.
            for (int64_t d = rank_ - 2; d >= outerStart_; --d) {
                position_[d] = 0;
            }
            return true;
        }
        // Save the original row before decoding its coordinates below.
        cachedOuterRow_ = row;
        cachedOuterValid_ = false;
        base_ = 0;
        for (int64_t d = rank_ - 2; d >= outerStart_; --d) {
            const int64_t coord = row % data_->outputShape[d];
            row /= data_->outputShape[d];
            outer_[d] = MakeContributors(coord, data_->inputShape[d],
                                          data_->outputShape[d], front_[d], data_->mode);
            position_[d] = 0;
            if (outer_[d].Size() == 0) {
                return false;
            }
            base_ += outer_[d].At(0) * data_->inputStride[d];
        }
        if (outerStart_ != 0) {
            base_ += row * data_->inputStride[outerStart_ - 1];
        }
        cachedOuterBase_ = base_;
        cachedOuterValid_ = true;
        return true;
    }
    __aicore__ inline bool NextOuter()
    {
        for (int64_t d = rank_ - 2; d >= outerStart_; --d) {
            const int64_t old = outer_[d].At(position_[d]);
            ++position_[d];
            if (position_[d] < outer_[d].Size()) {
                base_ += (outer_[d].At(position_[d]) - old) * data_->inputStride[d];
                return true;
            }
            position_[d] = 0;
            base_ += (outer_[d].At(0) - old) * data_->inputStride[d];
        }
        return false;
    }
    __aicore__ inline bool TryWideCertifiedFlat()
    {
        InitOuterPrefix();
        constexpr int64_t groupSize = 64;
        const int64_t count = end_ - begin_;
        if (rank_ == 0 || data_->totalInput > CACHE_ELEMENTS ||
            data_->totalOutput > 256 || count > 128) {
            return false;
        }
        const int64_t alignElements = 32 / sizeof(T);
        const int64_t sentinel = (data_->totalInput + alignElements - 1) /
                                  alignElements * alignElements;
        auto offsets = offsetBuffer_.Get<uint32_t>();
        Duplicate(offsets, static_cast<uint32_t>(sentinel * sizeof(T)),
                  static_cast<uint32_t>(count * groupSize));
        Sync<HardEvent::V_S>();
        int64_t maxContributors = 0;
        // Expand the outer Cartesian product once per output row. Every column
        // reuses the same ordered bases instead of restarting NextOuter.
        int64_t outerBases[groupSize];
        for (int64_t j = 0; j < count;) {
            const int64_t output = begin_ + j;
            const int64_t row = output / outputWidth_;
            const int64_t column = output % outputWidth_;
            const int64_t run = Min(count - j, outputWidth_ - column);
            int64_t outerCount = 0;
            bool planned = false;
            for (int64_t c = 0; c < run; ++c) {
                const auto last = MakeContributors(column + c, inputWidth_, outputWidth_,
                                                   front_[rank_ - 1], data_->mode);
                const int64_t lastCount = last.Size();
                int64_t pass = 0;
                if (lastCount != 0) {
                    // An entirely empty last-axis interval needs no outer plan.
                    if (!planned) {
                        if (InitOuter(row)) {
                            do {
                                if (outerCount == groupSize) {
                                    Sync<HardEvent::S_V>();
                                    return false;
                                }
                                outerBases[outerCount++] = base_;
                            } while (NextOuter());
                        }
                        planned = true;
                    }
                    if (outerCount != 0 && lastCount > groupSize / outerCount) {
                        Sync<HardEvent::S_V>();
                        return false;
                    }
                    // Keep the original outer-major, last-axis-minor order so
                    // grouped reduction and its numerical certificate are unchanged.
                    for (int64_t outer = 0; outer < outerCount; ++outer) {
                        for (int64_t k = 0; k < lastCount; ++k) {
                            offsets.SetValue((j + c) * groupSize + pass,
                                static_cast<uint32_t>((outerBases[outer] + last.At(k)) * sizeof(T)));
                            ++pass;
                        }
                    }
                }
                if (pass > maxContributors) {
                    maxContributors = pass;
                }
            }
            j += run;
        }
        maxContributorsObserved=maxContributors;
        return true;
    }
std::vector<int64_t> Bases(int64_t row){std::vector<int64_t>v;if(InitOuter(row)){do{v.push_back(base_);if(v.size()>8192)throw std::runtime_error("outer overflow");}while(NextOuter());}return v;}
};}
namespace PL{template<class T>class Planner{public:
Data*data_=nullptr;Contributors outer_[32]{};int64_t position_[32]{},front_[32]{},rank_=0,outerStart_=0,begin_=0,end_=0,base_=0,cachedOuterRow_=-1,cachedOuterBase_=0,inputWidth_=1,outputWidth_=1,maxContributorsObserved=-1;bool cachedOuterValid_=false;OffsetBuffer offsetBuffer_;
void Setup(Data& data,const std::vector<int64_t>& pads,bool contiguous,int64_t begin,int64_t end){data_=&data;cachedOuterRow_=-1;cachedOuterValid_=false;rank_=data.rank;begin_=begin;end_=end;inputWidth_=rank_==0?1:data.inputShape[rank_-1];outputWidth_=rank_==0?1:data.outputShape[rank_-1];for(int64_t d=0;d<rank_;++d){const int64_t index=contiguous?2*d:d;front_[d]=pads.at(index);}offsetBuffer_.v.clear();}
    __aicore__ inline void InitOuterPrefix()
    {
        outerStart_ = 0;
        while (outerStart_ < rank_ - 1 && front_[outerStart_] == 0 &&
               data_->inputShape[outerStart_] == data_->outputShape[outerStart_]) {
            ++outerStart_;
        }
    }
    __aicore__ inline bool InitOuter(int64_t row)
    {
        if (row == cachedOuterRow_) {
            if (!cachedOuterValid_) {
                return false;
            }
            base_ = cachedOuterBase_;
            // A rejected gather can stop NextOuter before it resets the cursor.
            for (int64_t d = rank_ - 2; d >= outerStart_; --d) {
                position_[d] = 0;
            }
            return true;
        }
        // Save the original row before decoding its coordinates below.
        cachedOuterRow_ = row;
        cachedOuterValid_ = false;
        base_ = 0;
        for (int64_t d = rank_ - 2; d >= outerStart_; --d) {
            const int64_t coord = row % data_->outputShape[d];
            row /= data_->outputShape[d];
            outer_[d] = MakeContributors(coord, data_->inputShape[d],
                                          data_->outputShape[d], front_[d], data_->mode);
            position_[d] = 0;
            if (outer_[d].Size() == 0) {
                return false;
            }
            base_ += outer_[d].At(0) * data_->inputStride[d];
        }
        if (outerStart_ != 0) {
            base_ += row * data_->inputStride[outerStart_ - 1];
        }
        cachedOuterBase_ = base_;
        cachedOuterValid_ = true;
        return true;
    }
    __aicore__ inline bool NextOuter()
    {
        for (int64_t d = rank_ - 2; d >= outerStart_; --d) {
            const int64_t old = outer_[d].At(position_[d]);
            ++position_[d];
            if (position_[d] < outer_[d].Size()) {
                base_ += (outer_[d].At(position_[d]) - old) * data_->inputStride[d];
                return true;
            }
            position_[d] = 0;
            base_ += (outer_[d].At(0) - old) * data_->inputStride[d];
        }
        return false;
    }
    __aicore__ inline bool TryWideCertifiedFlat()
    {
        InitOuterPrefix();
        constexpr int64_t groupSize = 64;
        const int64_t count = end_ - begin_;
        if (rank_ == 0 || data_->totalInput > CACHE_ELEMENTS ||
            data_->totalOutput > 256 || count > 128) {
            return false;
        }
        const int64_t alignElements = 32 / sizeof(T);
        const int64_t sentinel = (data_->totalInput + alignElements - 1) /
                                  alignElements * alignElements;
        auto offsets = offsetBuffer_.Get<uint32_t>();
        Duplicate(offsets, static_cast<uint32_t>(sentinel * sizeof(T)),
                  static_cast<uint32_t>(count * groupSize));
        Sync<HardEvent::V_S>();
        int64_t maxContributors = 0;
        // Expand the outer Cartesian product once per output row. Every column
        // reuses the same ordered bases instead of restarting NextOuter.
        int64_t outerBases[groupSize];
        // Last-axis contributors depend only on the column and this call's
        // padding. Cache narrow rows only when this core processes >1 row's
        // worth of outputs; wider/shorter ranges keep the original mapping.
        constexpr int64_t lastPlanCapacity = 32;
        const bool reuseLast = outputWidth_ <= lastPlanCapacity && count > outputWidth_;
        Contributors lastPlans[lastPlanCapacity];
        if (reuseLast) {
            for (int64_t column = 0; column < outputWidth_; ++column) {
                lastPlans[column] = MakeContributors(column, inputWidth_, outputWidth_,
                    front_[rank_ - 1], data_->mode);
            }
        }
        for (int64_t j = 0; j < count;) {
            const int64_t output = begin_ + j;
            const int64_t row = output / outputWidth_;
            const int64_t column = output % outputWidth_;
            const int64_t run = Min(count - j, outputWidth_ - column);
            int64_t outerCount = 0;
            bool planned = false;
            for (int64_t c = 0; c < run; ++c) {
                const auto last = reuseLast ? lastPlans[column + c] :
                    MakeContributors(column + c, inputWidth_, outputWidth_,
                                     front_[rank_ - 1], data_->mode);
                const int64_t lastCount = last.Size();
                int64_t pass = 0;
                if (lastCount != 0) {
                    // An entirely empty last-axis interval needs no outer plan.
                    if (!planned) {
                        if (InitOuter(row)) {
                            do {
                                if (outerCount == groupSize) {
                                    Sync<HardEvent::S_V>();
                                    return false;
                                }
                                outerBases[outerCount++] = base_;
                            } while (NextOuter());
                        }
                        planned = true;
                    }
                    if (outerCount != 0 && lastCount > groupSize / outerCount) {
                        Sync<HardEvent::S_V>();
                        return false;
                    }
                    // Keep the original outer-major, last-axis-minor order so
                    // grouped reduction and its numerical certificate are unchanged.
                    for (int64_t outer = 0; outer < outerCount; ++outer) {
                        for (int64_t k = 0; k < lastCount; ++k) {
                            offsets.SetValue((j + c) * groupSize + pass,
                                static_cast<uint32_t>((outerBases[outer] + last.At(k)) * sizeof(T)));
                            ++pass;
                        }
                    }
                }
                if (pass > maxContributors) {
                    maxContributors = pass;
                }
            }
            j += run;
        }
        maxContributorsObserved=maxContributors;
        return true;
    }
std::vector<int64_t> Bases(int64_t row){std::vector<int64_t>v;if(InitOuter(row)){do{v.push_back(base_);if(v.size()>8192)throw std::runtime_error("outer overflow");}while(NextOuter());}return v;}
};}

struct TestCase{Data d;std::vector<int64_t>front,back;std::string label;bool legalOfficial=true;};
struct Counts{int64_t cases=0,ranges=0,accepted=0,rejected=0,cacheActive=0,hostRanges=0,syntheticRanges=0,sourceOffsets=0,fallbackRows=0,partialResets=0,paddingReuse=0,floatBits=0;std::map<int64_t,int64_t>widths,counts,terms;std::map<std::string,int64_t>prefix;std::set<int64_t>contributorBoundaries;} stats;
int64_t mod(int64_t x,int64_t p){int64_t r=x%p;return r<0?r+p:r;}
int64_t forwardMap(int64_t i,int64_t front,int64_t n,int64_t mode){int64_t q=i-front;if(mode==0)return q>=0&&q<n?q:-1;if(n==1)return 0;if(mode==1)return std::max<int64_t>(0,std::min<int64_t>(q,n-1));if(mode==4)return mod(q,n);if(mode==2){int64_t k=mod(q,2*(n-1));return k<n?k:2*(n-1)-k;}int64_t k=mod(q,2*n);return k<n?k:2*n-1-k;}
TestCase make(std::vector<int64_t> input,std::vector<int64_t> output,std::vector<int64_t>front,int64_t mode,std::string label,bool legal=true){TestCase t;t.d.rank=input.size();t.d.mode=mode;t.front=front;t.label=label;t.legalOfficial=legal;t.back.resize(input.size());for(int64_t a=input.size();a-->0;){t.d.inputShape[a]=input[a];t.d.outputShape[a]=output[a];t.d.inputStride[a]=t.d.totalInput;t.d.totalInput*=input[a];t.d.totalOutput*=output[a];t.back[a]=input[a]-output[a]-front[a];}return t;}
std::vector<int64_t> pads(const TestCase&t,bool layout){std::vector<int64_t>p(2*t.d.rank);for(int a=0;a<t.d.rank;a++){p[layout?2*a:a]=t.front[a];p[layout?2*a+1:t.d.rank+a]=t.back[a];}return p;}
void fail(const TestCase&t,const std::string&msg,int64_t begin,int64_t end){std::cerr<<"FAIL "<<t.label<<" begin="<<begin<<" end="<<end<<" "<<msg<<"\n";std::exit(2);}
std::vector<int64_t> oracle(const TestCase&t,int64_t output){std::vector<int64_t>coords(t.d.rank);for(int64_t a=t.d.rank;a-->0;){coords[a]=output%t.d.outputShape[a];output/=t.d.outputShape[a];}std::vector<int64_t>v{0};for(int64_t a=0;a<t.d.rank;a++){std::vector<int64_t>indices;for(int64_t i=0;i<t.d.inputShape[a];i++)if(forwardMap(i,t.front[a],t.d.outputShape[a],t.d.mode)==coords[a])indices.push_back(i);std::vector<int64_t>w;for(auto base:v)for(auto i:indices)w.push_back(base+i*t.d.inputStride[a]);v.swap(w);}std::sort(v.begin(),v.end());return v;}
float value(int64_t i,int seed){static constexpr float values[]={0.f,-0.f,1.f,-1.f,1e20f,-1e20f,1e-20f,-1e-20f,65504.f,-65504.f};return values[(i*13+seed*7)%10];}
uint32_t bits(float f){uint32_t b;std::memcpy(&b,&f,sizeof(b));return b;}
template<class T>void runRange(TestCase&t,int64_t begin,int64_t end,bool layout,bool host){F::Planner<T>f;P::Planner<T>p;PL::Planner<T>pl;auto padding=pads(t,layout);f.Setup(t.d,padding,layout,begin,end);p.Setup(t.d,padding,layout,begin,end);pl.Setup(t.d,padding,layout,begin,end);bool fa=f.TryWideCertifiedFlat(),pa=p.TryWideCertifiedFlat(),ca=pl.TryWideCertifiedFlat();if(fa!=pa||pa!=ca)fail(t,"wide accept mismatch",begin,end);if(p.offsetBuffer_.v!=pl.offsetBuffer_.v||f.offsetBuffer_.v!=p.offsetBuffer_.v)fail(t,"byte-offset/source order mismatch",begin,end);if(pa&&p.maxContributorsObserved!=pl.maxContributorsObserved)fail(t,"max contributors mismatch",begin,end);stats.ranges++;if(host)stats.hostRanges++;else stats.syntheticRanges++;stats.widths[t.d.outputShape[t.d.rank-1]]++;stats.counts[end-begin]++;int64_t prefix=0;while(prefix<t.d.rank-1&&t.front[prefix]==0&&t.d.inputShape[prefix]==t.d.outputShape[prefix])prefix++;stats.prefix[prefix==0?"none":prefix==t.d.rank-1?"all":"partial"]++;if(t.d.outputShape[t.d.rank-1]<=32&&end-begin>t.d.outputShape[t.d.rank-1]&&t.d.totalInput<=8192&&t.d.totalOutput<=256&&end-begin<=128)stats.cacheActive++;
if(pa){stats.accepted++;const int64_t sentinel=(t.d.totalInput+(32/sizeof(T))-1)/(32/sizeof(T))*(32/sizeof(T));for(int64_t o=begin;o<end;o++){std::vector<int64_t>actual;for(int k=0;k<64;k++){auto off=p.offsetBuffer_.v[(o-begin)*64+k];int64_t source=off/sizeof(T);if(source!=sentinel){if(off%sizeof(T)||source<0||source>=t.d.totalInput)fail(t,"offset out of bounds",begin,end);actual.push_back(source);}}stats.terms[actual.size()]++;stats.contributorBoundaries.insert(actual.size());stats.sourceOffsets+=actual.size();auto sorted=actual;std::sort(sorted.begin(),sorted.end());if(sorted!=oracle(t,o))fail(t,"independent forward-map multiset mismatch",begin,end);for(int seed=0;seed<4;seed++){std::array<float,64>a{},b{};for(int k=0;k<64;k++){auto ap=p.offsetBuffer_.v[(o-begin)*64+k]/sizeof(T),bp=pl.offsetBuffer_.v[(o-begin)*64+k]/sizeof(T);a[k]=ap==sentinel?0.f:value(ap,seed);b[k]=bp==sentinel?0.f:value(bp,seed);}for(int n=64;n>1;n/=2)for(int k=0;k<n/2;k++){a[k]=a[k*2]+a[k*2+1];b[k]=b[k*2]+b[k*2+1];}if(bits(a[0])!=bits(b[0]))fail(t,"CPU pairwise bit mismatch",begin,end);stats.floatBits++;}}}else stats.rejected++;
// Exercise actual InitOuter cached-row resets after wide planning or rejection.
for(int64_t row=begin/t.d.outputShape[t.d.rank-1];row<=(end-1)/t.d.outputShape[t.d.rank-1];row++){P::Planner<T>fresh;PL::Planner<T>freshPL;fresh.Setup(t.d,padding,layout,begin,end);freshPL.Setup(t.d,padding,layout,begin,end);fresh.InitOuterPrefix();freshPL.InitOuterPrefix();auto expected=fresh.Bases(row);if(p.Bases(row)!=expected||pl.Bases(row)!=expected||freshPL.Bases(row)!=expected)fail(t,"fallback cursor/base reset mismatch",begin,end);stats.fallbackRows++;if(p.InitOuter(row))p.NextOuter();if(pl.InitOuter(row))pl.NextOuter();if(p.Bases(row)!=expected||pl.Bases(row)!=expected)fail(t,"partially advanced cached row mismatch",begin,end);stats.partialResets++;}
// Same object, same shapes, new front values: Setup follows actual Init lifetime.
if(t.d.rank>0&&t.d.totalInput>0){TestCase changed=t;changed.front.back()+=1;changed.back.back()-=1;auto changedPads=pads(changed,!layout);p.Setup(changed.d,changedPads,!layout,begin,end);pl.Setup(changed.d,changedPads,!layout,begin,end);bool pp=p.TryWideCertifiedFlat(),cc=pl.TryWideCertifiedFlat();if(pp!=cc||p.offsetBuffer_.v!=pl.offsetBuffer_.v)fail(t,"changed padding call reuse",begin,end);stats.paddingReuse++;}}
int64_t ceildiv(int64_t a,int64_t b){return a/b+(a%b!=0);}
void runCase(TestCase&t){if(t.d.totalOutput<=0||t.d.totalOutput>256||t.d.totalInput>8192)return;stats.cases++;for(bool layout:{false,true}){std::set<std::pair<int64_t,int64_t>>ranges;auto width=t.d.outputShape[t.d.rank-1];for(int64_t begin:{0LL,1LL,7LL,15LL,31LL,32LL,63LL})for(int64_t count:std::vector<int64_t>{1,8,16,31,32,33,63,64,65,127,128,129,width-1,width,width+1})if(begin<t.d.totalOutput&&count>0)ranges.insert({begin,std::min(begin+count,t.d.totalOutput)});for(auto r:ranges){runRange<float>(t,r.first,r.second,layout,false);runRange<uint16_t>(t,r.first,r.second,layout,false);}for(int64_t cores:{1LL,2LL,4LL,8LL,16LL,32LL,64LL})for(int bytes:{2,4}){int64_t align=32/bytes;bool small=t.d.totalInput<=8192&&t.d.totalOutput<=256;int64_t work=small?32:256;int64_t useful=std::max<int64_t>(1,ceildiv(std::max(t.d.totalInput,t.d.totalOutput),work));int64_t requested=std::min<int64_t>(cores,std::min(useful,ceildiv(t.d.totalOutput,align)));int64_t factor=ceildiv(ceildiv(t.d.totalOutput,requested),align)*align;for(int64_t begin=0;begin<t.d.totalOutput;begin+=factor){if(bytes==2)runRange<uint16_t>(t,begin,std::min(begin+factor,t.d.totalOutput),layout,true);else runRange<float>(t,begin,std::min(begin+factor,t.d.totalOutput),layout,true);}}}}
int main(){try{
// These legal-domain shapes use nonnegative paddings and supplied reference mode vocabulary.
for(int mode=0;mode<=4;mode++)for(int width:{1,2,7,15,31,32,33})for(int prefix:{0,1,2}){std::vector<int64_t>in={2,3,width+4},out={2,3,width},front={0,0,2};if(prefix==0){in[0]+=2;front[0]=1;}if(prefix<=1){in[1]+=2;front[1]=1;}auto t=make(in,out,front,mode,"width-prefix");runCase(t);}
for(int n:{0,31,32,33,63,64,65})for(int mode=0;mode<=4;mode++){auto t=make({n,1},{1,1},{n? n/2:0,0},mode,"outer-boundary");runCase(t);auto l=make({1,n},{1,1},{0,n?n/2:0},mode,"last-boundary");runCase(l);}
// Outer65 forces early reject with an incompletely advanced cursor; partial identity prefix remains active.
for(int mode:{1,2,3,4}){auto t=make({2,65,3},{2,1,1},{0,32,1},mode,"prefix-reject65");runCase(t);}
std::mt19937_64 rng(20261117);for(int i=0;i<180;i++){int rank=1+rng()%4;std::vector<int64_t>in(rank),out(rank),front(rank);int64_t total=1;for(int a=0;a<rank;a++){int64_t n=1+rng()%(a==rank-1?35:4);if(total*n>256)n=1;out[a]=n;total*=n;int64_t delta=rng()%5;in[a]=n+delta;front[a]=rng()%(delta+1);}auto t=make(in,out,front,rng()%5,"seeded-positive-padding");runCase(t);}
std::cout<<"{\"status\":\"PASS\",\"device_execution\":false,\"seed\":20261117,\"cases\":"<<stats.cases<<",\"ranges\":"<<stats.ranges<<",\"host_ranges\":"<<stats.hostRanges<<",\"synthetic_ranges\":"<<stats.syntheticRanges<<",\"accepted\":"<<stats.accepted<<",\"rejected\":"<<stats.rejected<<",\"cache_active_ranges\":"<<stats.cacheActive<<",\"source_offsets\":"<<stats.sourceOffsets<<",\"fallback_rows\":"<<stats.fallbackRows<<",\"partial_cursor_resets\":"<<stats.partialResets<<",\"padding_reuse_checks\":"<<stats.paddingReuse<<",\"cpu_pairwise_bit_checks\":"<<stats.floatBits<<",\"contributor_counts\":[";bool comma=false;for(auto k:stats.contributorBoundaries){if(comma)std::cout<<",";std::cout<<k;comma=true;}std::cout<<"],\"width_ranges\":{";comma=false;for(auto x:stats.widths){if(comma)std::cout<<",";std::cout<<"\\\""<<x.first<<"\\\":"<<x.second;comma=true;}std::cout<<"},\"prefix_ranges\":{";comma=false;for(auto x:stats.prefix){if(comma)std::cout<<",";std::cout<<"\\\""<<x.first<<"\\\":"<<x.second;comma=true;}std::cout<<"}}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 3;}}
