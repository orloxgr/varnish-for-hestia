# Varnish for Hestia

One shared Varnish service, separate site caches and purge tokens, with per-site
profiles and VCL controls. Version **0.8.0** · GPL-3.0-or-later.

## Quick start

Requires **Ubuntu 26.04 amd64 with Hestia 1.10.5 already installed**, using
**Nginx -> Apache/PHP-FPM**. Run commands over SSH as an administrator. The
installer also installs Varnish **9.1.0**; do not install the service separately.

1. **Clone.**

   ```sh
   sudo git clone https://github.com/orloxgr/varnish-for-hestia.git /usr/local/src/varnish-for-hestia
   ```

2. **Install with an 8 GiB cache budget.**

   ```sh
   sudo python3 /usr/local/src/varnish-for-hestia/tools/install.py --memory-mb 8192
   ```

3. **Check that Varnish is running.** The output should be `active`.

   ```sh
   sudo systemctl is-active varnish
   ```

4. **Log into Hestia as the site owner. Click Plugins → Varnish in the top bar.**

   Sites start enabled with **General**. Choose **WordPress**, **WooCommerce**
   or **UltraCache for Hestia** per site and save. Administrators see all accounts
   and websites, with bulk profile and enable/disable controls.

Done. Existing users and sites are added during installation; new ones are picked
up automatically within a minute. Each owner can edit the supported VCL sections,
change purge tokens, clear cache, or disable Varnish for a site or their account.
All profiles work with plain PHP or WordPress, independently of installed plugins.

The **8 GiB budget is shared by all sites**, not allocated per user. This example
is sized for a **32 GB server**: Varnish also uses RAM outside cache storage,
and PHP, databases and other services need their own RAM. Hestia's existing code
and templates are not replaced.

While this repository is private, cloning requires your GitHub username and a
token with repository access at the password prompt, not your GitHub password.

## Update

```sh
sudo git -C /usr/local/src/varnish-for-hestia pull --ff-only
sudo python3 /usr/local/src/varnish-for-hestia/tools/install.py
```

Updates retain existing tokens, site settings and memory budget.
Refresh Hestia with **Ctrl+F5** after updating to load the new menu script.

## Change the server timeout in Hestia

1. Open **Plugins → Varnish** as administrator, in **All accounts**.
2. Under **Server settings · all websites**, enter **300** in
   **Backend first-byte timeout (seconds)**.
3. Click **Apply server timeout**.

This is the time Varnish allows Apache to start responding, including requests
that bypass cache. It applies to every domain and origin, survives updates and
is applied live without a Varnish restart or cache flush. Existing installations
keep the native service default until an administrator saves a value. Nginx,
Apache and PHP retain their separate time limits; configure those through Hestia
when a matching overall request limit is needed.

Hover over controls to see their purpose and scope. **Show memory usage** reads
one native `varnishstat` snapshot only when clicked. It shows malloc cache storage
used/free and the configured budget, rather than total process RSS. There is no
background statistics collector, request-log analysis or automatic polling.

For VCL details, backup, restore, removal or importing an existing Varnish,
see the [administration reference](docs/administration.md).
