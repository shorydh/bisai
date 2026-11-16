# PL 可达性静态审计

审计对象为候选七源码 `988e491ec2d8d758adac5caa0e304cc81cb500ade732aadc9427fa1254267d41`，比较父版本 P/1367774。没有删除原路径；本表是源码可达性分类，不能替代设备编译或运行证据。

| 对象 | 分类与依据 |
|---|---|
| 原 Host 注册、Tiling、四个 TilingKey 模板入口 | KEEP：原37文件逐字节一致，原 dtype/rank 分派仍可达。 |
| 原 identity/certified/wide/general 回退链 | KEEP：主头除两处缓存移植外逐字节一致，拒绝时原控制流保持。 |
| `InitOuterPrefix/InitOuter/NextOuter` | KEEP：P 原文不变；贡献枚举、同一行 cursor/base 重置及前缀索引影响所有后续回退。 |
| 新 `lastPlans[32]` 及初始化 | KEEP：wide 守卫通过且 `outputWidth<=32 && count>outputWidth` 时可达；例如低核数多行区间，以及 width31/count32。函数局部，不跨调用共享。 |
| `reuseLast==false` 的原生成分支 | KEEP：width33及以上、count<=width必经；常见高核数下width32也必经。 |
| 缓存初始化后的 wide 拒绝 | KEEP：outer/last总贡献超过64仍拒绝；此时缓存生成成本可能无用，不能删分支或暗改守卫。 |

新增代码中没有证实不可达的语句，因此无 DELETE。真实设备栈大小、spill、编译器代码生成和非目标设备动态兼容性为未测属性，不用“无死代码”推断资源安全或性能提升。
