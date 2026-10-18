# 实战样例：策略 C 全景（Java 订单计算器）

演示本技能「三档策略」中 C 档的完整用法，套用本技能的八段骨架：角色 + 上下文（业务规则）+ 待重构代码 + 硬约束 + 重构目标 + 可验证验收标准 + 输出格式 + 守卫。原始素材见 references/sources.md 第 1 条。

## 1. 重构前代码（坏味道明显）

```java
public class OrderCalculator {
    public double calculateTotal(Order order) {
        double total = 0;
        if (order != null) {
            if (order.getItems() != null) {
                for (Item item : order.getItems()) {
                    if (item != null) {
                        double price = item.getPrice();
                        if (item.getQuantity() > 0) {
                            price = price * item.getQuantity();
                        } else {
                            price = 0;
                        }
                        if (item.getCategory().equals("BOOK")) {
                            price = price * 0.9;
                        } else if (item.getCategory().equals("ELECTRONICS")) {
                            price = price * 0.95;
                        }
                        total = total + price;
                    }
                }
            }
        }
        if (total > 100) { total = total * 0.98; }
        if (order != null && order.getCountry() != null) {
            if (order.getCountry().equals("US")) {
                total = total * 1.08;
            } else {
                total = total * 1.2;
            }
        }
        if (total > 0) { total = total + 5; }
        return total;
    }
}
```

问题：嵌套 5 层、魔法数字、分类折扣散落、税费与运费耦合、`item.getCategory()` 可能 NPE。

## 2. 用策略 C 生成的提示词（本技能的输出）

```text
你是资深 Java 专家，专注在不改变行为的前提下做重构。

【前置判断】
- 未提供代码：直接输出 NO_CODE_PROVIDED 并索取代码；
- 代码无明显可改进处：输出 NO_REFACTORING_NEEDED，说明理由，不要硬改。

【上下文】
- 项目/模块：电商订单价格计算器
- 语言与框架：Java 11+
- 这段代码做什么、已知痛点：calculateTotal 计算订单总价，业务规则——
  - 商品小计 = 单价 × 数量（数量非正时按 0 计）；
  - 图书类打 9 折，电子产品打 95 折；
  - 订单总价超过 100 时再打 98 折；
  - 美国订单加 8% 税，其他地区加 20% 税；
  - 最终价格大于 0 时加 5 元运费。

【待重构代码】
{同第 1 节的 OrderCalculator.calculateTotal 方法}

【硬约束（不可违反）】
1. 外部行为 100% 一致：不改公开 API、返回值、抛出的异常类型；
2. 不新增第三方依赖、不弱化错误处理；
3. 遵循现有 Java 编码规范与命名风格。

【重构目标】
0. 先为现有行为生成「行为基线测试」，把下方 4 条用例锚成可运行断言；
1. 提取子方法，降低嵌套深度（5 层 → 1 层）；
2. 消除重复逻辑，分类折扣 / 税费 / 运费各司其职；
3. 用具名常量替换魔法数字。

【验收标准（可运行命令；重构后含行为基线测试全部通过）】
- 测试命令：mvn test（或 JUnit 单独跑 calculateTotal）
- 用例：
  - 空订单 → 0；
  - 单本图书 100 × 1 → 100 × 0.9 × 1.08 + 5 = 102.2（折后 90，不触发 > 100 的满减）；
  - 电子产品 200 × 2 → 400 × 0.95 × 0.98 × 1.2 + 5 = 451.88；
  - 商品分类为 null → 与原实现一致（抛 NullPointerException）；若业务希望改为不打折，属行为变更，另开变更单。

【输出格式】
1. 问题清单：问题 → 严重度 → 位置；
2. 重构后的完整代码，并用 diff 标出关键改动（声明基线文件）；
3. 表格：每处改动 → 改了什么 → 为什么 → 影响面；
4. 风险提示：哪些改动有兼容性风险。
```

## 3. 参考重构结果（行为等价 + 单一职责）

```java
public class OrderCalculator {
    public double calculateTotal(Order order) {
        if (order == null || order.getItems() == null) {
            return 0;
        }
        double subtotal = calculateSubtotal(order.getItems());
        subtotal = applyOrderDiscount(subtotal);
        subtotal = applyTax(subtotal, order.getCountry());
        return applyShipping(subtotal);
    }

    private double calculateSubtotal(List<Item> items) {
        double total = 0;
        for (Item item : items) {
            if (item == null) continue;
            double price = item.getPrice() * Math.max(item.getQuantity(), 0);
            total += applyCategoryDiscount(price, item.getCategory());
        }
        return total;
    }

    private double applyCategoryDiscount(double price, String category) {
        // category.equals(...) 有意保留原实现在 category 为 null 时抛 NPE 的行为
        if (category.equals("BOOK")) return price * 0.9;
        if (category.equals("ELECTRONICS")) return price * 0.95;
        return price;
    }

    private double applyOrderDiscount(double subtotal) {
        return subtotal > 100 ? subtotal * 0.98 : subtotal;
    }

    private double applyTax(double subtotal, String country) {
        if (country == null) return subtotal;
        return "US".equals(country) ? subtotal * 1.08 : subtotal * 1.2;
    }

    private double applyShipping(double total) {
        return total > 0 ? total + 5 : total;
    }
}
```

## 4. 为什么这一版可靠

- 每个方法职责单一、可独立测试；嵌套从 5 层降到 1 层。
- 计算顺序（小计 → 满减 → 税 → 运费）被显式化，语义一目了然。
- `category.equals("BOOK")` 保留原实现在 category 为 null 时抛 NPE 的行为：行为等价包括异常行为，不能借重构顺手「修 bug」；确需改为不打折时，应单开行为变更单并补对应用例。
- 验收标准里的 4 个用例（含异常行为）可机械核对行为等价，正是「能跑」与「可靠」的分水岭。
