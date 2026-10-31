<?php
require $root . '/web/templates/header.php';
$panel = top_panel($headerOwner, $TAB);
?>
<script>document.title = <?= json_encode($meta['title'], JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT) ?>;</script>
<div class="toolbar"><div class="toolbar-inner"><div class="toolbar-buttons">
    <?php if ($isAdmin): ?><a class="button button-secondary" href="./">All accounts</a><?php endif; ?>
    <a class="button button-secondary" href="/list/web/"><i class="fas fa-arrow-left icon-blue"></i>Back</a>
</div></div></div>
<div class="container"><div class="form-container form-container-wide">
    <h1 class="u-mb10"><?= $escape($meta['title']) ?></h1>
    <p class="u-mb20">Account: <strong><?= $escape($owner) ?></strong></p>
    <?php if ($pageError !== ''): ?>
        <div class="alert alert-danger u-mb20" role="alert"><i class="fas fa-circle-exclamation"></i><p><?= $escape($pageError) ?></p></div>
    <?php elseif ($message !== ''): ?>
        <div class="alert alert-<?= $escape($messageType) ?> u-mb20" role="status"><i class="fas fa-circle-check"></i><p><?= $escape($message) ?></p></div>
    <?php endif; ?>
    <?php if ($managed): ?>
        <p class="u-mb20"><i class="fas fa-memory <?= !empty($data['enabled']) && !empty($data['allowed']) ? 'icon-green' : 'icon-red' ?>"></i>
            Varnish: <strong><?= !empty($data['enabled']) && !empty($data['allowed']) ? 'Enabled' : 'Disabled' ?></strong></p>
        <?php if (empty($data['allowed'])): ?><div class="alert alert-info u-mb20" role="status"><p>The hosting package does not currently allow Varnish.</p></div><?php endif; ?>
        <form method="post" class="u-mb20"><?php $formFields('toggle-account'); ?><input type="hidden" name="enabled" value="<?= empty($data['enabled']) ? '1' : '0' ?>"><button type="submit" class="button button-secondary"><?= empty($data['enabled']) ? 'Enable' : 'Disable' ?> for this account</button></form>
        <?php if (isset($data['connection'])): ?>
            <section class="u-mb20" aria-label="Site connection details"><h2 class="u-mb20">Site connection details</h2>
                <?php foreach ($data['connection'] as $key => $value): ?>
                    <div class="u-mb10"><label class="form-label" for="connection-<?= $escape($key) ?>"><?= $escape(ucfirst(str_replace('_', ' ', $key))) ?></label><input class="form-control" id="connection-<?= $escape($key) ?>" type="text" value="<?= $escape($value) ?>" readonly autocomplete="off"></div>
                <?php endforeach; ?>
            </section>
        <?php endif; ?>
        <h2 class="u-mb20">Websites</h2>
    <?php elseif ($pageError === ''): ?>
        <div class="alert alert-info u-mb20" role="status"><p>Install the Varnish service addon to enable cache management.</p></div>
    <?php endif; ?>
    <?php foreach ($data['sites'] as $site): ?>
        <details class="box-collapse u-mb10" <?= $site['domain'] === $selectedDomain ? 'open' : '' ?>>
            <summary class="box-collapse-header"><i class="fas fa-globe u-mr10"></i><?= $escape($site['domain']) ?></summary>
            <div class="box-collapse-content">
                <p class="u-mb10">Status: <strong><?= $site['suspended'] ? 'Suspended' : (!empty($site['enabled']) ? 'Enabled' : 'Disabled') ?></strong></p>
                <?php if ($site['aliases']): ?><p class="u-mb10">Aliases: <?= $escape(implode(', ', $site['aliases'])) ?></p><?php endif; ?>
                <?php if ($managed): ?>
                    <p class="u-mb20">Route: <?= !empty($site['routing_active']) ? 'Varnish' : 'Original' ?></p>
                    <div class="toolbar-buttons u-mb20">
                        <form method="post"><?php $formFields('credentials', $site['domain']); ?><button type="submit" class="button button-secondary"><i class="fas fa-key icon-orange"></i>Show site token</button></form>
                        <form method="post"><?php $formFields('flush', $site['domain']); ?><button type="submit" class="button button-secondary"><i class="fas fa-trash icon-red"></i>Clear site cache</button></form>
                        <form method="post"><?php $formFields('toggle-site', $site['domain']); ?><input type="hidden" name="enabled" value="<?= empty($site['enabled']) ? '1' : '0' ?>"><button type="submit" class="button button-secondary"><?= empty($site['enabled']) ? 'Enable site' : 'Disable site' ?></button></form>
                    </div>
                    <details class="box-collapse u-mb10">
                        <summary class="box-collapse-header">Profile and site VCL</summary>
                        <div class="box-collapse-content"><form method="post">
                            <?php $formFields('configure-site', $site['domain']); ?>
                            <div class="u-mb20"><label class="form-label" for="profile-<?= $escape($site['domain']) ?>">Profile</label><select class="form-select" id="profile-<?= $escape($site['domain']) ?>" name="profile">
                                <?php foreach (['general' => 'General', 'wordpress' => 'WordPress', 'woocommerce' => 'WooCommerce', 'ultracache' => 'UltraCache for Hestia'] as $value => $label): ?>
                                    <option value="<?= $escape($value) ?>" <?= $site['profile'] === $value ? 'selected' : '' ?>><?= $escape($label) ?></option>
                                <?php endforeach; ?>
                            </select></div>
                            <p class="u-mb20">Optional rules added to this profile. Leave empty to use the profile as supplied.</p>
                            <div class="u-mb20"><label class="form-label" for="recv-<?= $escape($site['domain']) ?>">Request VCL</label><textarea class="form-control" id="recv-<?= $escape($site['domain']) ?>" name="custom_recv" rows="6" maxlength="16384" spellcheck="false"><?= $escape($site['custom_recv']) ?></textarea></div>
                            <div class="u-mb20"><label class="form-label" for="backend-<?= $escape($site['domain']) ?>">Backend response VCL</label><textarea class="form-control" id="backend-<?= $escape($site['domain']) ?>" name="custom_backend_response" rows="6" maxlength="16384" spellcheck="false"><?= $escape($site['custom_backend_response']) ?></textarea></div>
                            <button type="submit" class="button"><i class="fas fa-floppy-disk icon-purple"></i>Validate and apply</button>
                        </form></div>
                    </details>
                    <details class="box-collapse u-mb10">
                        <summary class="box-collapse-header">Change site purge token</summary>
                        <div class="box-collapse-content"><form method="post">
                            <?php $formFields('token', $site['domain']); ?>
                            <div class="u-mb20"><label class="form-label" for="token-<?= $escape($site['domain']) ?>">New purge token</label><input class="form-control" id="token-<?= $escape($site['domain']) ?>" type="password" name="password" minlength="12" maxlength="256" pattern="[A-Za-z0-9_-]+" autocomplete="new-password" required></div>
                            <button type="submit" class="button"><i class="fas fa-floppy-disk icon-purple"></i>Change token</button>
                        </form></div>
                    </details>
                <?php endif; ?>
            </div>
        </details>
    <?php endforeach; ?>
    <?php if ($managed && !$data['sites']): ?><p class="u-mb20">This account has no websites.</p><?php endif; ?>
    <p class="u-mt20"><small>Version <?= $escape($meta['version']) ?></small></p>
</div></div>
<?php require $root . '/web/templates/footer.php'; ?>
