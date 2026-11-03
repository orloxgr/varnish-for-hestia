"""Application cookie exclusions; additional owner rules can only add bypasses."""
import re

# WordPress private state, PHP sessions and common personalized Woo extensions.
# Cart cookies are separate because UltraCache may explicitly approve an ESI parent.
PRIVATE = ('wordpress_logged_in_*', 'wordpress_sec_*', 'wp-postpass_*', 'comment_author_*',
           'PHPSESSID', 'woocommerce_recently_viewed', 'yith_wcwl_session_*', 'yith_woocompare_*')
CART = ('woocommerce_items_in_cart', 'woocommerce_cart_hash', 'wp_woocommerce_session_*')
MAX_RULES = 64
MAX_BYTES = 8192
RULE = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}\*?')


def normalize(value):
    if isinstance(value, str):
        if len(value.encode()) > MAX_BYTES:
            raise ValueError('Cookie rules may contain at most 8 KiB')
        value = value.splitlines()
    if not isinstance(value, list):
        raise ValueError('Use at most 64 cookie names or trailing-star prefixes')
    result = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError('Cookie rules must be names, one per line')
        item = item.strip()
        if not item:
            continue
        if not RULE.fullmatch(item):
            raise ValueError('Use cookie names with letters, digits, underscore, dot or hyphen; only a trailing * is allowed')
        if item not in result:
            result.append(item)
    if len(result) > MAX_RULES:
        raise ValueError('Use at most 64 cookie names or trailing-star prefixes')
    if len('\n'.join(result).encode()) > MAX_BYTES:
        raise ValueError('Cookie rules may contain at most 8 KiB')
    return result


def pattern(rules):
    names = []
    for rule in normalize(list(rules)):
        name = rule.rstrip('*').replace('.', '[.]').replace('-', '[-]')
        if rule.endswith('*'):
            name += '[^=;[:blank:]]*'
        names.append(name)
    if not names:
        raise ValueError('An empty cookie rule list has no match pattern')
    return '(^|;[[:blank:]]*)(' + '|'.join(names) + ')='
