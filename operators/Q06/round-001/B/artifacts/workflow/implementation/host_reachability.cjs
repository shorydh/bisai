const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../../..');
const source=fs.readFileSync(path.join(root,'P/op_host/pad_v3_grad_tiling.cpp'),'utf8');
const a=source.indexOf('        const bool smallOutput ='),b=source.indexOf('    context->SetBlockDim(blockDim);',a);
const excerpt=source.slice(a,b);
if(!excerpt.includes('std::max(tiling->totalInput, tiling->totalOutput)')||!excerpt.includes('alignedBlocks * alignment'))throw Error('Host formula changed');
const ceil=(a,b)=>Math.floor(a/b)+(a%b!==0?1:0);
const records=[];let examined=0,violations=0,width32HighCoreCacheRanges=0;
for(const bytes of [2,4])for(let totalOut=1;totalOut<=256;totalOut++)for(const totalIn of [0,1,31,32,33,127,128,255,256,257,8191,8192])for(const cores of [1,2,4,8,16,32,64]){
 const alignment=32/bytes,smallOutput=totalIn<=8192&&totalOut<=256,workPerCore=smallOutput?32:256;
 const useful=Math.max(1,ceil(Math.max(totalIn,totalOut),workPerCore));
 const requested=Math.min(cores,Math.min(useful,ceil(totalOut,alignment)));
 const factor=ceil(ceil(totalOut,requested),alignment)*alignment;
 const counts=[];for(let start=0;start<totalOut;start+=factor)counts.push(Math.min(factor,totalOut-start));
 examined++;
 if(cores>=ceil(totalOut,32)&&factor>32)violations++;
 if(cores>=8&&totalOut%32===0&&counts.some(c=>c>32))width32HighCoreCacheRanges++;
 if([31,32,33].some(w=>totalOut%w===0)&&[32,256,8192].includes(totalIn)&&[1,8,32].includes(cores))records.push({bytes,totalOut,totalIn,cores,blockFactor:factor,counts,guardByWidth:[31,32,33].map(width=>({width,cacheRanges:counts.filter(c=>width<=32&&c>width).length}))});
}
const result={status:violations===0&&width32HighCoreCacheRanges===0?'PASS':'FAIL',device_execution:false,actual_official_core_count:null,formula_source:'../../../P/op_host/pad_v3_grad_tiling.cpp',formula_excerpt_sha256:crypto.createHash('sha256').update(excerpt).digest('hex'),examined,conditional_statement:'If coreNum>=ceil(totalOutput/32), totalInput<=8192,totalOutput<=256 and dtype bytes2/4, Host blockFactor<=32, so width32 count>width cache never activates; width33 guard always false.',violations,width32_core_ge_8_activation_violations:width32HighCoreCacheRanges,limits:'Source formula enumeration over boundary input totals and core counts; not measured official hardware or full Host validation. Low core counts may activate width32.',examples:records};
fs.writeFileSync(path.join(__dirname,'host-schedule-excerpt.cpp.txt'),excerpt);
fs.writeFileSync(path.join(__dirname,'host-reachability.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({status:result.status,examined,violations,width32HighCoreCacheRanges}));
