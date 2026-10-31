<?php
require $root . '/web/templates/header.php';
$panel = top_panel($headerOwner, $TAB);
$profiles = ['general' => 'General', 'wordpress' => 'WordPress', 'woocommerce' => 'WooCommerce', 'ultracache' => 'UltraCache for Hestia'];
?>
<script>document.title = <?= json_encode($meta['title'], JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT) ?>;</script>
<div class="toolbar"><div class="toolbar-inner"><div class="toolbar-buttons"><a class="button button-secondary" href="/list/web/"><i class="fas fa-arrow-left icon-blue"></i>Back</a></div></div></div>
<div class="container"><div class="form-container form-container-wide">
    <h1 class="u-mb10"><?= $escape($meta['title']) ?></h1>
    <p class="u-mb20">All accounts · <?= $escape($data['total_accounts'] ?? 0) ?> accounts · <?= $escape($data['total_sites'] ?? 0) ?> websites</p>
    <?php if ($pageError !== ''): ?><div class="alert alert-danger u-mb20" role="alert"><p><?= $escape($pageError) ?></p></div>
    <?php elseif (isset($data['changed'])): ?><div class="alert alert-success u-mb20" role="status"><p>Applied to <?= $escape($data['changed']['accounts']) ?> accounts and <?= $escape($data['changed']['sites']) ?> websites.</p></div><?php endif; ?>
    <form method="post">
        <?php $formFields('admin-bulk'); ?>
        <h2 class="u-mb20">Bulk changes</h2>
        <div class="u-mb20"><label class="form-label" for="bulk-operation">Change</label><select class="form-select" id="bulk-operation" name="operation">
            <?php if ($meta['slug'] === 'varnish'): ?><option value="set-profile">Set website profile</option><?php endif; ?>
            <option value="enable-sites">Enable websites</option><option value="disable-sites">Disable websites</option>
            <option value="enable-accounts">Enable accounts</option><option value="disable-accounts">Disable accounts</option>
        </select></div>
        <?php if ($meta['slug'] === 'varnish'): ?><div class="u-mb20"><label class="form-label" for="bulk-profile">Varnish profile (for Set website profile)</label><select class="form-select" id="bulk-profile" name="profile"><?php foreach ($profiles as $value => $label): ?><option value="<?= $escape($value) ?>"><?= $escape($label) ?></option><?php endforeach; ?></select></div><?php endif; ?>
        <div class="u-mb20"><label class="form-label" for="bulk-scope">Apply to</label><select class="form-select" id="bulk-scope" name="scope"><option value="selected">Selected accounts / websites below</option><option value="all">All accounts / websites</option></select></div>
        <p class="u-mb20">Select an account to include all its websites. Account enable/disable uses account checkboxes. Website changes retain account enable/disable settings.</p>
        <button type="submit" class="button u-mb20"><i class="fas fa-floppy-disk icon-purple"></i>Apply change</button>
        <?php foreach ($data['accounts'] ?? [] as $account): ?>
            <details class="box-collapse u-mb20" aria-label="<?= $escape($account['owner']) ?>" open>
                <summary class="box-collapse-header"><label><input type="checkbox" name="accounts[]" value="<?= $escape($account['owner']) ?>"> <?= $escape($account['owner']) ?></label> · <?= $account['suspended'] ? 'Suspended' : ($account['enabled'] && $account['allowed'] ? 'Enabled' : 'Disabled') ?> · <a href="?owner=<?= rawurlencode($account['owner']) ?>">Manage account</a></summary>
                <div class="box-collapse-content">
                    <?php foreach ($account['sites'] as $site): ?>
                        <div class="u-mb20">
                            <label><input type="checkbox" name="targets[]" value="<?= $escape(json_encode(['owner' => $account['owner'], 'domain' => $site['domain']], JSON_THROW_ON_ERROR)) ?>"> <strong><?= $escape($site['domain']) ?></strong></label>
                            <p>Status: <?= $site['suspended'] || $account['suspended'] ? 'Suspended' : ($site['active'] ? 'Active' : 'Inactive') ?> · Site setting: <?= $site['enabled'] ? 'Enabled' : 'Disabled' ?><?php if (isset($site['profile'])): ?> · Profile: <?= $escape($profiles[$site['profile']] ?? $site['profile']) ?><?php endif; ?> · <a href="?owner=<?= rawurlencode($account['owner']) ?>&amp;domain=<?= rawurlencode($site['domain']) ?>">Manage website</a></p>
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
