# Changelog

## 0.6.1

- Keep the original Accept header in the UltraCache profile for ordinary PHP APIs and content negotiation.
- Bypass standard cart, checkout and account paths in UltraCache without relying on an application plugin.
- Verify all profiles against plain HTTP origins, sessions, private responses and optional ESI.

## 0.6.0

- Add an administrator dashboard listing all native accounts and websites.
- Add bulk account/site enable and disable, plus direct owner management.
- Apply a profile to selected or all websites while retaining site VCL and tokens.

## 0.5.4

- Render addon pages with Hestia’s native header, navigation, selected theme, forms and alerts.
- Keep owner actions in HTML and show visible success or failure feedback.
- Remove the legacy website-access probe from the owner interface.

## 0.5.3

- Add a Plugins menu in Hestia’s top bar through its native custom-scripts loader.
- Share one dropdown with other installed addons, without editing Hestia templates.
- Install, update, roll back and remove only this addon’s menu script.

## 0.5.2

- Create the shared Hestia plugins directory when installing the first addon.
- Preserve existing plugin-directory permissions and neighboring plugins on installation and retry.

## 0.5.1

- Administrator installation failures show command arguments, exit status, subprocess output and Python tracebacks.
- Panel PHP syntax-check failures retain native compiler diagnostics.

## 0.5.0

Initial release.

- Shared native Varnish service with isolated host, backend and purge scopes.
- General, WordPress, WooCommerce and UltraCache profiles, including ESI.
- Bounded site-local VCL editing with native compiler validation.
- Owner token, scoped purge and enable/disable controls.
- Additional Hestia proxy templates and native origin fallback.
- Automatic account/domain lifecycle discovery and package policy.
- Private configuration archives, cold restore and independent removal.
- Durable installation, live-configuration and restore recovery.
- Atomic installed-code generations and failed-upgrade rollback.
- Application configuration remains independently managed.
