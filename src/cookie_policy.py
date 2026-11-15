"""Owner cookie exclusions; built-in HTTP policy lives in the shared VCL."""
import re

# Built-in application/analytics policy lives in shared/cache-policy.vcl.
RULE = re.compile(r"[!#$%&'+.^_`|~0-9A-Za-z-]+\*?")


def normalize(value):
    if isinstance(value, str):
        value = value.splitlines()
    if not isinstance(value, list):
        raise ValueError('Use cookie names or trailing-star prefixes')
    result = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError('Cookie rules must be names, one per line')
        item = item.strip()
        if not item:
            continue
        if not RULE.fullmatch(item):
            raise ValueError('Use valid HTTP cookie names; only a trailing * is interpreted as a prefix wildcard')
        if item not in result:
            result.append(item)
    return result


def pattern(rules):
    names = []
    for rule in normalize(list(rules)):
        name = re.escape(rule.removesuffix('*'))
        if rule.endswith('*'):
            name += '[^=;[:blank:]]*'
        names.append(name)
    if not names:
        raise ValueError('An empty cookie rule list has no match pattern')
    return '(^|;[[:blank:]]*)(' + '|'.join(names) + ')='


def vcl_pattern(rules):
    # Native long strings preserve PCRE escapes. Cookie names cannot contain
    # quotes/braces, so they cannot terminate this generated VCL literal.
    return '{"' + pattern(rules) + '"}'
