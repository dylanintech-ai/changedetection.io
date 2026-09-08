"""Convert Target category responses into a dated SKU catalog and paused watches.

Target street_date is a retailer release-date proxy, not the expansion release.
No regular retail price is treated as verified manufacturer MSRP.
"""
import argparse
from datetime import date
import html
import json
from pathlib import Path


def cutoff(today):
    try:
        return today.replace(year=today.year - 2)
    except ValueError:
        return today.replace(year=today.year - 2, day=28)


def extract(payload, today):
    search = payload['data']['search']
    rows = []
    for raw in search['products']:
        item = raw.get('item', {})
        sku = str(raw.get('tcin', ''))
        if not sku.isdigit():
            continue
        title = html.unescape(item.get('product_description', {}).get('title', ''))
        release = item.get('mmbv_content', {}).get('street_date')
        try:
            released = date.fromisoformat(release)
            scope = 'recent' if cutoff(today) <= released <= today else 'upcoming' if released > today else 'older'
        except (ValueError, TypeError):
            scope = 'unknown_release_date'
        brand = item.get('primary_brand', {}).get('name', '').lower()
        if brand not in ('pokemon', 'pokémon'):
            scope = 'brand_review'
        rows.append({
            'tcin': sku, 'title': title, 'url': f'https://www.target.com/p/-/A-{sku}',
            'street_date': release, 'release_date_source': 'Target item.mmbv_content.street_date',
            'scope': scope, 'current_price': raw.get('price', {}).get('current_retail'),
            'regular_price': raw.get('price', {}).get('reg_retail'),
            'msrp': None, 'seller_verified': False,
            'watch': {'url': f'https://www.target.com/p/-/A-{sku}', 'title': title,
                      'processor': 'restock_diff', 'paused': True,
                      'processor_config_restock_diff': {'in_stock_processing': 'in_stock_only', 'follow_price_changes': False}}
        })
    return rows, search['search_response']['metadata']['total_results']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pages', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--as-of', type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    all_rows = {}
    totals = []
    for path in args.pages:
        rows, total = extract(json.loads(path.read_text()), args.as_of)
        totals.append(total)
        all_rows.update({row['tcin']: row for row in rows})
    report = {'as_of': str(args.as_of), 'cutoff': str(cutoff(args.as_of)),
              'reported_category_totals': totals, 'unique_imported': len(all_rows),
              'complete': len(set(totals)) == 1 and len(all_rows) == totals[0],
              'products': list(all_rows.values())}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'products'}))


if __name__ == '__main__':
    main()
