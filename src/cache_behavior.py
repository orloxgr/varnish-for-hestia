"""Per-site public cache options; independent of profiles and browser cache."""
import aggressive
import cms_routes
import cms_discovery


class CachePolicyError(ValueError):
    pass


def change(site, payload):
    try:
        values = aggressive.settings(payload)
        text = payload.get('custom_private_paths', '')
        if not isinstance(text, str):
            raise ValueError('Custom private paths must be text, one absolute URL path per line')
        paths = cms_routes.literal_prefixes([line.strip() for line in text.splitlines() if line.strip()])
        excluded = payload.get('cms_excluded_directories')
        if excluded is None:
            excluded = site.get('cms_excluded_directories', [])
        else:
            if not isinstance(excluded, str):
                raise ValueError('Excluded CMS directories must be text, one directory per line')
            excluded = [line.strip() for line in excluded.splitlines() if line.strip()]
        excluded = cms_discovery.exclusions(excluded)
    except ValueError as error:
        # These are our fixed validation messages, never database/VCL errors.
        raise CachePolicyError(str(error)) from None
    site.update(values, custom_private_paths=paths, cms_excluded_directories=excluded)


def execution(site):
    """Only effective policy changes invalidate a site, never scan timestamps."""
    values = aggressive.settings(site)
    return (values['aggressive'], values['aggressive_ttl'] if values['aggressive'] else None,
            site.get('cookie_rules_revision',0) if values['aggressive'] else None,
            site.get('cms_document_root'),site.get('cms_pending_root'),
            cms_routes.literal_prefixes(site.get('custom_private_paths', [])),
            cms_routes.normalize(site.get('cms_installations')))
