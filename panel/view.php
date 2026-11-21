<?php
require $root . '/web/templates/header.php';
$panel = top_panel($headerOwner, $TAB);
?>
<script>document.title = <?= json_encode($meta['title'], JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT) ?>;</script>
<div class="toolbar"><div class="toolbar-inner"><div class="toolbar-buttons">
    <?php if ($isAdmin): ?><a class="button button-secondary" href="./" title="Return to the administrator overview of all accounts and websites.">All accounts</a><?php endif; ?>
    <a class="button button-secondary" href="/list/web/" title="Return to the Hestia website list."><i class="fas fa-arrow-left icon-blue"></i>Back</a>
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
        <form method="post" class="u-mb20"><?php $formFields('toggle-account'); ?><input type="hidden" name="enabled" value="<?= empty($data['enabled']) ? '1' : '0' ?>"><button type="submit" class="button button-secondary" title="Enable or disable Varnish for every website in this account. Individual website choices are retained."><?= empty($data['enabled']) ? 'Enable' : 'Disable' ?> for this account</button></form>
        <?php if (isset($data['connection'])): ?>
            <section class="u-mb20" aria-label="Site connection details"><h2 class="u-mb20">Site connection details</h2>
                <?php foreach ($data['connection'] as $key => $value): ?>
                    <div class="u-mb10"><label class="form-label" for="connection-<?= $escape($key) ?>"><?= $escape(ucfirst(str_replace('_', ' ', $key))) ?></label><input title="Read-only connection information for this website. Copy the relevant value into the application cache settings." class="form-control" id="connection-<?= $escape($key) ?>" type="text" value="<?= $escape($value) ?>" readonly autocomplete="off"></div>
                <?php endforeach; ?>
            </section>
        <?php endif; ?>
        <h2 class="u-mb20">Websites</h2>
    <?php elseif ($pageError === ''): ?>
        <div class="alert alert-info u-mb20" role="status"><p>Install the Varnish service addon to enable cache management.</p></div>
    <?php endif; ?>
    <?php foreach ($data['sites'] as $site): ?>
        <details class="box-collapse u-mb10" <?= $site['domain'] === $selectedDomain ? 'open' : '' ?>>
            <summary title="Expand or collapse this website’s cache controls." class="box-collapse-header"><i class="fas fa-globe u-mr10"></i><?= $escape($site['domain']) ?></summary>
            <div class="box-collapse-content">
                <p class="u-mb10">Status: <strong><?= $site['suspended'] ? 'Suspended' : (!empty($site['enabled']) ? 'Enabled' : 'Disabled') ?></strong></p>
                <?php if ($site['aliases']): ?><p class="u-mb10">Aliases: <?= $escape(implode(', ', $site['aliases'])) ?></p><?php endif; ?>
                <?php if ($managed): ?>
                    <p class="u-mb20">Route: <?= !empty($site['routing_active']) ? 'Varnish' : 'Original' ?></p>
                    <div class="toolbar-buttons u-mb20">
                        <a class="button button-secondary" href="?owner=<?= rawurlencode($owner) ?>&amp;domain=<?= rawurlencode($site['domain']) ?>&amp;cookies=1" title="Edit this website’s cookie cache policies in a searchable spreadsheet. Central choices are inherited unless you override them.">Cookie policies</a>
                        <form method="post"><?php $formFields('credentials', $site['domain']); ?><button type="submit" class="button button-secondary" title="Reveal this website’s local purge endpoint and secret token. Other websites use separate tokens."><i class="fas fa-key icon-orange"></i>Show site token</button></form>
                        <form method="post"><?php $formFields('flush', $site['domain']); ?><button type="submit" class="button button-secondary" title="Invalidate cached objects belonging to this website. Other websites keep their cache."><i class="fas fa-trash icon-red"></i>Clear site cache</button></form>
                        <form method="post"><?php $formFields('toggle-site', $site['domain']); ?><input type="hidden" name="enabled" value="<?= empty($site['enabled']) ? '1' : '0' ?>"><button type="submit" class="button button-secondary" title="Enable or disable Varnish only for this website and its aliases. Disabling restores its original web routing."><?= empty($site['enabled']) ? 'Enable site' : 'Disable site' ?></button></form>
                    </div>
                    <details class="box-collapse u-mb10">
                        <summary class="box-collapse-header" title="Control server-side public HTML caching. Known CMS private routes and actions stay excluded.">Server cache and CMS rules</summary>
                        <div class="box-collapse-content"><form method="post">
                            <?php $formFields('configure-cache-policy', $site['domain']); $cacheId = $site['domain']; ?>
                            <label class="form-label u-block u-mb20"><input type="checkbox" name="aggressive" value="1" <?= !empty($site['aggressive']) ? 'checked' : '' ?> title="Use the selected server cache duration for public anonymous HTML despite generic origin cache restrictions. Known login markers, private CMS routes, cart actions and explicit private choices keep their exclusions."> Enable aggressive caching</label>
                            <label class="form-label" for="aggressive-ttl-<?= $escape($cacheId) ?>">Server cache duration (seconds)</label>
                            <input class="form-control u-mb20" id="aggressive-ttl-<?= $escape($cacheId) ?>" type="number" min="1" step="1" name="aggressive_ttl" value="<?= $escape($site['aggressive_ttl'] ?? 86400) ?>" title="Lifetime used by aggressive caching. A shorter generic origin cache lifetime does not cap this choice. Browser cache settings are separate.">
                            <p class="u-mb10">Aggressive caching serves warm public HITs entirely in Varnish. Original HTML and embedded tokens are cached unchanged; opaque session state is not queried.</p>
                            <p class="u-mb10">CMS private paths and actions are recognized automatically, including configured routes when available. They remain excluded with aggressive caching enabled.</p>
                            <?php if (!empty($site['cms_discovery']['error'])): ?><p class="u-mb10" role="status"><?= $escape($site['cms_discovery']['error']) ?></p><?php endif; ?>
                            <?php if (!empty($site['cms_installations'])): ?>
                                <ul class="u-mb20"><?php foreach ($site['cms_installations'] as $cms): ?><li><strong><?= $escape(['wordpress'=>'WordPress / WooCommerce','joomla'=>'Joomla','drupal'=>'Drupal','magento'=>'Magento / Adobe Commerce','prestashop'=>'PrestaShop'][$cms['cms']] ?? $cms['cms']) ?></strong> · <?= $escape($cms['base']) ?><?php if (!empty($cms['private_paths'])): ?> · Configured private paths: <?= $escape(implode(', ', $cms['private_paths'])) ?><?php endif; ?></li><?php endforeach; ?></ul>
                            <?php else: ?><p class="u-mb20"><?= ($site['cms_discovery']['status'] ?? '') === 'complete' ? 'No supported CMS detected.' : 'CMS discovery is pending or unavailable. Refresh detection to check this website.' ?></p><?php endif; ?>
                            <label class="form-label" for="private-paths-<?= $escape($cacheId) ?>">Additional private path prefixes</label>
                            <textarea class="form-control u-mb10" id="private-paths-<?= $escape($cacheId) ?>" name="custom_private_paths" rows="4" spellcheck="false" placeholder="/custom-members-area/" title="One literal URL prefix per line; no regular expressions. /members/ covers that subtree, while /members also matches /membership. Known CMS routes are automatic. Applies only to this website and its aliases."><?= $escape(implode("\n", $site['custom_private_paths'] ?? [])) ?></textarea>
                            <label class="form-label" for="cms-excluded-<?= $escape($cacheId) ?>">Excluded CMS directories</label>
                            <textarea class="form-control u-mb10" id="cms-excluded-<?= $escape($cacheId) ?>" name="cms_excluded_directories" rows="3" spellcheck="false" placeholder="/old-site/" title="One literal directory path relative to this website’s document root per line, using URL encoding for special characters. Detection skips the directory and its children before reading CMS configuration or querying its database. No regular expressions."><?= $escape(implode("\n", $site['cms_excluded_directories'] ?? [])) ?></textarea>
                            <p class="u-mb20">Use this for retired installations. Saving removes their detected CMS routes and cookie names. It does not delete files, change their database settings or block their URLs. Use <code>/</code> to skip all CMS detection for this website.</p>
                            <button type="submit" class="button" title="Validate and apply this website’s server cache behavior and additional private paths. Profile, tokens, browser cache and other websites are preserved.">Save cache behavior</button>
                        </form>
                        <form method="post" class="u-mt20"><?php $formFields('refresh-cms', $site['domain']); ?><button type="submit" class="button" title="Read this website’s native document root and configured CMS routes as its hosting account. Keeps existing unsaved form edits separate; save them before refreshing.">Refresh CMS detection</button></form>
                        </div>
                    </details>
                    <details class="box-collapse u-mb10">
                        <summary class="box-collapse-header" title="Browser caching for existing files served directly by Nginx. Dynamic responses retain their application policy.">Browser cache</summary>
                        <div class="box-collapse-content"><form method="post">
                            <?php $formFields('configure-browser-cache', $site['domain']); $browserChoice = $site['browser_cache']; $browserId = $site['domain']; $browserSite = true; require __DIR__ . '/browser-cache.php'; ?>
                        </form></div>
                    </details>
                    <details class="box-collapse u-mb10">
                        <summary class="box-collapse-header" title="Choose this website’s cache profile and optional supported VCL additions.">Profile and site VCL</summary>
                        <div class="box-collapse-content"><form method="post">
                            <?php $formFields('configure-site', $site['domain']); ?>
                            <div class="u-mb20"><label class="form-label" for="profile-<?= $escape($site['domain']) ?>">Profile</label><select title="Basic: WordPress/WooCommerce and public HTTP content. UltraCache: the same policy with ESI and async parent integration." class="form-select" id="profile-<?= $escape($site['domain']) ?>" name="profile">
                                <?php foreach (['basic' => 'Basic', 'ultracache' => 'UltraCache'] as $value => $label): ?>
                                    <option value="<?= $escape($value) ?>" <?= $site['profile'] === $value ? 'selected' : '' ?>><?= $escape($label) ?></option>
                                <?php endforeach; ?>
                            </select></div>
                            <p class="u-mb20">Optional rules added to this profile. Leave empty to use the profile as supplied.</p>
                            <div class="u-mb20"><label class="form-label" for="recv-<?= $escape($site['domain']) ?>">Request VCL</label><textarea title="Optional supported VCL rules for incoming requests to this website. Leave empty to use the selected profile unchanged." class="form-control" id="recv-<?= $escape($site['domain']) ?>" name="custom_recv" rows="6" spellcheck="false"><?= $escape($site['custom_recv']) ?></textarea></div>
                            <div class="u-mb20"><label class="form-label" for="backend-<?= $escape($site['domain']) ?>">Backend response VCL</label><textarea title="Optional supported VCL rules for responses from this website’s origin, such as cache lifetime. Leave empty to use the profile unchanged." class="form-control" id="backend-<?= $escape($site['domain']) ?>" name="custom_backend_response" rows="6" spellcheck="false"><?= $escape($site['custom_backend_response']) ?></textarea></div>
                            <button type="submit" class="button" title="Validate and apply this website’s profile and supported VCL additions. Invalid changes leave the previous policy active."><i class="fas fa-floppy-disk icon-purple"></i>Validate and apply</button>
                        </form></div>
                    </details>
                    <details class="box-collapse u-mb10">
                        <summary class="box-collapse-header" title="Change the secret used by applications to invalidate this website’s Varnish cache.">Change site purge token</summary>
                        <div class="box-collapse-content"><form method="post">
                            <?php $formFields('token', $site['domain']); ?>
                            <div class="u-mb20"><label class="form-label" for="token-<?= $escape($site['domain']) ?>">New purge token</label><input title="New site-specific purge secret: At least 12 letters, digits, underscores or hyphens. Update it manually in applications that use the old secret." class="form-control" id="token-<?= $escape($site['domain']) ?>" type="password" name="password" minlength="12" pattern="[A-Za-z0-9_-]+" autocomplete="new-password" required></div>
                            <button type="submit" class="button" title="Replace only this website’s purge token. Application settings are independent and are not updated automatically."><i class="fas fa-floppy-disk icon-purple"></i>Change token</button>
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
