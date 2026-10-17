package orders

type Item struct {
	SKU   string
	Qty   int
	Price int // 单位：分
}

func Total(items []Item) int {
	total := 0
	for _, item := range items {
		if item.Qty <= 0 {
			continue
		}
		total += item.Price * item.Qty
	}
	return total
}
