# 实战样例：遗留 C# 代码的行为基线（无测试框架）

演示工作流 2 + 工作流 4：面对一个多年没有测试、又不想只为重构引入测试框架的 C# 项目，可以把「行为基线 + 差分断言」写进一个可执行控制台程序，用**退出码**当验收信号。流程见 references/workflows.md。

本样例与 Go / Rust 样例使用同一套隐藏规则（整数截断、满减阈值、VIP 可为负），便于对照。代码块带 `<!-- verify:file=... -->` 标记，CI 会用 .github/scripts/verify_examples.py 生成临时工程并执行 `dotnet run`。

<!-- verify:run
dotnet run --project Example.csproj
-->

## 1. 遗留代码（无测试、魔数遍地）

<!-- verify:file=Legacy.cs -->
```csharp
namespace Orders
{
    public sealed class Item
    {
        public int Qty;
        public int Price; // 单位：分
        public string Category = "";
    }

    public sealed class Order
    {
        public Item[] Items = new Item[0];
        public string Region = "";
        public bool Vip;
    }

    public static class LegacyPricing
    {
        public static int Total(Order order)
        {
            var total = 0;
            foreach (var item in order.Items)
            {
                if (item.Qty <= 0) continue;
                var subtotal = item.Price * item.Qty;
                if (item.Category == "book") subtotal -= subtotal / 10;
                else if (item.Category == "electronics") subtotal -= subtotal / 20;
                total += subtotal;
            }
            if (total > 10000) total -= total / 50;
            if (order.Region == "US") total += total * 8 / 100;
            else if (order.Region == "EU") total += total * 2 / 10;
            if (order.Vip) total -= 300;
            return total;
        }
    }
}
```

**为什么危险**：字段全用 `public` 可变字段；分类用字符串 `==` 比较（大小写/拼写错误不报错）；魔数散落；整数除法逐处截断（`/10`、`/50`、`*8/100`）；满减是 `> 10000` 而非 `>=`；`Qty <= 0` 静默跳过；VIP 可把总价减成负数。这些「行为约定」编译器管不了。

## 2. 第一步：行为基线（先锁行为，再动结构）

```text
为下面的 C# 类生成「行为基线测试」，目标是捕捉当前真实行为（即使看起来是 bug 也照原样断言），不要修改被测代码。

- 覆盖：空订单、Qty <= 0、book / electronics / 其他分类、总价恰好 10000 与略高于 10000、US / EU / 其他地区、VIP；
- 断言具体到 int 结果（含整数除法截断后的值）；
- 项目里没有测试框架：把断言写成一个可执行控制台程序，失败时返回非零退出码。
{粘贴上面的 Legacy.cs}
```

> 没有测试框架也能先有安全网：一个**返回非零退出码的断言程序**就是最小可用的 characterisation test，既能本地跑，也能直接接进 CI。

## 3. 第二步：重构（套用主模板）

```text
你是资深 C# 工程师，专注在不改变行为的前提下做重构。

【硬约束】
1. 第 2 步的行为基线断言必须原样通过，一条都不许改；
2. 不改变公开类型成员与方法签名，返回值语义保持一致；
3. 整数除法的截断位置与顺序必须保持一致（含满减与税费的计算顺序）；
4. 不引入新依赖、不改变错误处理与日志。

【重构目标】
1. 用具名常量替换魔法数字（折扣、阈值、税率、VIP 调整）；
2. 把分类折扣、满减、税费拆成单一职责的私有方法；
3. 保持 Qty <= 0 静默跳过、VIP 可为负等隐式行为不变。

【验收标准】
测试命令：dotnet run --project Example.csproj（含全部行为基线与差分断言）必须通过，退出码 0。
```

## 4. 参考重构结果（行为等价）

<!-- verify:file=Refactored.cs -->
```csharp
namespace Orders
{
    public static class RefactoredPricing
    {
        private const int BookDiscountPercent = 10;
        private const int ElectronicsDiscountPercent = 5;
        private const int OrderDiscountThreshold = 10000;
        private const int OrderDiscountDivisor = 50;
        private const int UsTaxPercent = 8;
        private const int EuTaxPercent = 2;
        private const int EuTaxDivisor = 10;
        private const int VipAdjustment = 300;

        // 与 LegacyPricing.Total 行为等价；真实重构中它就是新的 Total。
        public static int Total(Order order)
        {
            var total = 0;
            foreach (var item in order.Items)
            {
                if (item.Qty <= 0) continue;
                total += ApplyDiscount(item.Price * item.Qty, CategoryDiscountPercent(item.Category));
            }
            if (total > OrderDiscountThreshold) total -= total / OrderDiscountDivisor;
            total += TaxFor(total, order.Region);
            if (order.Vip) total -= VipAdjustment;
            return total;
        }

        private static int CategoryDiscountPercent(string category)
        {
            switch (category)
            {
                case "book": return BookDiscountPercent;
                case "electronics": return ElectronicsDiscountPercent;
                default: return 0;
            }
        }

        private static int ApplyDiscount(int amount, int percent) => amount - amount * percent / 100;

        private static int TaxFor(int total, string region)
        {
            switch (region)
            {
                case "US": return total * UsTaxPercent / 100;
                case "EU": return total * EuTaxPercent / EuTaxDivisor;
                default: return 0;
            }
        }
    }
}
```

