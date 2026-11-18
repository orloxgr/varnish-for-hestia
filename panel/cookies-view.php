<?php
require $root . '/web/templates/header.php';
$panel = top_panel($headerOwner, $TAB);
$cookieDomain = $data['domain'] ?? $request['domain'] ?? null;
$centralCookies = ($data['cookie_scope'] ?? '') === 'central';
$back = $centralCookies ? './' : '?owner=' . rawurlencode($owner) . '&domain=' . rawurlencode((string)$cookieDomain);
$choices = $data['cookie_policies'] ?? ['schemaVersion' => 1, 'rules' => []];
?>
<style>
.cookie-toolbar{display:flex;flex-wrap:wrap;gap:12px;align-items:end;margin:18px 0}.cookie-toolbar label{display:grid;gap:5px}.cookie-toolbar input,.cookie-toolbar select{min-width:150px}.cookie-sheet{overflow:auto;border:1px solid #80808066;border-radius:8px}.cookie-sheet table{width:100%;table-layout:fixed;border-collapse:collapse}.cookie-sheet th,.cookie-sheet td{padding:12px;vertical-align:top;border-bottom:1px solid #80808055;text-align:left}.cookie-sheet th{background:#444;color:#fff}.cookie-sheet th:first-child{width:3%}.cookie-sheet th:nth-child(2){width:22%}.cookie-sheet th:nth-child(3){width:35%}.cookie-sheet th:nth-child(4){width:20%}.cookie-sheet th:nth-child(5){width:20%}.cookie-sheet .cookie-field{height:44px!important;min-height:44px;box-sizing:border-box;width:100%;margin:0;line-height:normal}.cookie-sheet input[type=text]{min-width:0}.cookie-sheet .cookie-description{height:85px!important;max-height:85px;resize:vertical;overflow-y:auto;line-height:1.4}.cookie-sheet small{display:block;margin-top:8px;font-size:12px;line-height:1.5;overflow-wrap:anywhere}.cookie-sheet tr[data-dirty=true]{box-shadow:inset 3px 0 #727cf5}.cookie-proposal{display:flex;align-items:center;padding:0 12px;border:1px solid #80808066;border-radius:4px;font-weight:600}.cookie-explain{margin-top:8px;white-space:normal;text-align:left;padding:5px 9px!important;font-size:12px!important}.cookie-detail-row[hidden]{display:none}.cookie-detail-row>td{padding:20px 24px;background:#80808012}.cookie-detail-grid{display:grid;grid-template-columns:1fr 1.2fr 1.4fr;gap:24px}.cookie-detail-grid strong{display:block;margin-bottom:8px}.cookie-detail-grid p,.cookie-full-description{margin:0;line-height:1.6;overflow-wrap:anywhere}.cookie-full-description{margin-top:18px}.cookie-evidence{margin-top:14px;font-size:12px;overflow-wrap:anywhere}.cookie-evidence a{text-decoration:underline}.cookie-message{min-height:1.5em}.cookie-paste{width:100%;box-sizing:border-box}@media(max-width:900px){.cookie-detail-grid{grid-template-columns:1fr}}
</style>
<div class="toolbar"><div class="toolbar-inner"><div class="toolbar-buttons">
<a class="button button-secondary" href="<?= $escape($back) ?>" title="Return to cache management. Unsaved cookie edits stay on this page only.">← Back</a>
<button class="button" type="submit" form="cookie-form" title="Validate, compile and activate these choices. Only websites whose executable policy changed are invalidated.">Save &amp; apply</button>
</div></div></div>
<div class="container"><div class="form-container form-container-wide">
<h1 class="u-mb10">Cookie cache policies</h1>
<p class="u-mb10"><strong><?= $centralCookies ? 'All websites · central choices' : $escape($cookieDomain) ?></strong><?= $centralCookies ? ' · Website overrides take precedence.' : ' · Only this website and its aliases.' ?></p>
<?php if ($pageError !== ''): ?><div class="alert alert-danger u-mb20" role="alert"><p><?= $escape($pageError) ?> The previous policy remains active.</p></div>
<?php elseif (!empty($data['cookie_policy_saved'])): ?><div class="alert alert-success u-mb20" role="status"><p>Cookie policies were compiled and applied.</p></div><?php endif; ?>
<p class="u-mb10">Cookies stay in the browser and reach the application. <strong>Shared HTML</strong> shares public HTML and delivers original provider cookies only to their visitor, without storing or replaying those values. <strong>Public variant</strong> adds the cookie value to the cache key; <strong>Private</strong> sends matching requests to the application.</p>
<p class="u-mb10">Known login and cart/session handling stays active. A website’s aggressive mode can override generic origin cache restrictions for anonymous HTML; explicit Private choices remain private. Every bundled cookie has a versioned, executable default. Inferred confidence describes the evidence, not whether its rule runs. Cookie issuance and consent use the existing provider integrations.</p>
<?php if (($data['cookie_profile'] ?? '') === 'basic'): ?><p class="u-mb10">Basic works without the WordPress plugin. Personal fragments use their application’s integration. Aggressive mode caches original HTML and embedded tokens unchanged.</p><?php endif; ?>
<?php if (!empty($data['cookie_legacy_choices'])): ?><p class="u-mb10" role="status">Legacy Automatic choices now resolve to the matching bundled action, or Public variant when no match exists. The concrete choices are shown below; saving stores them explicitly.</p><?php endif; ?>
<form id="cookie-form" method="post">
<?php $formFields($centralCookies ? 'admin-cookie-policies-save' : 'configure-cookie-policies', $cookieDomain); ?>
<input type="hidden" name="cookie_policies" id="cookie-payload">
<?php if (!$centralCookies): $integration = $data['cookie_integration'] ?? ['enabled' => false, 'url' => 'https://' . $cookieDomain . '/wp-json/ultracache/v1/cookie-policy-control']; ?>
<?php if (!empty($data['cookie_integration_notice'])): ?><p class="u-mb10" role="status"><?= $escape($data['cookie_integration_notice']) ?></p><?php endif; ?>
<details class="box-collapse u-mb20"><summary class="box-collapse-header" title="Connect an installed, compatible UltraCache WordPress integration explicitly. Basic needs no WordPress plugin.">WordPress integration · <?= !empty($integration['enabled']) ? 'Connected' : 'Not connected' ?></summary><div class="box-collapse-content">
<label class="form-label u-block u-mb10"><input type="checkbox" name="cookie_integration_enabled" value="1" <?= !empty($integration['enabled']) ? 'checked' : '' ?> title="Save & apply authenticates the configured endpoint and synchronizes these choices with the application’s supported engines. Requires a compatible UltraCache WordPress version and matching site token."> Synchronize policies with UltraCache WordPress</label>
<label class="form-label u-block u-mb10" for="cookie-integration-url">WordPress control endpoint</label><input class="form-control" id="cookie-integration-url" name="cookie_integration_url" value="<?= $escape($integration['url']) ?>" title="The exact control endpoint on this website or a native owned alias. Redirects and other websites are refused. The existing configured site token authenticates requests and responses.">
<p class="u-mt10">Enable only after installing the compatible WordPress integration and configuring the same site token. Save applies the snapshot to PHP/drop-in/Apache Static capabilities reported by that integration. Disabling clears the managed application snapshot and resumes standalone WordPress defaults; a failed operation retains the previous configuration. No websites are scanned.</p>
</div></details>
<?php endif; ?>
<div class="cookie-toolbar">
<label>Search<input class="form-control" id="cookie-search" type="search" placeholder="Name, description or provider" title="Search every local recognition record, reviewed policy and custom row."></label>
<label>Action<select class="form-select" id="cookie-action-filter" title="Filter by the currently displayed cache action."><option value="">All actions</option><option value="shared">Shared HTML</option><option value="variant">Public variant</option><option value="private">Private</option></select></label>
<label>Source<select class="form-select" id="cookie-source-filter" title="Show inherited, locally overridden or custom entries."><option value="">All entries</option><option value="local">Local choices</option><option value="inherited">Inherited/default</option><option value="custom">Custom rows</option></select></label>
<label>Rows per page<select class="form-select" id="cookie-page-size" title="Pagination changes display only. All records remain searchable and selectable."><option>25</option><option selected>100</option><option value="all">All</option></select></label>
</div>
<div class="cookie-toolbar">
<button type="button" class="button button-secondary" id="cookie-add" title="Add a custom cookie with a stable automatically generated ID. Use a trailing * for a literal prefix.">Add cookie</button>
<label>Selected rows<select class="form-select" id="cookie-bulk-action" title="Choose a cache action to apply to selected rows when you click Apply to selected."><option value="shared">Shared HTML</option><option value="variant">Public variant</option><option value="private">Private</option></select></label>
<button type="button" class="button button-secondary" id="cookie-bulk" title="Set the chosen action on selected rows. Changes take effect only after Save & apply.">Apply to selected</button>
<button type="button" class="button button-secondary" id="cookie-suggest" title="Copy each selected row’s displayed proposal into a local choice. Inferred proposals are estimates; inspect the row’s reason first.">Use proposals</button>
<button type="button" class="button button-secondary" id="cookie-reset" title="Remove local choices from selected rows and inherit the admin/bundled default again. Selected custom rows are removed.">Reset selected</button>
</div>
<p id="cookie-count" class="cookie-message" aria-live="polite"></p>
<div class="cookie-sheet"><table aria-label="Cookie cache policies"><thead><tr>
<th><input type="checkbox" id="cookie-select-page" aria-label="Select visible rows" title="Select or deselect the rows displayed on this page."></th><th>Cookie</th><th>Description</th><th>Cache action</th><th>Proposal / source</th>
</tr></thead><tbody id="cookie-rows"></tbody></table></div>
<div class="cookie-toolbar"><button type="button" class="button button-secondary" id="cookie-prev" title="Display the previous page of matching rows.">← Previous</button><span id="cookie-page"></span><button type="button" class="button button-secondary" id="cookie-next" title="Display the next page of matching rows.">Next →</button></div>
<details class="box-collapse u-mb20"><summary class="box-collapse-header" title="Paste tab-separated rows copied from Excel. IDs are created automatically.">Paste rows from Excel</summary><div class="box-collapse-content">
<p class="u-mb10">Columns: cookie name, description, action (shared/variant/private; omitted action defaults to variant). One cookie per line; a trailing * means prefix. A spreadsheet header row is optional.</p>
<textarea id="cookie-paste" class="form-control cookie-paste" rows="5" spellcheck="false" title="Paste tab-separated cookie, description and optional action columns. Existing rows are not overwritten."></textarea>
<button type="button" class="button button-secondary u-mt10" id="cookie-import" title="Append every pasted row as a custom cookie. Nothing is applied until Save & apply.">Append pasted rows</button>
</div></details>
<p id="cookie-error" class="cookie-message" role="alert"></p>
</form></div></div>
<script type="application/json" id="cookie-initial"><?= json_encode(['rows' => $data['cookie_policy_rows'] ?? [], 'settings' => $choices, 'scope' => $data['cookie_scope'] ?? 'site'], JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT | JSON_THROW_ON_ERROR) ?></script>
<script>
<?php readfile(__DIR__ . '/cookie-admin.js'); ?>
</script>
<?php require $root . '/web/templates/footer.php'; ?>
