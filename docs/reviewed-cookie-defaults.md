# Source-reviewed cookie defaults

Bundle `2026.11.26.1` changes exactly these five selectors from Vary to Shared
in **both Basic and UltraCache**. The original cookies still reach the application
on an origin request; their values no longer multiply public HTML cache objects.

| Selector | Purpose and reason for Shared |
| --- | --- |
| `wp-settings-` prefix | The current authenticated user's wp-admin interface preferences. WordPress core updates them in the admin area; anonymous public HTML does not use them as an identity. |
| `wp-settings-time-` prefix | Synchronization timestamp for those admin preferences, rather than a public representation selector. |
| `wp_lang` exact | WordPress core's login-screen language. The normal frontend locale does not read this cookie; the login route retains its existing private handling. |
| `cmplz_saved_categories` exact | Previous category snapshot used by Complianz JavaScript to decide whether to post a consent-record update. Actual category consent checks use the category-specific cookies. |
| `cmplz_saved_services` exact | Equivalent service-update bookkeeping. Actual service checks use `cmplz_consented_services`. |

These are ordinary reviewed catalogue choices, visible and overrideable in the
existing Cookie policies editor. Saved site choices take precedence over central
administrator choices, then bundled defaults. Updates do not silently overwrite
an intentionally saved Vary or Private choice. Custom frontend consumers can
retain or add their appropriate explicit choice.

The reviewed reasons and pinned source links are available through the existing
proposal metadata. The canonical generator consults these catalogue entries
before its generic name/description inference, so regeneration retains the
decisions. The generated standalone artifact and native runtime agree.

## Evidence

- WordPress **7.1.4**, commit `0afb74de8c3fe4c1869e44b62b0418d67b11aa4c`:
  [admin preference synchronization](https://github.com/WordPress/wordpress-develop/blob/0afb74de8c3fe4c1869e44b62b0418d67b11aa4c/src/wp-includes/option.php#L1698-L1742)
  and [current-user settings access](https://github.com/WordPress/wordpress-develop/blob/0afb74de8c3fe4c1869e44b62b0418d67b11aa4c/src/wp-includes/option.php#L1830-L1860).
  [Locale determination](https://github.com/WordPress/wordpress-develop/blob/0afb74de8c3fe4c1869e44b62b0418d67b11aa4c/src/wp-includes/l10n.php#L140-L173)
  reads `wp_lang` for `wp-login.php`, where the
  [cookie is created](https://github.com/WordPress/wordpress-develop/blob/0afb74de8c3fe4c1869e44b62b0418d67b11aa4c/src/wp-login.php#L531-L532).
- Complianz public source **7.5.8**, commit
  `8a54a2c907f2688ad47d06ff2a51b3a361028154`:
  [JavaScript snapshot comparison and consent-record POST](https://github.com/complianz/complianz-gdpr/blob/8a54a2c907f2688ad47d06ff2a51b3a361028154/cookiebanner/js/complianz.js#L2234-L2272),
  [category checks](https://github.com/complianz/complianz-gdpr/blob/8a54a2c907f2688ad47d06ff2a51b3a361028154/functions.php#L2272-L2292)
  and [service checks](https://github.com/complianz/complianz-gdpr/blob/8a54a2c907f2688ad47d06ff2a51b3a361028154/functions.php#L2303-L2321).
  The [provider's integration guide](https://complianz.io/help/wordpress/configuration/developers-guide-for-third-party-integrations/)
  separately identifies saved snapshots as consent-record/A-B update signals.

No blanket `cmplz_` rule is introduced. `cmplz_id` retains its existing Vary
decision while its A/B identity and initial-banner versus Ajax behavior are
qualified separately. Actual consent, authentication, account/cart identity,
private routes and application no-store decisions remain independent.

## Qualification

The focused suite checks the exact five-action delta against the recorded
baseline, canonical generator output, both profiles, raw Cookie forwarding,
Shared HTML reuse and administrator/site override precedence. Native HTTP
checks use the real Hestia VCL renderer with a declared mock origin; they do
not claim complete site-specific HTML or consent acceptance. Projected-Variant
transport fixtures now explicitly configure their three Variant dimensions
rather than relying on the superseded provider defaults.

The recognition CSV is unchanged: all 2,288 records match the pinned input.
No other executable cookie decision is changed. Full assessment regeneration
already had unrelated metadata-only drift; this update preserves that existing
editorial metadata while using generated reviewed rows for the five corrections.
