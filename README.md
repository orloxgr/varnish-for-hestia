# Varnish for Hestia

One shared Varnish service, separate site caches and purge tokens, with per-site
profiles and VCL controls. Version **0.5.0** · GPL-3.0-or-later.

## Quick start

Requires **Ubuntu 26.04 amd64 with Hestia 1.10.5 already installed**, using
**Nginx → Apache/PHP-FPM**. Run commands over SSH as an administrator. The
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

4. **Log into Hestia as the site owner and open:**

   ```text
   https://YOUR-SERVER:8083/plugins/varnish/
   ```

   Click **Open Varnish for Hestia**. Sites start enabled with **General**;
   choose **WordPress**, **WooCommerce** or **UltraCache for Hestia** per site
   and save. An administrator can use Hestia's **Log in as** action to open the
   owner's account.

Done. Existing users and sites are added during installation; new ones are picked
up automatically within a minute. Each owner can edit the supported VCL sections,
change purge tokens, clear cache, or disable Varnish for a site or their account.
Profiles work independently of installed applications.

The **8 GiB budget is shared by all sites**, not allocated per user. This example
is sized for a **32 GiB server**: Varnish also uses RAM outside cache storage,
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

For VCL details, backup, restore, removal or importing an existing Varnish,
see the [administration reference](docs/administration.md).
