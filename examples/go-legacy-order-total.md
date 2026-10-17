# 实战样例：遗留 Go 代码的行为基线（无测试）

演示工作流 2 + 工作流 4：先用行为基线测试锁住当前行为（含整数截断这类隐式规则），再做结构化重构，最后用差分测试证明等价。流程见 references/workflows.md。

## 1. 遗留代码（无测试、魔数遍地）

```go
package orders

type Item struct {
	SKU      string
	Qty      int
	Price    int // 单位：分
	Category string
}

type Order struct {
	Items  []Item
	Region string
	VIP    bool
}

func Total(o *Order) int {
	total := 0
	for _, it := range o.Items {
		if it.Qty <= 0 {
			continue
		}
		s := it.Price * it.Qty
		if it.Category == "book" {
			s -= s / 10
		} else if it.Category == "electronics" {
			s -= s / 20
		}
		total += s
	}
	if total > 10000 {
		total -= total / 50
	}
	if o.Region == "US" {
		total += total * 8 / 100
	} else if o.Region == "EU" {
		total += total * 2 / 10
	}
	if o.VIP {
		total -= 300
	}
	return total
}
```

**为什么危险**：全程整数除法，每一步都会**截断**（`s/10`、`total/50`、`*8/100`），取整规则完全隐式；满减是 `> 10000` 而非 `>=`，恰好 10000 不触发；`Qty <= 0` 被静默跳过而非报错；VIP 减 300 可以把总价减成**负数**；魔数与 if/else 链散落，改一处极易连带改变行为。

## 2. 第一步：行为基线测试（先跑通，不改代码）

```text
为下面的 Go 函数生成「行为基线测试」，目标是捕捉当前真实行为（即使看起来是 bug 也照原样断言），不要修改被测代码。

- 覆盖：空订单、Qty <= 0、book / electronics / 其他分类、总价恰好 10000 与略高于 10000、US / EU / 其他地区、VIP；
- 断言具体到整数结果（含整数除法截断后的值）；
- 测试必须在当前代码上直接通过。
{粘贴上面的 orders.go}
```

生成的基线测试（`go test` 通过）：

```go
package orders

import "testing"

func TestTotalBaseline(t *testing.T) {
	cases := []struct {
		name  string
		order *Order
		want  int
	}{
		{"empty order", &Order{}, 0},
		{"non-positive qty ignored", &Order{Items: []Item{{Qty: 0, Price: 1000}, {Qty: -2, Price: 500}}}, 0},
		{"book discount truncates", &Order{Items: []Item{{Qty: 1, Price: 1000, Category: "book"}}}, 900},
		{"electronics discount truncates", &Order{Items: []Item{{Qty: 2, Price: 1000, Category: "electronics"}}}, 1900},
		{"order discount needs strictly above threshold", &Order{Items: []Item{{Qty: 2, Price: 5000}}}, 10000},
		{"us tax integer division", &Order{Items: []Item{{Qty: 3, Price: 4000, Category: "book"}}, Region: "US"}, 11430},
		{"eu tax", &Order{Items: []Item{{Qty: 3, Price: 4000, Category: "book"}}, Region: "EU"}, 12700},
		{"vip can go below zero", &Order{Items: []Item{{Qty: 1, Price: 100, Category: "book"}}, VIP: true}, -210},
	}
	for _, c := range cases {
		if got := Total(c.order); got != c.want {
			t.Errorf("%s: Total() = %d, want %d", c.name, got, c.want)
		}
	}
}
```

> 「eu tax」这一条手算很容易得到 12960：忘了 10800 已经触发满减（`10800/50 = 216`），EU 税必须落在 10584 上。**期望值要跑出来，不能算出来**——这才是「行为基线」而非「理想行为」。

## 3. 第二步：重构（套用主模板）

