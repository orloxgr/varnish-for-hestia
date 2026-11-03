<?php
require $root . '/web/templates/header.php';
$panel = top_panel($headerOwner, $TAB);
$profiles = ['general' => 'General', 'wordpress' => 'WordPress', 'woocommerce' => 'WooCommerce', 'ultracache' => 'UltraCache for Hestia'];
?>
<script>document.title = <?= json_encode($meta['title'], JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT) ?>;</script>
<div class="toolbar"><div class="toolbar-inner"><div class="toolbar-buttons"><a class="button button-secondary" href="/list/web/" title="Return to the Hestia website list."><i class="fas fa-arrow-left icon-blue"></i>Back</a></div></div></div>
<div class="container"><div class="form-container form-container-wide">
    <h1 class="u-mb10"><?= $escape($meta['title']) ?></h1>
    <p class="u-mb20">All accounts · <?= $escape($data['total_accounts'] ?? 0) ?> accounts · <?= $escape($data['total_sites'] ?? 0) ?> websites</p>
    <?php if ($pageError !== ''): ?><div class="alert alert-danger u-mb20" role="alert"><p><?= $escape($pageError) ?></p></div>
    <?php elseif (!empty($data['memory_size_saved'])): ?><div class="alert alert-success u-mb20" role="status"><p>Cache size: <?= $escape($data['memory_budget_mb']) ?> MiB. <?= !empty($data['service_restarted']) ? 'Varnish was restarted; the cache will refill as websites are visited.' : 'The size was unchanged; no restart was needed.' ?></p></div>
    <?php elseif (!empty($data['server_settings_saved'])): ?><div class="alert alert-success u-mb20" role="status"><p>The server timeout was applied to all websites.</p></div>
    <?php elseif (isset($data['changed'])): ?><div class="alert alert-success u-mb20" role="status"><p>Applied to <?= $escape($data['changed']['accounts']) ?> accounts and <?= $escape($data['changed']['sites']) ?> websites.</p></div><?php endif; ?>
    <section class="u-mb20">
        <h2 class="u-mb20">Server settings · all websites</h2>
        <form method="post" class="u-mb20">
            <?php $formFields('admin-server-settings'); $timeout = $data['server_settings']['first_byte_timeout_seconds'] ?? $data['service_first_byte_timeout_seconds'] ?? ''; ?>
            <label class="form-label u-block u-mb10" for="first-byte-timeout">Backend first-byte timeout (seconds) <span title="How long Varnish waits for Apache to start responding. Applies to every domain, including cache-bypass requests. It does not change Nginx, Apache or PHP time limits." aria-label="Help: backend first-byte timeout">ⓘ</span></label>
            <input class="form-control u-mb10" id="first-byte-timeout" type="number" name="first_byte_timeout_seconds" min="0" step="any" value="<?= $escape($timeout) ?>" placeholder="300" title="Maximum wait for the first response byte from Apache, in seconds. Use 300 for a five-minute limit. Fractional seconds are accepted; zero selects native immediate timeout. Applies to all accounts and domains." required>
            <?php if (!isset($data['server_settings']['first_byte_timeout_seconds'])): ?><p class="u-mb10">Currently using the Varnish service default<?= $timeout !== '' ? ': ' . $escape($timeout) . ' seconds' : '' ?>.</p><?php endif; ?>
            <button class="button" type="submit" title="Save the timeout for all websites and apply it without restarting Varnish or clearing the cache.">Apply server timeout</button>
        </form>
        <form method="post" class="u-mb20">
            <?php $formFields('admin-memory-size'); ?>
            <label class="form-label u-block u-mb10" for="cache-size">Varnish cache size (MiB) <span title="One shared cache budget for all accounts and websites. 1024 MiB = 1 GiB. Varnish also uses RAM outside this cache budget." aria-label="Help: shared cache size">ⓘ</span></label>
            <input class="form-control u-mb10" id="cache-size" type="number" name="memory_mb" min="1" step="1" value="<?= $escape($data['memory_budget_mb'] ?? '') ?>" title="Total cache storage for the whole server, not per account. For example, 8192 MiB is 8 GiB. The saved size is retained during addon updates." required>
            <p class="u-mb10">Changing the size restarts Varnish for all websites and clears its cached content.</p>
            <button class="button" type="submit" title="Save the shared cache size and restart the native Varnish service. Cached content is cleared. An unchanged size does not trigger a restart.">Apply size and restart Varnish</button>
        </form>
        <form method="post" class="u-mb20"><?php $formFields('admin-memory'); ?><button class="button button-secondary" type="submit" title="Read one memory snapshot from varnishstat. Runs only when clicked; no background collection or automatic refresh.">Show memory usage</button></form>
        <?php if (isset($data['memory'])):
            $mib = static fn($bytes) => number_format((float)$bytes / 1048576, 1); ?>
            <p class="u-mb10" title="Native malloc cache storage counters. These values describe cache storage, rather than the total RAM used by the Varnish process.">Cache used: <strong><?= $escape($mib($data['memory']['used_bytes'])) ?> MiB</strong> · Free cache space: <strong><?= $escape($mib($data['memory']['free_bytes'])) ?> MiB</strong> · Budget: <strong><?= $escape($data['memory']['budget_mb']) ?> MiB</strong></p>
        <?php endif; ?>
    </section>
    <form method="post">
        <?php $formFields('admin-bulk'); ?>
        <h2 class="u-mb20">Bulk changes</h2>
        <div class="u-mb20"><label class="form-label" for="bulk-operation">Change</label><select class="form-select" id="bulk-operation" name="operation" title="Choose whether to change site profiles, enable or disable websites, or enable or disable whole accounts.">
            <?php if ($meta['slug'] === 'varnish'): ?><option value="set-profile">Set website profile</option><?php endif; ?>
            <option value="enable-sites">Enable websites</option><option value="disable-sites">Disable websites</option>
            <option value="enable-accounts">Enable accounts</option><option value="disable-accounts">Disable accounts</option>
        </select></div>
        <?php if ($meta['slug'] === 'varnish'): ?><div class="u-mb20"><label class="form-label" for="bulk-profile">Varnish profile (for Set website profile)</label><select class="form-select" id="bulk-profile" name="profile" title="The caching policy to assign when the operation is Set website profile. Profiles do not require the corresponding WordPress plugin to be installed."><?php foreach ($profiles as $value => $label): ?><option value="<?= $escape($value) ?>"><?= $escape($label) ?></option><?php endforeach; ?></select></div><?php endif; ?>
        <div class="u-mb20"><label class="form-label" for="bulk-scope">Apply to</label><select class="form-select" id="bulk-scope" name="scope" title="Selected changes only checked accounts or websites. All applies the chosen operation across the whole server."><option value="selected">Selected accounts / websites below</option><option value="all">All accounts / websites</option></select></div>
        <p class="u-mb20">Select an account to include all its websites. Account enable/disable uses account checkboxes. Website changes retain account enable/disable settings.</p>
        <button type="submit" class="button u-mb20" title="Apply the selected bulk operation to the chosen scope. Selecting an account includes all of its websites."><i class="fas fa-floppy-disk icon-purple"></i>Apply change</button>
        <?php foreach ($data['accounts'] ?? [] as $account): ?>
            <details class="box-collapse u-mb20" aria-label="<?= $escape($account['owner']) ?>" open>
                <summary class="box-collapse-header" title="Expand or collapse the websites in this account."><label><input type="checkbox" title="Select this account and all its websites for the chosen bulk operation." name="accounts[]" value="<?= $escape($account['owner']) ?>"> <?= $escape($account['owner']) ?></label> · <?= $account['suspended'] ? 'Suspended' : ($account['enabled'] && $account['allowed'] ? 'Enabled' : 'Disabled') ?> · <a title="Open the cache controls for this account or website." href="?owner=<?= rawurlencode($account['owner']) ?>">Manage account</a></summary>
                <div class="box-collapse-content">
                    <?php foreach ($account['sites'] as $site): ?>
                        <div class="u-mb20">
                            <label><input type="checkbox" title="Select only this website for the chosen bulk website operation." name="targets[]" value="<?= $escape(json_encode(['owner' => $account['owner'], 'domain' => $site['domain']], JSON_THROW_ON_ERROR)) ?>"> <strong><?= $escape($site['domain']) ?></strong></label>
                            <p>Status: <?= $site['suspended'] || $account['suspended'] ? 'Suspended' : ($site['active'] ? 'Active' : 'Inactive') ?> · Site setting: <?= $site['enabled'] ? 'Enabled' : 'Disabled' ?><?php if (isset($site['profile'])): ?> · Profile: <?= $escape($profiles[$site['profile']] ?? $site['profile']) ?><?php endif; ?> · <a title="Open the cache controls for this account or website." href="?owner=<?= rawurlencode($account['owner']) ?>&amp;domain=<?= rawurlencode($site['domain']) ?>">Manage website</a></p>
                            <?php if ($site['aliases']): ?><p>Aliases: <?= $escape(implode(', ', $site['aliases'])) ?></p><?php endif; ?>
                        </div>
                    <?php endforeach; ?>
                    <?php if (!$account['sites']): ?><p>No websites.</p><?php endif; ?>
                </div>
            </details>
        <?php endforeach; ?>
    </form>
    <p class="u-mt20"><small>Version <?= $escape($meta['version']) ?></small></p>
</div></div>
<?php require $root . '/web/templates/footer.php'; ?>
