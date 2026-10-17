# 实战样例：遗留 Rust 代码的行为基线（无测试）

演示工作流 2 + 工作流 4：先为没有测试的遗留 Rust 代码生成「行为基线测试」锁住当前行为，再做结构化重构，最后用差分测试证明等价。流程见 references/workflows.md。

本样例与 Go 样例使用同一套「隐藏规则」（整数截断、满减阈值、VIP 可为负），方便对照两种语言的迁移方式。代码块带 `<!-- verify:file=... -->` 标记，CI 会用 .github/scripts/verify_examples.py 实际执行 `cargo test`。

<!-- verify:run
cargo test --quiet
-->

## 1. 遗留代码（无测试、魔数遍地）

<!-- verify:file=src/legacy.rs -->
```rust
pub struct Item {
    pub qty: i32,
    pub price: i64, // 单位：分
    pub category: String,
}

pub struct Order {
    pub items: Vec<Item>,
    pub region: String,
    pub vip: bool,
}

pub fn total(order: &Order) -> i64 {
    let mut total: i64 = 0;
    for item in order.items.iter() {
        if item.qty <= 0 {
            continue;
        }
        let mut subtotal = item.price * i64::from(item.qty);
        if item.category == "book" {
            subtotal -= subtotal / 10;
        } else if item.category == "electronics" {
            subtotal -= subtotal / 20;
        }
        total += subtotal;
    }
    if total > 10_000 {
        total -= total / 50;
    }
    if order.region == "US" {
        total += total * 8 / 100;
    } else if order.region == "EU" {
        total += total * 2 / 10;
    }
    if order.vip {
        total -= 300;
    }
    total
}
```

**为什么危险**：字符串当分类（笔误不报错）、魔数散落、整数除法全程截断、满减阈值是 `>` 而非 `>=`、`qty <= 0` 静默跳过、VIP 可把总价减成负数。Rust 编译器能拦住类型错误，但拦不住这些**行为约定**。

## 2. 第一步：行为基线测试（先跑通，不改代码）

```text
为下面的 Rust 函数生成「行为基线测试」，目标是捕捉当前真实行为（即使看起来是 bug 也照原样断言），不要修改被测代码。

- 覆盖：空订单、qty <= 0、book / electronics / 其他分类、总价恰好 10000 与略高于 10000、US / EU / 其他地区、VIP；
- 断言具体到 i64 结果（含整数除法截断后的值）；
- 测试必须在当前代码上直接通过。
{粘贴 src/legacy.rs}
```

生成的基线测试（`cargo test` 通过）：

<!-- verify:file=tests/baseline.rs -->
```rust
use verify_example::legacy::{total, Item, Order};

fn item(qty: i32, price: i64, category: &str) -> Item {
    Item {
        qty,
        price,
        category: category.to_string(),
    }
}

fn order(items: Vec<Item>, region: &str, vip: bool) -> Order {
    Order {
        items,
        region: region.to_string(),
        vip,
    }
}

#[test]
fn baseline_matches_current_behaviour() {
    let cases: Vec<(&str, Order, i64)> = vec![
        ("empty order", order(vec![], "", false), 0),
        (
            "non-positive qty ignored",
            order(vec![item(0, 1000, ""), item(-2, 500, "")], "", false),
            0,
        ),
        (
            "book discount truncates",
            order(vec![item(1, 1000, "book")], "", false),
            900,
        ),
        (
            "electronics discount truncates",
            order(vec![item(2, 1000, "electronics")], "", false),
            1900,
        ),
        (
            "order discount needs strictly above threshold",
            order(vec![item(2, 5000, "")], "", false),
            10_000,
        ),
        (
            "us tax integer division",
            order(vec![item(3, 4000, "book")], "US", false),
            11_430,
        ),
        (
            "eu tax",
            order(vec![item(3, 4000, "book")], "EU", false),
            12_700,
        ),
        (
            "vip can go below zero",
            order(vec![item(1, 100, "book")], "", true),
            -210,
        ),
    ];
    for (name, order, want) in cases {
        assert_eq!(total(&order), want, "{name}");
    }
}
```

> 「eu tax」手算容易得到 12960：忘了 10800 已经触发满减（10800 / 50 = 216），EU 税必须落在 10584 上。**期望值要跑出来，不能算出来**。

## 3. 第二步：重构（套用主模板）

```text
你是资深 Rust 工程师，专注在不改变行为的前提下做重构。

【硬约束】
1. 第 2 步的行为基线测试必须原样通过，一条都不许改；
2. 不改变公开函数 total(&Order) -> i64 与公开结构体字段；
3. 整数除法的截断位置与顺序必须保持一致（含满减与税费的计算顺序）；
4. 不引入新依赖、不改变错误处理与日志。

【重构目标】
1. 用具名常量替换魔法数字（折扣、阈值、税率、VIP 调整）；
2. 把分类折扣、满减、税费拆成单一职责的小函数；
3. 保持 qty <= 0 静默跳过、VIP 可为负等隐式行为不变。

【验收标准】
测试命令：cargo test（含全部行为基线测试）必须通过。
```

