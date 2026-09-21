# inventory_analysis.py
def find_product_combinations(products, target_price, price_margin=10):
    """
    Find all pairs of products where the combined price is within
    the target_price ± price_margin range.

    Args:
        products: List of dictionaries with 'id', 'name', and 'price' keys
        target_price: The ideal combined price
        price_margin: Acceptable deviation from the target price

    Returns:
        List of dictionaries with product pairs and their combined price
    """
    results = []

    # Work with plain prices instead of repeated dict lookups on every iteration
    prices = [product['price'] for product in products]
    low = target_price - price_margin
    high = target_price + price_margin
    n = len(products)

    # Each unordered pair is visited exactly once (j starts at i+1), which
    # removes the O(len(results)) duplicate scan and halves the work.
    for i in range(n - 1):
        if i % 100 == 0:
            print(f"Processing product {i+1} of {n}")
        product1 = products[i]
        price1 = prices[i]
        min_partner = low - price1
        max_partner = high - price1
        for j in range(i + 1, n):
            price2 = prices[j]
            # Equivalent to (target_price - margin) <= price1 + price2 <= (target_price + margin)
            if min_partner <= price2 <= max_partner:
                combined_price = price1 + price2
                results.append({
                    'product1': product1,
                    'product2': products[j],
                    'combined_price': combined_price,
                    'price_difference': abs(target_price - combined_price)
                })

    # Sort by price difference from target
    results.sort(key=lambda x: x['price_difference'])
    return results

# Example usage
if __name__ == "__main__":
    import time
    import random

    # Generate a large list of products
    print("Generating Product List")
    product_list = []
    for i in range(5000):
        product_list.append({
            'id': i,
            'name': f'Product {i}',
            'price': random.randint(5, 500)
        })

    # Measure execution time
    print(f"Finding product combinations for {len(product_list)} products")
    start_time = time.time()
    combinations = find_product_combinations(product_list, 500, 50)
    end_time = time.time()

    print(f"Found {len(combinations)} product combinations")
    print(f"Execution time: {end_time - start_time:.2f} seconds")