注意 ApplyDiscount 用 `amount * percent / 100` 复现原来的 `amount - amount / 10`：对整数而言截断点没有变化。

## 5. 第三步：基线与差分断言写进可执行程序

<!-- verify:file=Program.cs -->
```csharp
using System;
using Orders;

internal static class Program
{
    private static int Main()
    {
        var failures = 0;
        failures += CheckBaseline();
        failures += CheckEquivalence();
        if (failures > 0)
        {
            Console.WriteLine($"FAILED: {failures} assertion(s)");
            return 1;
        }
        Console.WriteLine("PASS: baseline and differential checks are green");
        return 0;
    }

    private static Order NewOrder(Item[] items, string region = "", bool vip = false) =>
        new Order { Items = items, Region = region, Vip = vip };

    private static Item NewItem(int qty, int price, string category = "") =>
        new Item { Qty = qty, Price = price, Category = category };

    private static int CheckBaseline()
    {
        var cases = new (string Name, Order Order, int Want)[]
        {
            ("empty order", NewOrder(new Item[0]), 0),
            ("non-positive qty ignored", NewOrder(new[] { NewItem(0, 1000), NewItem(-2, 500) }), 0),
            ("book discount truncates", NewOrder(new[] { NewItem(1, 1000, "book") }), 900),
            ("electronics discount truncates", NewOrder(new[] { NewItem(2, 1000, "electronics") }), 1900),
            ("order discount needs strictly above threshold", NewOrder(new[] { NewItem(2, 5000) }), 10000),
            ("us tax integer division", NewOrder(new[] { NewItem(3, 4000, "book") }, "US"), 11430),
            ("eu tax", NewOrder(new[] { NewItem(3, 4000, "book") }, "EU"), 12700),
            ("vip can go below zero", NewOrder(new[] { NewItem(1, 100, "book") }, vip: true), -210),
        };

        var failures = 0;
        foreach (var item in cases)
        {
            var got = LegacyPricing.Total(item.Order);
            if (got != item.Want)
            {
                Console.WriteLine($"baseline {item.Name}: got {got}, want {item.Want}");
                failures += 1;
            }
        }
        return failures;
    }

    private static int CheckEquivalence()
    {
        var random = new Random(7);
        var prices = new[] { 10, 40, 50, 99, 100, 333 };
        var categories = new[] { "book", "electronics", "other" };
        var regions = new[] { "US", "EU", "" };
        var failures = 0;

        for (var index = 0; index < 200; index += 1)
        {
            var items = new Item[random.Next(5)];
            for (var i = 0; i < items.Length; i += 1)
            {
                items[i] = NewItem(
                    random.Next(-2, 6),
                    prices[random.Next(prices.Length)],
                    categories[random.Next(categories.Length)]);
            }
            var order = NewOrder(items, regions[random.Next(regions.Length)], random.Next(3) == 0);
            var legacy = LegacyPricing.Total(order);
            var refactored = RefactoredPricing.Total(order);
            if (legacy != refactored)
            {
                Console.WriteLine($"differential case {index}: legacy={legacy} refactored={refactored}");
                failures += 1;
            }
        }
        return failures;
    }
}
```

`CheckBaseline` 锁住当前行为（含枚举用例），`CheckEquivalence` 用固定种子生成 200 组订单对比遗留版与重构版输出；任何一条不等都会让程序返回退出码 1。

## 6. 可执行验证

CI 用 `python3 .github/scripts/verify_examples.py --require-all` 把三个 .cs 文件写入临时目录，按本机 `dotnet --version` 生成 `Example.csproj`（本地 .NET 10 → `net10.0`，CI .NET 8 → `net8.0`），再执行 `dotnet run --project Example.csproj`；本地可 `--only csharp-legacy-order-total` 单独跑。退出码非零即失败。

## 7. 这个流程为什么可靠

- **无测试框架也有安全网**：断言程序的退出码就是验收信号，比口头断言「行为不变」强得多。
- **隐式行为被锁死**：整数截断、满减阈值、`Qty <= 0` 跳过、VIP 可为负，全部由基线断言固定。
- **差分断言扩覆盖**：枚举用例之外，用固定种子生成用例对比新旧实现。
- **要改行为就单独提**：以后若想「修」整数截断或负数总价，属于行为变更，应另开变更单并同步改断言。