## 4. 参考重构结果（行为等价）

为便于差分验证，重构版放在独立模块 `src/refactored.rs`、导出 `refactored::total`；真实重构中它替换 `legacy::total`，其余保持不变。

<!-- verify:file=src/refactored.rs -->
```rust
use crate::legacy::Order;

const BOOK_DISCOUNT_PERCENT: i64 = 10;
const ELECTRONICS_DISCOUNT_PERCENT: i64 = 5;
const ORDER_DISCOUNT_THRESHOLD: i64 = 10_000;
const ORDER_DISCOUNT_DIVISOR: i64 = 50;
const US_TAX_PERCENT: i64 = 8;
const EU_TAX_PERCENT: i64 = 2;
const EU_TAX_DIVISOR: i64 = 10;
const VIP_ADJUSTMENT: i64 = 300;

pub fn total(order: &Order) -> i64 {
    let mut total: i64 = 0;
    for item in order.items.iter().filter(|item| item.qty > 0) {
        total += apply_discount(
            item.price * i64::from(item.qty),
            category_discount_percent(&item.category),
        );
    }
    if total > ORDER_DISCOUNT_THRESHOLD {
        total -= total / ORDER_DISCOUNT_DIVISOR;
    }
    total += tax_for(total, &order.region);
    if order.vip {
        total -= VIP_ADJUSTMENT;
    }
    total
}

fn category_discount_percent(category: &str) -> i64 {
    match category {
        "book" => BOOK_DISCOUNT_PERCENT,
        "electronics" => ELECTRONICS_DISCOUNT_PERCENT,
        _ => 0,
    }
}

fn apply_discount(amount: i64, percent: i64) -> i64 {
    amount - amount * percent / 100
}

fn tax_for(total: i64, region: &str) -> i64 {
    match region {
        "US" => total * US_TAX_PERCENT / 100,
        "EU" => total * EU_TAX_PERCENT / EU_TAX_DIVISOR,
        _ => 0,
    }
}
```

注意 apply_discount 用 `amount * percent / 100` 复现原来的 `amount - amount / 10`：对整数而言 `10 * s / 100 == s / 10`，截断点没有变化；迭代器 filter 也保持了原按顺序累加的语义。

## 5. 第三步：差分测试再兜一层

<!-- verify:file=tests/differential.rs -->
```rust
use verify_example::legacy::{self, Item, Order};
use verify_example::refactored;

fn item(qty: i32, price: i64, category: &str) -> Item {
    Item {
        qty,
        price,
        category: category.to_string(),
    }
}

fn order(items: Vec<Item>, region: &str, vip: bool) -> Order {
    Order {
        items,
        region: region.to_string(),
        vip,
    }
}

#[test]
fn refactored_matches_legacy() {
    let cases: Vec<Order> = vec![
        order(vec![], "", false),
        order(vec![item(0, 1000, ""), item(-2, 500, "")], "", false),
        order(vec![item(3, 4000, "book")], "EU", false),
        order(vec![item(1, 100, "book")], "", true),
        order(
            vec![item(7, 333, "book"), item(2, 1999, "electronics")],
            "EU",
            true,
        ),
        order(vec![item(1, 10_001, "")], "US", false),
        order(vec![item(5, 2001, "electronics")], "US", true),
    ];
    for (index, case) in cases.iter().enumerate() {
        assert_eq!(
            legacy::total(case),
            refactored::total(case),
            "case {index}"
        );
    }
}
```

## 6. 可执行验证

样例按真实 Rust 工程拆分文件，模块根如下（其余文件见上文）：

<!-- verify:file=src/lib.rs -->
```rust
pub mod legacy;
pub mod refactored;
```

CI 用 `python3 .github/scripts/verify_examples.py --require-all` 把它们写入临时 crate（缺省 `Cargo.toml` 自动生成，包名 `verify_example`）并执行 `cargo test --quiet`；本地可 `--only rust-legacy-order-total` 单独跑。测试失败 CI 即失败。

## 7. 这个流程为什么可靠

- **隐式行为被锁死**：整数截断、满减阈值、qty <= 0 跳过、VIP 可为负，全部由测试固定。
- **重构只动结构**：常量具名、match 分派、职责拆分，计算顺序与截断位置不变。
- **差分测试兜底**：在基线未覆盖的组合上直接比较两个模块的输出。
- **语言差异不等于行为差异**：Rust 的类型系统让「字符串分类」这类问题更容易被发现，但重构边界仍由行为基线测试定义。
