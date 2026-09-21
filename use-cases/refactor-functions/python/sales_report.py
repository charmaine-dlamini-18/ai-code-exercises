from datetime import datetime


def generate_sales_report(sales_data, report_type='summary', date_range=None,
                         filters=None, grouping=None, include_charts=False,
                         output_format='pdf'):
    """
    Generate a comprehensive sales report based on provided data and parameters.

    Parameters:
    - sales_data: List of sales transactions
    - report_type: 'summary', 'detailed', or 'forecast'
    - date_range: Dict with 'start' and 'end' dates
    - filters: Dict of filters to apply
    - grouping: How to group data ('product', 'category', 'customer', 'region')
    - include_charts: Whether to include charts/visualizations
    - output_format: 'pdf', 'excel', 'html', or 'json'

    Returns:
    - Report data or file path depending on output_format
    """
    _validate_inputs(sales_data, report_type, output_format)

    sales_data = _filter_by_date_range(sales_data, date_range)
    sales_data = _apply_filters(sales_data, filters)

    if not sales_data:
        return _empty_report_result(report_type, output_format)

    metrics = _calculate_metrics(sales_data)
    grouped_data = _group_sales(sales_data, grouping) if grouping else None

    report_data = _build_report_header(report_type, date_range, filters)
    report_data['summary'] = _build_summary(metrics)

    if grouped_data is not None:
        report_data['grouping'] = _build_grouping_section(
            grouping, grouped_data, metrics['total_sales'])

    if report_type == 'detailed':
        report_data['transactions'] = _build_transactions(sales_data)

    if report_type == 'forecast':
        report_data['forecast'] = _build_forecast(sales_data)

    if include_charts:
        report_data['charts'] = _build_charts(sales_data, grouping, grouped_data)

    return _dispatch_output(report_data, output_format, include_charts)


def _validate_inputs(sales_data, report_type, output_format):
    """Validate the public arguments before any processing begins."""
    if not sales_data or not isinstance(sales_data, list):
        raise ValueError("Sales data must be a non-empty list")

    if report_type not in ['summary', 'detailed', 'forecast']:
        raise ValueError("Report type must be 'summary', 'detailed', or 'forecast'")

    if output_format not in ['pdf', 'excel', 'html', 'json']:
        raise ValueError("Output format must be 'pdf', 'excel', 'html', or 'json'")


def _filter_by_date_range(sales_data, date_range):
    """Validate the date range and narrow the data to that window."""
    if not date_range:
        return sales_data

    if 'start' not in date_range or 'end' not in date_range:
        raise ValueError("Date range must include 'start' and 'end' dates")

    start_date = datetime.strptime(date_range['start'], '%Y-%m-%d')
    end_date = datetime.strptime(date_range['end'], '%Y-%m-%d')

    if start_date > end_date:
        raise ValueError("Start date cannot be after end date")

    filtered = []
    for sale in sales_data:
        sale_date = datetime.strptime(sale['date'], '%Y-%m-%d')
        if start_date <= sale_date <= end_date:
            filtered.append(sale)

    return filtered


def _apply_filters(sales_data, filters):
    """Apply the arbitrary key/value filters from the options dict."""
    if not filters:
        return sales_data

    filtered = sales_data
    for key, value in filters.items():
        if isinstance(value, list):
            filtered = [sale for sale in filtered if sale.get(key) in value]
        else:
            filtered = [sale for sale in filtered if sale.get(key) == value]
    return filtered


def _empty_report_result(report_type, output_format):
    """Return the empty-result structure for a given output format."""
    print("Warning: No data matches the specified criteria")
    if output_format == 'json':
        return {"message": "No data matches the specified criteria", "data": []}
    return _generate_empty_report(report_type, output_format)


def _calculate_metrics(sales_data):
    """Compute the summary statistics over the (filtered) sales data."""
    total_sales = sum(sale['amount'] for sale in sales_data)
    return {
        'total_sales': total_sales,
        'transaction_count': len(sales_data),
        'average_sale': total_sales / len(sales_data),
        'max_sale': max(sales_data, key=lambda x: x['amount']),
        'min_sale': min(sales_data, key=lambda x: x['amount']),
    }


def _group_sales(sales_data, grouping):
    """Bucket sales by a field, accumulating count, total and items per group."""
    grouped = {}
    for sale in sales_data:
        key = sale.get(grouping, 'Unknown')
        if key not in grouped:
            grouped[key] = {'count': 0, 'total': 0, 'items': []}

        grouped[key]['count'] += 1
        grouped[key]['total'] += sale['amount']
        grouped[key]['items'].append(sale)

    for key in grouped:
        grouped[key]['average'] = grouped[key]['total'] / grouped[key]['count']

    return grouped


