# 实战样例：策略 C 全景（Java 订单计算器）

演示本技能「三档策略」中 C 档的完整用法：角色 + 上下文（业务规则）+ 硬约束 + 可验证验收标准。原始素材见 references/sources.md 第 1 条。

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
这是一个电商订单价格计算器。calculateTotal 方法负责计算订单总价，规则如下：
- 商品小计 = 单价 × 数量（数量非正时按 0 计）；
- 图书类打 9 折，电子产品打 95 折；
- 订单总价超过 100 时再打 98 折；
- 美国订单加 8% 税，其他地区加 20% 税；
- 最终价格大于 0 时加 5 元运费。

请重构这段代码，要求：
1. 提取子方法，降低嵌套深度；
2. 消除重复逻辑；
3. 保持原有行为不变；
4. 使用有意义的命名；
5. 输出重构后的完整代码，并附一段说明，列出你做了哪些改动。

验收标准：重构后的代码必须通过以下测试用例——
- 空订单返回 0；
- 单本图书 100 元 × 1 本，期望 100 × 0.9 × 0.98 × 1.08 + 5；
- 电子产品 200 元 × 2 件，期望 400 × 0.95 × 0.98 × 1.2 + 5。
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
        if ("BOOK".equals(category)) return price * 0.9;
        if ("ELECTRONICS".equals(category)) return price * 0.95;
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
- `"BOOK".equals(category)` 把「category 为 null 会抛 NPE」改为「视为不打折」——这是一处**有意的行为收紧**，属于主模板【输出格式】第 4 条要求明示的「风险提示/改动说明」。
- 验收标准里的 3 个用例可机械核对行为等价，正是「能跑」与「可靠」的分水岭。
