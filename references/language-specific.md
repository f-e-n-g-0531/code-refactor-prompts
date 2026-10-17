# 分语言定制要点

用法：把 SKILL.md 主模板里的「{语言/框架}」「{测试命令}」「{重构目标}」替换成下面对应语言的内容；「红线」抄进【硬约束】。本文件是 specialized-prompts.md 第 6 节的完整参考。

## Java

- 基线版本：Java 17 / 21（LTS）
- 验证：`mvn test` 或 `gradle test`；静态：`mvn spotbugs:check` / `./gradlew checkstyleMain`
- 惯用重构目标：
  - Stream + Collectors（groupingBy / partitionBy / toMap）替代手写 for 累加
  - Optional 替代「返回 null 表示可能无值」；record 替代纯数据 POJO
  - sealed interface + switch 模式匹配替代 instanceof 链；text block 替代字符串拼接
  - try-with-resources 管理 Closeable；局部可推断处用 `var`
- 红线：保持对外函数签名不变；Optional 里不放 null；金额用 BigDecimal；不做可读性倒退的「为流式而流式」

## Python

- 基线版本：Python 3.11+
- 验证：`pytest`；静态：`ruff check` + `ruff format` / `mypy`
- 惯用重构目标：
  - 推导式替代手写循环；enumerate 替代手动计数；with 管理资源
  - 补类型注解（PEP 484/585/604：`list[str]`、`str | None`）；dataclass / Pydantic 替代手写 __init__/__eq__
  - f-string 替代 % / .format()；match/case 替代长 if-elif；海象运算符 `:=` 仅在更清晰时用
  - pathlib 替代 os.path 字符串拼接
- 红线：可变默认参数（`def f(lst=[])`）改为 None + 内部初始化；闭包晚绑定用默认参数捕获；大集合用生成器惰性求值

## JavaScript / TypeScript

- 验证：`npm test`（Jest / Vitest）；`tsc --noEmit`；ESLint + Prettier
- 惯用重构目标：
  - var → const/let；函数表达式 → 箭头函数；模板字符串替代拼接；解构 + 展开替代 Object.assign/concat
  - 回调地狱 → async/await；独立请求用 Promise.all 并行
  - TS：类型收窄替代断言；unknown 替代 any；as const、字面量联合、可选链 `?.` 与空值合并 `??`
- 红线：开启 strict 模式；别滥用 `!`（非空断言）与 any；改 async 后保持错误传播语义一致

## React

- 验证：`npm test`（Testing Library）；ESLint（react-hooks 插件）
- 惯用重构目标：
  - Class 组件 → 函数组件 + Hooks；生命周期 → useEffect（注意依赖数组）
  - 重复逻辑抽成自定义 Hook（`useXxx`）
  - 大组件按职责拆分（每个 <100 行）：展示组件 / 容器 / 受控组件
  - useMemo / useCallback 仅在确有收益时使用
- 红线：依赖数组必须完整（否则闭包读到旧值）；Hook 调用顺序稳定（不得写在条件分支里）；保持 props / 对外 API 不变

## Go

- 验证：`go test ./...`；`go vet` + `gofmt`/`goimports`；golangci-lint
- 惯用重构目标（参考 Effective Go / Go Code Review Comments / Uber Go Style）：
  - 小而面向消费者的接口替代大接口
  - 显式错误处理：`if err != nil { return ..., fmt.Errorf("...: %w", err) }`；errors.Is / As 替代 == 比较
  - context 贯穿 IO；结构体 + 构造函数替代全局状态；组合（embedding）替代继承
- 红线：不得忽略 error；不用 panic 控制流程；保持导出 API 签名不变；别复制含锁的结构体

## Rust

- 验证：`cargo test`；`cargo clippy -- -D warnings`；`cargo fmt`
- 惯用重构目标：
  - 用 enum + struct 让非法状态不可表示；避免「魔法布尔 + 字段」拼状态
  - 返回 `Result<T, 自定义错误>`（库用 thiserror、应用用 anyhow）；`?` 传播错误
  - 默认借用，仅在确有理由时 clone；迭代器 + 组合子（map / and_then / ok_or）替代手写索引循环
  - 把不变式编码进类型系统，而非运行时断言
- 红线：去掉 unwrap/expect（测试与已证明不变式除外）；不轻易 unsafe（需书面理由）；clippy 全绿；不为「消生命周期」而滥用 Arc/Mutex

## C# / .NET

- 验证：`dotnet test`；`dotnet format`；启用 nullable 与分析器
- 惯用重构目标：
  - 开启 nullable reference types 并处理警告；用 record 表达值语义
  - LINQ 替代手写循环；switch 表达式 + 模式匹配替代 if/else 链；using declaration 管理 IDisposable
  - CancellationToken 贯穿异步 API；依赖抽象（接口）而非具体类
- 红线：绝不 `.Result` / `.Wait()` 阻塞异步；避免 sync-over-async；保持公开方法签名与异常契约不变

## C++

- 验证：CTest / GoogleTest / Catch2；`clang-tidy` / `clang-format`；ASan/UBSan
- 惯用重构目标：
  - RAII（智能指针、容器）替代裸 new/delete；std::unique_ptr 表达所有权
  - const / constexpr、范围 for、std::span / string_view 替代「指针 + 长度」
  - 算法库替代手写循环；移动语义（std::move）仅在确有收益处；三/五法则显式化
- 红线：不改变对象生命周期 / 所有权语义；重构不得引入悬垂引用或 UB；保持 ABI / 公开接口稳定

## SQL

- 说明：SQL「重构」以等价改写 + 性能为目标
- 验证：EXPLAIN / 执行计划前后对比；事务 + 回滚下核对结果集等价（COUNT / 校验和 / 抽样）
- 惯用重构目标：
  - 消除 N+1（合并为 JOIN / 集合操作）；用参数化查询防注入
  - 拆复杂查询为 CTE 提可读；去重复子查询；明确索引使用；避免 SELECT * 与隐式类型转换
- 红线：结果集必须等价；不得改变 NULL 语义与排序；性能改动附执行计划前后对比

## 其余（Ruby / PHP）

- Ruby：`rspec`；惯用 Enumerable、块与 yield、符号哈希、guard clause；避免猴子补丁滥用。
- PHP：`composer test`（PHPUnit）+ PHPStan / Psalm；惯用类型声明（7.4+ 属性、8.x union / enum / match）；少用全局状态；用异常而非返回码。