def _build_report_header(report_type, date_range, filters):
    """Assemble the metadata part of the report payload."""
    return {
        'report_type': report_type,
        'date_generated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'date_range': date_range,
        'filters': filters,
    }


def _build_summary(metrics):
    """Shape the summary section from the computed metrics."""
    return {
        'total_sales': metrics['total_sales'],
        'transaction_count': metrics['transaction_count'],
        'average_sale': metrics['average_sale'],
        'max_sale': {
            'amount': metrics['max_sale']['amount'],
            'date': metrics['max_sale']['date'],
            'details': metrics['max_sale']
        },
        'min_sale': {
            'amount': metrics['min_sale']['amount'],
            'date': metrics['min_sale']['date'],
            'details': metrics['min_sale']
        }
    }


def _build_grouping_section(grouping, grouped_data, total_sales):
    """Convert grouped stats into the report's grouping section."""
    groups = {}
    for key, data in grouped_data.items():
        groups[key] = {
            'count': data['count'],
            'total': data['total'],
            'average': data['average'],
            'percentage': (data['total'] / total_sales) * 100
        }

    return {'by': grouping, 'groups': groups}


def _build_transactions(sales_data):
    """Build the transaction list, augmenting rows with calculated fields."""
    transactions = []
    for sale in sales_data:
        transaction = {k: v for k, v in sale.items()}

        if 'tax' in sale and 'amount' in sale:
            transaction['pre_tax'] = sale['amount'] - sale['tax']

        if 'cost' in sale and 'amount' in sale:
            transaction['profit'] = sale['amount'] - sale['cost']
            transaction['margin'] = (transaction['profit'] / sale['amount']) * 100

        transactions.append(transaction)

    return transactions


def _build_forecast(sales_data):
    """Compute monthly sales, growth rates and a rolling three-month forecast."""
    monthly_sales = {}
    for sale in sales_data:
        sale_date = datetime.strptime(sale['date'], '%Y-%m-%d')
        month_key = f"{sale_date.year}-{sale_date.month:02d}"
        monthly_sales[month_key] = monthly_sales.get(month_key, 0) + sale['amount']

    sorted_months = sorted(monthly_sales.keys())
    growth_rates = []
    for i in range(1, len(sorted_months)):
        prev_amount = monthly_sales[sorted_months[i - 1]]
        curr_amount = monthly_sales[sorted_months[i]]
        if prev_amount > 0:
            growth_rate = ((curr_amount - prev_amount) / prev_amount) * 100
            growth_rates.append(growth_rate)

    avg_growth_rate = sum(growth_rates) / len(growth_rates) if growth_rates else 0

    forecast = {}
    if sorted_months:
        last_month = sorted_months[-1]
        last_amount = monthly_sales[last_month]

        year, month = map(int, last_month.split('-'))

        for i in range(1, 4):
            month += 1
            if month > 12:
                month = 1
                year += 1

            forecast_month = f"{year}-{month:02d}"
            forecast_amount = last_amount * (1 + (avg_growth_rate / 100))

            forecast[forecast_month] = forecast_amount
            last_amount = forecast_amount

    return {
        'monthly_sales': monthly_sales,
        'growth_rates': {
            sorted_months[i]: growth_rates[i - 1] for i in range(1, len(sorted_months))
        },
        'average_growth_rate': avg_growth_rate,
        'projected_sales': forecast
    }


def _build_charts(sales_data, grouping, grouped_data):
    """Build the chart payload (sales over time, and a pie chart if grouped)."""
    charts_data = {}

    time_chart = {'labels': [], 'data': []}
    date_sales = {}
    for sale in sales_data:
        date_sales[sale['date']] = date_sales.get(sale['date'], 0) + sale['amount']

    for date in sorted(date_sales.keys()):
        time_chart['labels'].append(date)
        time_chart['data'].append(date_sales[date])

    charts_data['sales_over_time'] = time_chart

    if grouping:
        pie_chart = {'labels': [], 'data': []}
        for key, data in grouped_data.items():
            pie_chart['labels'].append(key)
            pie_chart['data'].append(data['total'])

        charts_data['sales_by_' + grouping] = pie_chart

    return charts_data


def _dispatch_output(report_data, output_format, include_charts):
    """Render the report payload in the requested output format."""
    if output_format == 'json':
        return report_data
    if output_format == 'html':
        return _generate_html_report(report_data, include_charts)
    if output_format == 'excel':
        return _generate_excel_report(report_data, include_charts)
    return _generate_pdf_report(report_data, include_charts)


# Helper functions (not implemented here)
def _generate_empty_report(report_type, output_format):
    # Generate an empty report file
    pass


def _generate_html_report(report_data, include_charts):
    # Generate HTML report
    pass


def _generate_excel_report(report_data, include_charts):
    # Generate Excel report
    pass


def _generate_pdf_report(report_data, include_charts):
    # Generate PDF report
    pass