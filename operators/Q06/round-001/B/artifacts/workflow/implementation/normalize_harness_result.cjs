const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const raw=fs.readFileSync(path.join(__dirname,'planner-result.raw.txt'),'utf8').replace(/^\uFEFF/,'').trim();
// The GCC diagnostic executable writes escaped quotes only around dynamic map keys.
// Keep the original stdout untouched and normalize only JSON string delimiters.
const result=JSON.parse(raw.replace(/\\"/g,'"'));
result.checker_scope='actual source-derived planning prefix/order/offset/fallback; device kernels/vector math/half arithmetic not executed';
result.official_precision='pending';
result.contributor_65='Targeted outer65/last65 cases execute early wide-path rejection and cached-row fallback reset; accepted slot counts never exceed64';
result.test_domain='Nonnegative paddings and modes0..4 matching restored Host/official reference vocabulary; empty source tested; changed-front call probe may imply negative back and is diagnostic only, not a new legal-domain claim';
result.harness_sha256=crypto.createHash('sha256').update(fs.readFileSync(path.join(__dirname,'planner_harness.cpp'))).digest('hex');
fs.writeFileSync(path.join(__dirname,'planner-result.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result,null,2));