```text
你是资深 Go 工程师，专注在不改变行为的前提下做重构。

【硬约束】
1. 第 2 步的行为基线测试必须原样通过，一条都不许改；
2. 不改变函数签名 Total(o *Order) int 与返回值语义；
3. 整数除法的截断位置与顺序必须保持一致（含满减与税费的计算顺序）；
4. 不引入新依赖、不改变错误处理与日志。

【重构目标】
1. 用具名常量替换魔法数字（折扣、阈值、税率、VIP 调整）；
2. 把分类折扣、满减、税费拆成单一职责的小函数；
3. 保持 Qty <= 0 静默跳过、VIP 可为负等隐式行为不变。

【验收标准】
测试命令：go test ./...（含全部行为基线测试）必须通过。
```

## 4. 参考重构结果（行为等价）

```go
package orders

const (
	bookDiscountPercent        = 10
	electronicsDiscountPercent = 5
	orderDiscountThreshold     = 10000
	orderDiscountDivisor       = 50
	usTaxPercent               = 8
	euTaxPercent               = 2
	euTaxDivisor               = 10
	vipAdjustment              = 300
)

func Total(o *Order) int {
	total := 0
	for _, it := range o.Items {
		if it.Qty <= 0 {
			continue
		}
		total += applyDiscount(it.Price*it.Qty, categoryDiscountPercent(it.Category))
	}
	if total > orderDiscountThreshold {
		total -= total / orderDiscountDivisor
	}
	total += taxFor(total, o.Region)
	if o.VIP {
		total -= vipAdjustment
	}
	return total
}

func categoryDiscountPercent(category string) int {
	switch category {
	case "book":
		return bookDiscountPercent
	case "electronics":
		return electronicsDiscountPercent
	default:
		return 0
	}
}

func applyDiscount(amount, percent int) int {
	return amount - amount*percent/100
}

func taxFor(total int, region string) int {
	switch region {
	case "US":
		return total * usTaxPercent / 100
	case "EU":
		return total * euTaxPercent / euTaxDivisor
	default:
		return 0
	}
}
```

注意 `applyDiscount` 用 `amount*percent/100` 复现原来的 `amount - amount/10`：对整数而言 `10*s/100 == s/10`，截断点没有变化。

## 5. 第三步：差分测试再兜一层

行内单测只覆盖了枚举用例，重构后补一个差分测试，在更多组合上对比新旧实现：

```go
func TestRefactoredMatchesLegacy(t *testing.T) {
	orders := []*Order{
		{},
		{Items: []Item{{Qty: 0, Price: 1000}, {Qty: -2, Price: 500}}},
		{Items: []Item{{Qty: 3, Price: 4000, Category: "book"}}, Region: "EU"},
		{Items: []Item{{Qty: 1, Price: 100, Category: "book"}}, VIP: true},
		{Items: []Item{{Qty: 7, Price: 333, Category: "book"}, {Qty: 2, Price: 1999, Category: "electronics"}}, Region: "EU", VIP: true},
		{Items: []Item{{Qty: 1, Price: 10001}}, Region: "US"},
		{Items: []Item{{Qty: 5, Price: 2001, Category: "electronics"}}, Region: "US", VIP: true},
	}
	for i, o := range orders {
		if legacy, refactored := Total(o), TotalRefactored(o); legacy != refactored {
			t.Errorf("case %d: legacy=%d refactored=%d", i, legacy, refactored)
		}
	}
}
```

`go test ./...` 全绿：基线测试锁行为，差分测试扩大覆盖。

## 6. 这个流程为什么可靠

- **隐式行为被锁死**：整数截断、`>` 而非 `>=`、Qty <= 0 跳过、VIP 可为负，全部由测试固定。
- **重构只动结构**：常量具名、职责拆分，计算顺序与截断位置不变。
- **差分测试兜底**：在基线未覆盖的组合上直接比较新旧实现输出。
- **要改行为就单独提**：以后若确实想「修」整数截断或负数总价，属于行为变更，应另开变更单并同步改测试，而不是在重构里顺手改掉。
