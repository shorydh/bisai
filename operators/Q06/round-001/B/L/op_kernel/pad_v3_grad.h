#ifndef PADV3GRAD_H
#define PADV3GRAD_H

#include "kernel_operator.h"
#include "kernel_tiling/kernel_tiling.h"
#include "pad_v3_grad_tiling_data.h"
#include "pad_v3_grad_tiling_key.h"
#define PADV3GRAD_INLINE __aicore__ inline
#ifndef PAD_V3_GRAD_INDEX_H
#define PAD_V3_GRAD_INDEX_H

#include <cstdint>

// The exact arithmetic used on the device is also tested by a portable oracle.
#ifndef PADV3GRAD_INLINE
#define PADV3GRAD_INLINE inline
#endif

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
#endif

#undef PADV3GRAD_INLINE

namespace NsPadV3Grad {
using namespace AscendC;
using PadV3GradIndex::Contributors;
using PadV3GradIndex::MakeContributors;

constexpr int64_t TILE_ELEMENTS = 1024;
constexpr int64_t CACHE_ELEMENTS = 8192;
constexpr int64_t MAX_GATHER_PASSES = 8;

// Every core exclusively owns a contiguous output interval. Each output is
// gathered from the inverse pad map, so no atomic updates or workspace are needed.
template <typename T, typename Meta = PadV3GradTilingData> class PadV3Grad {
public:
    __aicore__ inline void Init(GM_ADDR x, GM_ADDR paddings, GM_ADDR y,
                               const Meta *data)
    {
        data_ = data;
        cachedOuterRow_ = -1;
        x_.SetGlobalBuffer(reinterpret_cast<__gm__ T *>(x), data_->totalInput);
        y_.SetGlobalBuffer(reinterpret_cast<__gm__ T *>(y), data_->totalOutput);
        begin_ = static_cast<int64_t>(GetBlockIdx()) * data_->blockFactor;
        end_ = Min(begin_ + data_->blockFactor, data_->totalOutput);
        rank_ = data_->rank;
        inputWidth_ = rank_ == 0 ? 1 : data_->inputShape[rank_ - 1];
        outputWidth_ = rank_ == 0 ? 1 : data_->outputShape[rank_ - 1];
        identity_ = data_->totalInput == data_->totalOutput;
        GlobalTensor<int32_t> pad32;
        GlobalTensor<int64_t> pad64;
        if (data_->readPaddings != 0) {
            if (data_->paddingsDtype == 0) {
                pad32.SetGlobalBuffer(reinterpret_cast<__gm__ int32_t *>(paddings), 2 * rank_);
            } else {
                pad64.SetGlobalBuffer(reinterpret_cast<__gm__ int64_t *>(paddings), 2 * rank_);
            }
        }
        for (int64_t d = 0; d < rank_; ++d) {
            if (data_->readPaddings != 0) {
                const int64_t index = data_->paddingsContiguous != 0 ? 2 * d : d;
                front_[d] = data_->paddingsDtype == 0 ? static_cast<int64_t>(pad32.GetValue(index))
                                                     : pad64.GetValue(index);
            } else {
                front_[d] = data_->padFront[d];
            }
            identity_ = identity_ && front_[d] == 0 &&
                        data_->inputShape[d] == data_->outputShape[d];
        }
        if (begin_ >= end_) {
            return;
        }
        // Explicit buffers use 127168 bytes for float and 120992 for half,
        // below 128KiB and separate from Select's reserved 8KiB at 184KiB.
        // An extra aligned input block holds a zero sentinel for missing gathers.
        const bool smallFlat = data_->totalInput <= CACHE_ELEMENTS && data_->totalOutput <= 256;
        pipe_.InitBuffer(inputBuffer_, (CACHE_ELEMENTS + 16) * sizeof(T));
        pipe_.InitBuffer(outputBuffer_, TILE_ELEMENTS * sizeof(T));
        pipe_.InitBuffer(gatherBuffer_, (smallFlat ? CACHE_ELEMENTS : TILE_ELEMENTS) * sizeof(T));
        pipe_.InitBuffer(offsetBuffer_, MAX_GATHER_PASSES * TILE_ELEMENTS * sizeof(uint32_t));
        pipe_.InitBuffer(sumBuffer_, TILE_ELEMENTS * sizeof(float));
        pipe_.InitBuffer(floatBuffer_, (smallFlat && sizeof(T) == sizeof(half) ? CACHE_ELEMENTS : TILE_ELEMENTS) * sizeof(float));
        pipe_.InitBuffer(nextBuffer_, TILE_ELEMENTS * sizeof(float));
        pipe_.InitBuffer(errorBuffer_, TILE_ELEMENTS * sizeof(float));
        pipe_.InitBuffer(tempBuffer_, TILE_ELEMENTS * sizeof(float));
        pipe_.InitBuffer(correctionBuffer_, TILE_ELEMENTS * sizeof(float));
        pipe_.InitBuffer(maskBuffer_, TILE_ELEMENTS / 8);
    }

    __aicore__ inline void Process()
    {
        if (begin_ >= end_) {
            return;
        }
        if (identity_) {
            CopyIdentity();
            return;
        }
        if (TryWideCertifiedFlat()) {
            return;
        }
        if (TryCertifiedFlat()) {
            return;
        }
        if (data_->totalInput <= CACHE_ELEMENTS && data_->totalOutput <= 256) {
            if (SmallFlatTile()) { return; }
            ScalarTileSmall();
            return;
        }
        int64_t directBegin = 0;
        int64_t directEnd = 0;
        DirectInterval(directBegin, directEnd);
        for (int64_t output = begin_; output < end_;) {
            const int64_t column = output % outputWidth_;
            int64_t count = Min(Min(outputWidth_ - column, end_ - output), TILE_ELEMENTS);
            const int64_t row = output / outputWidth_;
            const bool hasOuter = InitOuter(row);
            bool contiguous = rank_ == 0 ||
                (inputWidth_ == outputWidth_ && front_[rank_ - 1] == 0);
            // A padded row often has a large interior with exactly one source
            // per output. Split at its boundaries and copy that interval directly.
            if (!contiguous && directEnd > directBegin) {
                if (column < directBegin) {
                    count = Min(count, directBegin - column);
                } else if (column < directEnd) {
                    count = Min(count, directEnd - column);
                    contiguous = true;
                }
            }
            // Edge reductions at the two endpoints can be much longer than the
            // interior. Keep them in separate tiles so interior lanes vectorize.
            if (!contiguous && data_->mode == PadV3GradIndex::EDGE && outputWidth_ > 1) {
                if (column == 0) {
                    count = 1;
                } else if (column < outputWidth_ - 1) {
                    count = Min(count, outputWidth_ - 1 - column);
                }
            }
            int64_t passes = 0;
            if (!contiguous && hasOuter) {
                passes = PrepareGather(column, count);
            }
            if (contiguous || !hasOuter || passes <= MAX_GATHER_PASSES) {
                VectorTile(output, row, column, count, contiguous, passes, hasOuter);
            } else {
                ScalarTile(output, row, column, count);
            }
            output += count;
        }
    }

private:
    __aicore__ inline int64_t Min(int64_t a, int64_t b) const { return a < b ? a : b; }

    __aicore__ inline void DirectInterval(int64_t &first, int64_t &last) const
    {
        if (rank_ == 0 || outputWidth_ <= 1) { return; }
        const int64_t front = front_[rank_ - 1];
        // Conservative intervals for nonnegative padding. Crops and very large
        // periodic pads retain the general inverse-map implementation.
        if (front < 0 || front >= outputWidth_ || inputWidth_ < outputWidth_ ||
            front > inputWidth_ - outputWidth_) { return; }
        const int64_t back = inputWidth_ - outputWidth_ - front;
        if (back >= outputWidth_) { return; }
        if (data_->mode == PadV3GradIndex::CONSTANT) {
            first = 0; last = outputWidth_;
        } else if (data_->mode == PadV3GradIndex::EDGE) {
            first = front == 0 ? 0 : 1;
            last = back == 0 ? outputWidth_ : outputWidth_ - 1;
        } else if (data_->mode == PadV3GradIndex::REFLECT) {
            first = front == 0 ? 0 : front + 1;
            last = back == 0 ? outputWidth_ : outputWidth_ - 1 - back;
        } else if (data_->mode == PadV3GradIndex::SYMMETRIC) {
            first = front; last = outputWidth_ - back;
        } else if (data_->mode == PadV3GradIndex::CIRCULAR) {
            first = back; last = outputWidth_ - front;
        }
    }

    template <HardEvent event> __aicore__ inline void Sync()
    {
        const auto id = pipe_.FetchEventID<event>();
        SetFlag<event>(id);
        WaitFlag<event>(id);
    }

    __aicore__ inline void Load(int64_t offset, int64_t count)
    {
        // The same buffer serves vector rows and scalar read-cache blocks.
        Sync<HardEvent::V_MTE2>();
        Sync<HardEvent::S_MTE2>();
        DataCopyExtParams params{1, static_cast<uint32_t>(count * sizeof(T)), 0, 0, 0};
        DataCopyPadExtParams<T> padding{false, 0, 0, static_cast<T>(0)};
        DataCopyPad(inputBuffer_.Get<T>(), x_[offset], params, padding);
    }

    __aicore__ inline void Store(int64_t offset, int64_t count, bool scalar)
    {
        if (scalar) {
            Sync<HardEvent::S_MTE3>();
        } else {
            Sync<HardEvent::V_MTE3>();
        }
        DataCopyExtParams params{1, static_cast<uint32_t>(count * sizeof(T)), 0, 0, 0};
        DataCopyPad(y_[offset], outputBuffer_.Get<T>(), params);
        // Both scalar and vector paths may reuse this buffer on the next tile.
        Sync<HardEvent::MTE3_V>();
        Sync<HardEvent::MTE3_S>();
    }

    __aicore__ inline void CopyIdentity()
    {
        for (int64_t offset = begin_; offset < end_;) {
            const int64_t count = Min(end_ - offset, CACHE_ELEMENTS);
            Load(offset, count);
            Sync<HardEvent::MTE2_MTE3>();
            DataCopyExtParams params{1, static_cast<uint32_t>(count * sizeof(T)), 0, 0, 0};
            DataCopyPad(y_[offset], inputBuffer_.Get<T>(), params);
            Sync<HardEvent::MTE3_MTE2>();
            offset += count;
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

    // Reduce one contiguous group of 32 FP32 contributors per output. The
    // measured absolute sum certifies the ordinary atol+rtol contract; it is
    // not a guarantee for a pure-relative comparison near zero.
    __aicore__ inline void ReduceGroups(const LocalTensor<float> &dst,
                                        const LocalTensor<float> &src, int64_t count,
                                        int32_t terms = 32, int32_t slots = 32)
    {
        if (count <= 255) {
            WholeReduceSum(dst, src, terms, static_cast<int32_t>(count), 1, 1, slots / 8);
        } else {
            WholeReduceSum(dst, src, terms, 128, 1, 1, slots / 8);
            WholeReduceSum(dst[128], src[128 * slots], terms, 128, 1, 1, slots / 8);
        }
    }

    __aicore__ inline bool StoreCertified(const LocalTensor<float> &values, int64_t count,
                                            int32_t terms = 32, int32_t slots = 32,
                                            float threshold = 26.0f, bool dynamicFloat = false)
    {
        const uint32_t n = static_cast<uint32_t>(count);
        const uint32_t compareCount = static_cast<uint32_t>((count + 63) / 64 * 64);
        auto sum = sumBuffer_.Get<float>();
        auto sumAbs = correctionBuffer_.Get<float>();
        // Gather has finished reading its offsets before this function is
        // called, so their storage is now available for absolute values.
        auto absolute = offsetBuffer_.Get<float>();
        Duplicate(sumAbs, 0.0f, compareCount);
        if constexpr (sizeof(T) == sizeof(float)) {
            if (dynamicFloat) {
                Duplicate(sum, 0.0f, compareCount);
                PipeBarrier<PIPE_V>();
            }
        }
        ReduceGroups(sum, values, count, terms, slots);
        Abs(absolute, values, n * static_cast<uint32_t>(slots));
        PipeBarrier<PIPE_V>();
        ReduceGroups(sumAbs, absolute, count, terms, slots);
        PipeBarrier<PIPE_V>();
        auto mask = maskBuffer_.Get<uint8_t>();
        // The dynamic FP32 certificate retains both absolute and relative
        // error budgets. Separate ordered masks reject NaN/Inf; the small
        // top-end exclusion ensures that the FP64 reference cannot cast to
        // infinity while the FP32 tree happens to round down to FLT_MAX.
        if constexpr (sizeof(T) == sizeof(float)) {
            if (dynamicFloat) {
                auto absSum = tempBuffer_.Get<float>();
                auto budget = nextBuffer_.Get<float>();
                Abs(absSum, sum, compareCount);
                PipeBarrier<PIPE_V>();
                Adds(budget, absSum, 1.0f, compareCount);
                PipeBarrier<PIPE_V>();
                Muls(budget, budget, threshold, compareCount);
                PipeBarrier<PIPE_V>();
                Compare(mask, sumAbs, budget, CMPMODE::LE, compareCount);
                CompareScalar(mask[32], sumAbs, 3.4027975e38F, CMPMODE::LE, compareCount);
                CompareScalar(mask[64], absSum, 3.402823466e38F, CMPMODE::LE, compareCount);
            } else {
                CompareScalar(mask, sumAbs, threshold, CMPMODE::LE, compareCount);
            }
        } else {
            CompareScalar(mask, sumAbs, threshold, CMPMODE::LE, compareCount);
        }
        Sync<HardEvent::V_S>();
        for (int64_t byte = 0; byte < (count + 7) / 8; ++byte) {
            const int64_t bits = Min(8, count - byte * 8);
            const uint8_t wanted = static_cast<uint8_t>((1u << bits) - 1u);
            bool valid = (mask.GetValue(byte) & wanted) == wanted;
            if constexpr (sizeof(T) == sizeof(float)) {
                if (dynamicFloat) {
                    valid = valid && (mask.GetValue(32 + byte) & wanted) == wanted &&
                            (mask.GetValue(64 + byte) & wanted) == wanted;
                }
            }
            if (!valid) {
                // E2 restarts input DMA and index generation. Complete all
                // old readers before those buffers change producer pipelines.
                Sync<HardEvent::S_V>();
                Sync<HardEvent::V_MTE2>();
                return false;
            }
        }
        auto out = outputBuffer_.Get<T>();
        if constexpr (sizeof(T) == sizeof(half)) {
            Cast(out, sum, RoundMode::CAST_RINT, n);
        } else {
            Adds(out, sum, 0.0f, n);
        }
        Store(begin_, count, false);
        return true;
    }

    // A core with at most 128 outputs can use 64 slots per output in the
    // existing 8192-element buffers. No buffer allocation changes are needed.
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
        auto input = inputBuffer_.Get<T>();
        if (data_->totalInput != 0) {
            DataCopyExtParams params{1, static_cast<uint32_t>(data_->totalInput * sizeof(T)), 0, 0, 0};
            DataCopyPadExtParams<T> padding{false, 0, 0, static_cast<T>(0)};
            DataCopyPad(input, x_, params, padding);
            Sync<HardEvent::MTE2_S>();
        }
        input.SetValue(sentinel, static_cast<T>(0));
        Sync<HardEvent::S_V>();
        const uint32_t lanes = static_cast<uint32_t>(count * groupSize);
        auto gathered = gatherBuffer_.Get<T>();
        Gather(gathered, input, offsets, static_cast<uint32_t>(0), lanes);
        PipeBarrier<PIPE_V>();
        const int32_t terms = maxContributors <= 32 ? 32 : 64;
        // The documented pairwise reduction has at most six FP32 stages for
        // 64 lanes. These budgets retain margin even with per-stage error 2u;
        // half pre-rounding error stays below 2^-11, and FP32 keeps its original
        // mixed tolerance plus the finite/top-end guards in StoreCertified.
        const float threshold = sizeof(T) == sizeof(half) ? 512.0f : 64.0f;
        if constexpr (sizeof(T) == sizeof(half)) {
            auto floats = floatBuffer_.Get<float>();
            Cast(floats, gathered, RoundMode::CAST_NONE, lanes);
            PipeBarrier<PIPE_V>();
            return StoreCertified(floats, count, terms, 64, threshold, true);
        } else {
            return StoreCertified(gathered, count, terms, 64, threshold, true);
        }
    }

    __aicore__ inline bool TryCertifiedFlat()
    {
        constexpr int64_t groupSize = 32;
        if (rank_ == 0 || data_->totalInput > CACHE_ELEMENTS || data_->totalOutput > 256) {
            return false;
        }
        const int64_t count = end_ - begin_;
        const int64_t alignElements = 32 / sizeof(T);
        const int64_t sentinel = (data_->totalInput + alignElements - 1) /
                                  alignElements * alignElements;
        auto offsets = offsetBuffer_.Get<uint32_t>();
        Duplicate(offsets, static_cast<uint32_t>(sentinel * sizeof(T)),
                  static_cast<uint32_t>(count * groupSize));
        Sync<HardEvent::V_S>();
        for (int64_t j = 0; j < count; ++j) {
            const int64_t output = begin_ + j;
            const auto last = MakeContributors(output % outputWidth_, inputWidth_, outputWidth_,
                                               front_[rank_ - 1], data_->mode);
            int64_t pass = 0;
            if (last.Size() != 0 && InitOuter(output / outputWidth_)) {
                do {
                    for (int64_t k = 0; k < last.Size(); ++k) {
                        if (pass == groupSize) {
                            Sync<HardEvent::S_V>();
                            return false;
                        }
                        offsets.SetValue(j * groupSize + pass,
                            static_cast<uint32_t>((base_ + last.At(k)) * sizeof(T)));
                        ++pass;
                    }
                } while (NextOuter());
            }
        }
        auto input = inputBuffer_.Get<T>();
        if (data_->totalInput != 0) {
            DataCopyExtParams params{1, static_cast<uint32_t>(data_->totalInput * sizeof(T)), 0, 0, 0};
            DataCopyPadExtParams<T> padding{false, 0, 0, static_cast<T>(0)};
            DataCopyPad(input, x_, params, padding);
            Sync<HardEvent::MTE2_S>();
        }
        input.SetValue(sentinel, static_cast<T>(0));
        Sync<HardEvent::S_V>();
        const uint32_t lanes = static_cast<uint32_t>(count * groupSize);
        auto gathered = gatherBuffer_.Get<T>();
        Gather(gathered, input, offsets, static_cast<uint32_t>(0), lanes);
        PipeBarrier<PIPE_V>();
        if constexpr (sizeof(T) == sizeof(half)) {
            auto floats = floatBuffer_.Get<float>();
            Cast(floats, gathered, RoundMode::CAST_NONE, lanes);
            PipeBarrier<PIPE_V>();
            return StoreCertified(floats, count);
        } else {
            return StoreCertified(gathered, count);
        }
    }

    // Small tensors share a single input DMA and gather across output rows.
    // Reject an expensive inverse map before touching output GM; exceptional
    // FP32 reductions likewise return to the original row/scalar dispatcher.
    __aicore__ inline bool SmallFlatTile()
    {
        constexpr int64_t flatStride = 256;
        constexpr int64_t maxPasses = 32;
        if (rank_ == 0 || data_->totalInput > CACHE_ELEMENTS ||
            data_->totalOutput > flatStride) {
            return false;
        }
        const int64_t count = end_ - begin_;
        int64_t passes = 0;
        const int64_t alignElements = 32 / sizeof(T);
        const int64_t sentinel = (data_->totalInput + alignElements - 1) /
                                  alignElements * alignElements;
        auto offsets = offsetBuffer_.Get<uint32_t>();
        Duplicate(offsets, static_cast<uint32_t>(sentinel * sizeof(T)),
                  static_cast<uint32_t>(flatStride * maxPasses));
        Sync<HardEvent::V_S>();
        // Build each output's complete inverse map once. Rejected plans have
        // touched only UB indices, so Process can still run its original path.
        for (int64_t j = 0; j < count; ++j) {
            const int64_t output = begin_ + j;
            const auto last = MakeContributors(output % outputWidth_, inputWidth_, outputWidth_,
                                               front_[rank_ - 1], data_->mode);
            int64_t pass = 0;
            if (last.Size() != 0 && InitOuter(output / outputWidth_)) {
                do {
                    for (int64_t k = 0; k < last.Size(); ++k) {
                        if (pass == maxPasses) {
                            return false;
                        }
                        offsets.SetValue(pass * flatStride + j,
                            static_cast<uint32_t>((base_ + last.At(k)) * sizeof(T)));
                        ++pass;
                    }
                } while (NextOuter());
            }
            if (pass > passes) {
                passes = pass;
            }
        }
        auto input = inputBuffer_.Get<T>();
        if (passes != 0) {
            DataCopyExtParams params{1, static_cast<uint32_t>(data_->totalInput * sizeof(T)), 0, 0, 0};
            DataCopyPadExtParams<T> padding{false, 0, 0, static_cast<T>(0)};
            DataCopyPad(input, x_, params, padding);
            Sync<HardEvent::MTE2_S>();
            input.SetValue(sentinel, static_cast<T>(0));
        }
        Sync<HardEvent::S_V>();
        accumulationCount_ = 0;
        auto sum = sumBuffer_.Get<float>();
        const uint32_t n = static_cast<uint32_t>(count);
        Duplicate(sum, 0.0f, n);
        Duplicate(correctionBuffer_.Get<float>(), 0.0f, n);
        PipeBarrier<PIPE_V>();
        for (int64_t pass = 0; pass < passes; ++pass) {
            auto gathered = gatherBuffer_.Get<T>();
            Gather(gathered, input, offsets[pass * flatStride], static_cast<uint32_t>(0), n);
            AccumulateVector(gathered, count);
        }
        if constexpr (sizeof(T) == sizeof(float)) {
            if (accumulationCount_ > 1) {
                Sync<HardEvent::V_S>();
                auto mask = maskBuffer_.Get<uint8_t>();
                for (int64_t byte = 0; byte < (count + 7) / 8; ++byte) {
                    const int64_t bits = Min(8, count - byte * 8);
                    const uint8_t wanted = static_cast<uint8_t>((1u << bits) - 1u);
                    if ((mask.GetValue(byte) & wanted) != wanted) {
                        // No GM output has been written. The ordinary Process
                        // loop will split rows before any ScalarTile fallback.
                        return false;
                    }
                }
            }
        }
        Add(sum, sum, correctionBuffer_.Get<float>(), n);
        PipeBarrier<PIPE_V>();
        auto out = outputBuffer_.Get<T>();
        if constexpr (sizeof(T) == sizeof(half)) {
            Cast(out, sum, RoundMode::CAST_RINT, n);
        } else {
            Adds(out, sum, 0.0f, n);
        }
        Store(begin_, count, false);
        return true;
    }

    __aicore__ inline int64_t PrepareGather(int64_t column, int64_t count)
    {
        if (planColumn_ == column && planCount_ == count) { return planPasses_; }
        planColumn_ = -1;
        int64_t passes = 0;
        for (int64_t k = 0; k < MAX_GATHER_PASSES; ++k) {
            windowStart_[k] = inputWidth_;
            windowLength_[k] = -1; // Maximum source coordinate until ranges are finalized.
        }
        for (int64_t j = 0; j < count; ++j) {
            const auto contributors = MakeContributors(column + j, inputWidth_, outputWidth_,
                                                       front_[rank_ - 1], data_->mode);
            if (contributors.Size() > MAX_GATHER_PASSES) {
                return MAX_GATHER_PASSES + 1;
            }
            if (contributors.Size() > passes) {
                passes = contributors.Size();
            }
            if (inputWidth_ > CACHE_ELEMENTS) {
                for (int64_t k = 0; k < contributors.Size(); ++k) {
                    const int64_t index = contributors.At(k);
                    windowStart_[k] = Min(windowStart_[k], index);
                    if (index > windowLength_[k]) {
                        windowLength_[k] = index;
                    }
                }
            }
        }
        const int64_t alignElements = 32 / sizeof(T);
        for (int64_t k = 0; k < passes; ++k) {
            if (inputWidth_ <= CACHE_ELEMENTS) {
                windowStart_[k] = 0;
                windowLength_[k] = inputWidth_;
            } else {
                windowLength_[k] = windowLength_[k] - windowStart_[k] + 1;
            }
            if (windowLength_[k] > CACHE_ELEMENTS || windowLength_[k] <= 0) {
                return MAX_GATHER_PASSES + 1;
            }
            windowSentinel_[k] = (windowLength_[k] + alignElements - 1) / alignElements * alignElements;
        }
        Sync<HardEvent::V_S>();
        auto offsets = offsetBuffer_.Get<uint32_t>();
        for (int64_t j = 0; j < count; ++j) {
            const auto contributors = MakeContributors(column + j, inputWidth_, outputWidth_,
                                                       front_[rank_ - 1], data_->mode);
            for (int64_t k = 0; k < passes; ++k) {
                const int64_t index = k < contributors.Size() ? contributors.At(k) - windowStart_[k]
                                                              : windowSentinel_[k];
                offsets.SetValue(k * TILE_ELEMENTS + j, static_cast<uint32_t>(index * sizeof(T)));
            }
        }
        Sync<HardEvent::S_V>();
        planColumn_ = column;
        planCount_ = count;
        planPasses_ = passes;
        return passes;
    }

    __aicore__ inline void AccumulateVector(const LocalTensor<T> &values, int64_t count)
    {
        PipeBarrier<PIPE_V>();
        if constexpr (sizeof(T) == sizeof(half)) {
            auto floats = floatBuffer_.Get<float>();
            Cast(floats, values, RoundMode::CAST_NONE, static_cast<uint32_t>(count));
            PipeBarrier<PIPE_V>();
            AccumulateFloat(floats, count);
        } else {
            AccumulateFloat(values, count);
        }
    }

    // TwoSum records the rounding error of each addition. This avoids losing
    // small contributions when large positive and negative gradients cancel.
    __aicore__ inline void AccumulateFloat(const LocalTensor<float> &values, int64_t count)
    {
        const uint32_t n = static_cast<uint32_t>(count);
        const uint32_t compareCount = static_cast<uint32_t>((count + 63) / 64 * 64);
        auto sum = sumBuffer_.Get<float>();
        auto next = nextBuffer_.Get<float>();
        auto error = errorBuffer_.Get<float>();
        auto temp = tempBuffer_.Get<float>();
        auto correction = correctionBuffer_.Get<float>();
        auto mask = maskBuffer_.Get<uint8_t>();
        if (accumulationCount_++ == 0) {
            Adds(sum, values, 0.0f, n);
            PipeBarrier<PIPE_V>();
            return;
        }
        Add(next, sum, values, n);
        PipeBarrier<PIPE_V>();
        Sub(temp, next, sum, n);
        PipeBarrier<PIPE_V>();
        Sub(error, next, temp, n);
        PipeBarrier<PIPE_V>();
        Sub(error, sum, error, n);
        Sub(temp, values, temp, n);
        PipeBarrier<PIPE_V>();
        Add(error, error, temp, n);
        PipeBarrier<PIPE_V>();
        Add(correction, correction, error, n);
        Duplicate(temp, 0.0f, compareCount);
        PipeBarrier<PIPE_V>();
        Abs(temp, next, n);
        PipeBarrier<PIPE_V>();
        CompareScalar(mask, temp, 3.402823466e+38F, CMPMODE::LE, compareCount);
        PipeBarrier<PIPE_V>();
        // NaN/Inf must retain ordinary IEEE addition, not an inf-inf correction.
        Select(correction, mask, correction, 0.0f, SELMODE::VSEL_TENSOR_SCALAR_MODE, n);
        Adds(sum, next, 0.0f, n);
        PipeBarrier<PIPE_V>();
    }

    __aicore__ inline void VectorTile(int64_t output, int64_t row, int64_t column,
                                     int64_t count, bool contiguous, int64_t passes, bool hasOuter)
    {
        cacheBase_ = -1;
        accumulationCount_ = 0;
        auto sum = sumBuffer_.Get<float>();
        Duplicate(sum, 0.0f, static_cast<uint32_t>(count));
        Duplicate(correctionBuffer_.Get<float>(), 0.0f, static_cast<uint32_t>(count));
        PipeBarrier<PIPE_V>();
        if (hasOuter && (contiguous || passes != 0)) {
            do {
                auto input = inputBuffer_.Get<T>();
                if (contiguous) {
                    Load(base_ + column + (rank_ == 0 ? 0 : front_[rank_ - 1]), count);
                    Sync<HardEvent::MTE2_V>();
                    AccumulateVector(input, count);
                } else if (inputWidth_ <= CACHE_ELEMENTS) {
                    Load(base_, inputWidth_);
                    // Initialize sentinel after DMA's implicit right padding completes.
                    Sync<HardEvent::MTE2_S>();
                    input.SetValue(windowSentinel_[0], static_cast<T>(0));
                    Sync<HardEvent::S_V>();
                    for (int64_t k = 0; k < passes; ++k) {
                        auto gathered = gatherBuffer_.Get<T>();
                        Gather(gathered, input, offsetBuffer_.Get<uint32_t>()[k * TILE_ELEMENTS],
                               static_cast<uint32_t>(0), static_cast<uint32_t>(count));
                        AccumulateVector(gathered, count);
                    }
                } else {
                    // A wide input row need not fit in UB: each inverse-map
                    // pass loads only the source interval needed by this tile.
                    for (int64_t k = 0; k < passes; ++k) {
                        Load(base_ + windowStart_[k], windowLength_[k]);
                        Sync<HardEvent::MTE2_S>();
                        input.SetValue(windowSentinel_[k], static_cast<T>(0));
                        Sync<HardEvent::S_V>();
                        auto gathered = gatherBuffer_.Get<T>();
                        Gather(gathered, input, offsetBuffer_.Get<uint32_t>()[k * TILE_ELEMENTS],
                               static_cast<uint32_t>(0), static_cast<uint32_t>(count));
                        AccumulateVector(gathered, count);
                    }
                }
            } while (NextOuter());
        }
        if constexpr (sizeof(T) == sizeof(float)) {
            // A finite FP32 reduction can overflow temporarily and later cancel.
            // Recompute exceptional tiles with scaled scalar accumulation. This
            // also retains the ordinary Inf/NaN behavior of non-finite inputs.
            if (accumulationCount_ > 1) {
                Sync<HardEvent::V_S>();
                auto mask = maskBuffer_.Get<uint8_t>();
                for (int64_t byte = 0; byte < (count + 7) / 8; ++byte) {
                    const int64_t bits = Min(8, count - byte * 8);
                    const uint8_t wanted = static_cast<uint8_t>((1u << bits) - 1u);
                    if ((mask.GetValue(byte) & wanted) != wanted) {
                        ScalarTile(output, row, column, count);
                        return;
                    }
                }
            }
        }
        auto out = outputBuffer_.Get<T>();
        Add(sum, sum, correctionBuffer_.Get<float>(), static_cast<uint32_t>(count));
        PipeBarrier<PIPE_V>();
        if constexpr (sizeof(T) == sizeof(half)) {
            Cast(out, sum, RoundMode::CAST_RINT, static_cast<uint32_t>(count));
        } else {
            Adds(out, sum, 0.0f, static_cast<uint32_t>(count));
        }
        Store(output, count, false);
    }

    __aicore__ inline float ReadCached(int64_t offset)
    {
        if (cacheBase_ < 0 || offset < cacheBase_ || offset >= cacheBase_ + cacheCount_) {
            cacheBase_ = offset / CACHE_ELEMENTS * CACHE_ELEMENTS;
            cacheCount_ = Min(CACHE_ELEMENTS, data_->totalInput - cacheBase_);
            Load(cacheBase_, cacheCount_);
            Sync<HardEvent::MTE2_S>();
        }
        return static_cast<float>(inputBuffer_.Get<T>().GetValue(offset - cacheBase_));
    }

    // A power-of-two scale prevents finite intermediate overflow. Contributions
    // retain compensated FP32 precision; true non-finite inputs propagate normally.
    __aicore__ inline void AddScalar(float value, float &sum, float &correction, float &scale)
    {
        constexpr float largest = 3.402823466e+38F;
        value *= scale;
        float next = sum + value;
        if ((next > largest || next < -largest) && sum <= largest && sum >= -largest &&
            value <= largest && value >= -largest) {
            scale *= 0.5f;
            sum *= 0.5f;
            correction *= 0.5f;
            value *= 0.5f;
            next = sum + value;
        }
        if (next <= largest && next >= -largest && sum <= largest && sum >= -largest &&
            value <= largest && value >= -largest) {
            const float absSum = sum < 0 ? -sum : sum;
            const float absValue = value < 0 ? -value : value;
            correction += absSum >= absValue ? (sum - next) + value : (value - next) + sum;
        } else {
            correction = 0;
        }
        sum = next;
    }

    __aicore__ inline void ScalarTileSmall()
    {
        if (data_->totalInput > 0) {
            Load(0, data_->totalInput);
            Sync<HardEvent::MTE2_S>();
        }
        Sync<HardEvent::V_S>();
        auto input = inputBuffer_.Get<T>();
        auto out = outputBuffer_.Get<T>();
        for (int64_t output = begin_; output < end_; ++output) {
            float sum = 0;
            float correction = 0;
            float scale = 1;
            const int64_t column = output % outputWidth_;
            const int64_t row = output / outputWidth_;
            const auto last = MakeContributors(column, inputWidth_, outputWidth_,
                                               front_[rank_ - 1], data_->mode);
            if (last.Size() != 0 && InitOuter(row)) {
                do {
                    for (int64_t k = 0; k < last.Size(); ++k) {
                        const float value = static_cast<float>(input.GetValue(base_ + last.At(k)));
                        AddScalar(value, sum, correction, scale);
                    }
                } while (NextOuter());
            }
            out.SetValue(output - begin_, static_cast<T>((sum + correction) / scale));
        }
        Store(begin_, end_ - begin_, true);
    }

    __aicore__ inline void ScalarTile(int64_t output, int64_t row, int64_t column, int64_t count)
    {
        Sync<HardEvent::V_S>();
        auto out = outputBuffer_.Get<T>();
        for (int64_t j = 0; j < count; ++j) {
            float sum = 0;
            float correction = 0;
            float scale = 1;
            const auto last = MakeContributors(column + j, inputWidth_, outputWidth_,
                                               front_[rank_ - 1], data_->mode);
            if (last.Size() != 0 && InitOuter(row)) {
                do {
                    for (int64_t k = 0; k < last.Size(); ++k) {
                        AddScalar(ReadCached(base_ + last.At(k)), sum, correction, scale);
                    }
                } while (NextOuter());
            }
            out.SetValue(j, static_cast<T>((sum + correction) / scale));
        }
        Store(output, count, true);
    }

    TPipe pipe_;
    TBuf<QuePosition::VECIN> inputBuffer_;
    TBuf<QuePosition::VECOUT> outputBuffer_;
    TBuf<QuePosition::VECCALC> gatherBuffer_;
    TBuf<QuePosition::VECCALC> offsetBuffer_;
    TBuf<QuePosition::VECCALC> sumBuffer_;
    TBuf<QuePosition::VECCALC> floatBuffer_;
    TBuf<QuePosition::VECCALC> nextBuffer_;
    TBuf<QuePosition::VECCALC> errorBuffer_;
    TBuf<QuePosition::VECCALC> tempBuffer_;
    TBuf<QuePosition::VECCALC> correctionBuffer_;
    TBuf<QuePosition::VECCALC> maskBuffer_;
    GlobalTensor<T> x_;
    GlobalTensor<T> y_;
    const Meta *data_ = nullptr;
    Contributors outer_[PAD_V3_GRAD_MAX_RANK];
    int64_t cachedOuterRow_ = -1;
    int64_t cachedOuterBase_ = 0;
    bool cachedOuterValid_ = false;
    int64_t position_[PAD_V3_GRAD_MAX_RANK];
    int64_t front_[PAD_V3_GRAD_MAX_RANK];
    int64_t rank_ = 0;
    int64_t begin_ = 0;
    int64_t end_ = 0;
    int64_t base_ = 0;
    int64_t inputWidth_ = 0;
    int64_t outputWidth_ = 0;
    int64_t windowStart_[MAX_GATHER_PASSES];
    int64_t windowLength_[MAX_GATHER_PASSES];
    int64_t windowSentinel_[MAX_GATHER_PASSES];
    int64_t planColumn_ = -1;
    int64_t planCount_ = -1;
    int64_t planPasses_ = 0;
    int64_t cacheBase_ = -1;
    int64_t cacheCount_ = 0;
    int64_t accumulationCount_ = 0;
    bool identity_ = false;
};
} // namespace NsPadV3Grad
#endif
