const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../../..');
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
const headers=Object.fromEntries(['F','P','PL'].map(arm=>[arm,fs.readFileSync(path.join(root,arm,'op_kernel/pad_v3_grad.h'),'utf8')]));
function method(h,name){const match=h.match(new RegExp('    __aicore__ inline (?:void|bool) '+name+'\\(')); if(!match)throw Error(name); const line=match.index;let brace=h.indexOf('{',line),level=1,i=brace+1;for(;level;i++){if(h[i]==='{')level++;if(h[i]==='}')level--;}return h.slice(line,i);}
const indexStart=headers.P.indexOf('namespace PadV3GradIndex {');
const indexEnd=headers.P.indexOf('} // namespace PadV3GradIndex')+'} // namespace PadV3GradIndex'.length;
const indexCode=headers.P.slice(indexStart,indexEnd);
for(const h of Object.values(headers))if(h.slice(h.indexOf('namespace PadV3GradIndex {'),h.indexOf('} // namespace PadV3GradIndex')+'} // namespace PadV3GradIndex'.length)!==indexCode)throw Error('Index helper changed');
const common=`#include <algorithm>
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
${indexCode}
using PadV3GradIndex::Contributors;using PadV3GradIndex::MakeContributors;
`;
let classes='';const extraction=[];
for(const [arm,h]of Object.entries(headers)){
 const helpers=['InitOuter','NextOuter'];if(arm!=='F')helpers.unshift('InitOuterPrefix');
 const pieces=helpers.map(n=>method(h,n));let wide=method(h,'TryWideCertifiedFlat');const cut=wide.indexOf('        auto input = inputBuffer_.Get<T>();');if(cut<0)throw Error('cut');wide=wide.slice(0,cut)+'        maxContributorsObserved=maxContributors;\n        return true;\n    }';
 extraction.push({arm,header_sha256:sha(h),helpers:helpers.map((name,i)=>({name,sha256:sha(pieces[i])})),wide_planning_prefix_sha256:sha(wide),modifications:['Device Sync no-op only in CPU harness','OffsetTensor stores uint32 byte offsets in std::vector','Cut wide function before input DataCopy; append observed max and return true','No device floating/vector/certificate execution']});
 classes+=`namespace ${arm}{template<class T>class Planner{public:
Data*data_=nullptr;Contributors outer_[32]{};int64_t position_[32]{},front_[32]{},rank_=0,outerStart_=0,begin_=0,end_=0,base_=0,cachedOuterRow_=-1,cachedOuterBase_=0,inputWidth_=1,outputWidth_=1,maxContributorsObserved=-1;bool cachedOuterValid_=false;OffsetBuffer offsetBuffer_;
void Setup(Data& data,const std::vector<int64_t>& pads,bool contiguous,int64_t begin,int64_t end){data_=&data;cachedOuterRow_=-1;cachedOuterValid_=false;rank_=data.rank;begin_=begin;end_=end;inputWidth_=rank_==0?1:data.inputShape[rank_-1];outputWidth_=rank_==0?1:data.outputShape[rank_-1];for(int64_t d=0;d<rank_;++d){const int64_t index=contiguous?2*d:d;front_[d]=pads.at(index);}offsetBuffer_.v.clear();}
${pieces.join('\n')}
${wide}
std::vector<int64_t> Bases(int64_t row){std::vector<int64_t>v;if(InitOuter(row)){do{v.push_back(base_);if(v.size()>8192)throw std::runtime_error("outer overflow");}while(NextOuter());}return v;}
};}
`;
}
const driver=fs.readFileSync(path.join(__dirname,'planner_driver.cpp.txt'),'utf8');
fs.writeFileSync(path.join(__dirname,'planner_harness.cpp'),common+classes+driver);
fs.writeFileSync(path.join(__dirname,'harness-extraction.json'),JSON.stringify({source:'Actual frozen F/P/PL header planning prefixes and unchanged helpers',device_execution:false,extraction,generated_sha256:sha(common+classes+driver)},null,2)+'\n');
