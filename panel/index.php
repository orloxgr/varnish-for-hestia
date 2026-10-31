<?php
// This is an additional route. Existing Hestia files are only read/included.
declare(strict_types=1);
$meta = json_decode(file_get_contents('__INSTALL_ROOT__/addon.json'), true, 16, JSON_THROW_ON_ERROR);
if ($_SERVER['REQUEST_METHOD'] === 'GET' && empty($_SERVER['HTTP_REFERER'])) {
    // A public landing link supplies a real same-origin navigation for Hestia's
    // strict GET CSRF policy. No account data is accessed on this landing page.
    header('Cache-Control: no-store');
    header('Content-Type: text/html; charset=utf-8');
    $title = htmlspecialchars($meta['title'], ENT_QUOTES, 'UTF-8');
    echo '<!doctype html><html lang="en"><meta charset="utf-8"><title>' . $title .
         '</title><main><h1>' . $title . '</h1><p><a href="./">Open ' . $title . '</a></p></main></html>';
    exit;
}
$root = '/usr/local/hestia';
chdir($root . '/web');
$TAB = 'WEB';
// main.php's legacy policies read a caller-provided $panel[$user]. Resolve it
// lazily from the native cached account data after main.php checks the session.
$panel = new class implements ArrayAccess {
    public function offsetExists(mixed $offset): bool { return true; }
    public function offsetGet(mixed $offset): mixed {
        $name = trim((string)$offset, "'");
        if (!preg_match('/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$/D', $name)) {
            return ['SUSPENDED' => 'yes'];
        }
        return get_user_data($name)[$name] ?? ['SUSPENDED' => 'yes'];
    }
    public function offsetSet(mixed $offset, mixed $value): void { throw new LogicException('Read only'); }
    public function offsetUnset(mixed $offset): void { throw new LogicException('Read only'); }
};
require $root . '/web/inc/main.php';

header('Cache-Control: no-store, private');
header('X-Robots-Tag: noindex, nofollow');
$actor = $_SESSION['user'] ?? '';
$owner = $actor;
if (($_SESSION['userContext'] ?? '') === 'admin' && !empty($_SESSION['look'])) {
    $owner = $_SESSION['look'];
}
$respond = static function (int $code, array $data): never {
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_THROW_ON_ERROR);
    exit;
};
if ((isset($_GET['owner']) && $_GET['owner'] !== $owner) ||
    (isset($_POST['owner']) && $_POST['owner'] !== $owner)) {
    $respond(403, ['ok' => false, 'error' => 'Another account cannot be selected.']);
}
$action = 'inventory';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!is_string($_POST['token'] ?? null) ||
        !hash_equals($_SESSION['token'] ?? '', $_POST['token']) || !empty($read_only)) {
        $respond(403, ['ok' => false, 'error' => 'Request token invalid or account is read only.']);
    }
    $action = $_POST['action'] ?? '';
} elseif ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    $respond(405, ['ok' => false, 'error' => 'Method not supported.']);
}
$request = ['actor' => $actor, 'owner' => $owner, 'action' => $action,
            'domain' => $_POST['domain'] ?? null,
            'enabled' => ($_POST['enabled'] ?? '') === '1',
            'profile' => $_POST['profile'] ?? null,
            'password' => $_POST['password'] ?? null,
            'custom_recv' => $_POST['custom_recv'] ?? '',
            'custom_backend_response' => $_POST['custom_backend_response'] ?? ''];
$pipes = [];
$process = proc_open(['/usr/bin/sudo', '-n', $root . '/bin/' . $meta['command']],
    [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
if (!is_resource($process)) {
    $respond(503, ['ok' => false, 'error' => 'Addon bridge unavailable.']);
}
fwrite($pipes[0], json_encode($request, JSON_THROW_ON_ERROR));
fclose($pipes[0]);
$output = stream_get_contents($pipes[1], 1048576);
fclose($pipes[1]);
stream_get_contents($pipes[2], 4096);
fclose($pipes[2]);
$code = proc_close($process);
$data = json_decode($output, true);
if ($code !== 0 || !is_array($data) || empty($data['ok'])) {
    $respond(403, ['ok' => false, 'error' => 'Request refused or service unavailable.']);
}
if (($_GET['format'] ?? '') === 'json' || ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_POST['display'] ?? '') !== 'html')) {
    $respond(200, $data);
}
$escape = static fn($s) => htmlspecialchars((string)$s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title><?= $escape($meta['title']) ?></title>
<style>body{font:16px system-ui;background:#f4f6f8;color:#1d2939;margin:3rem auto;max-width:900px;padding:0 20px}main{background:white;border:1px solid #d0d5dd;border-radius:12px;padding:28px}a{color:#175cd3}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:14px 8px;border-bottom:1px solid #eaecf0}small{color:#475467}</style>
</head><body><main>
<a href="/list/web/">Back to Hestia websites</a>
<h1><?= $escape($meta['title']) ?></h1>
<p>Account: <strong><?= $escape($owner) ?></strong></p>
<?php if (empty($data['service_installed']) && !isset($data['enabled'])): ?>
<p>Service management has not been installed yet.</p>
<?php else: ?>
<?php if (isset($data['connection'])): ?>
<h2>Site connection</h2><pre><?= $escape(json_encode($data['connection'], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)) ?></pre>
<?php endif; ?>
<?php if (!empty($data['purged'])): ?><p>The selected site's cache was cleared.</p><?php endif; ?>
<?php if (empty($data['allowed'])): ?><p>The hosting package does not currently allow Varnish.</p><?php endif; ?>
<form method="post">
<input type="hidden" name="token" value="<?= $escape($_SESSION['token']) ?>">
<input type="hidden" name="action" value="toggle-account"><input type="hidden" name="display" value="html">
<input type="hidden" name="enabled" value="<?= !empty($data['enabled']) ? '0' : '1' ?>">
<button type="submit"><?= !empty($data['enabled']) ? 'Disable Varnish for this account' : 'Enable Varnish for this account' ?></button>
</form>
<?php foreach ($data['sites'] as $site): ?>
<section><h2><?= $escape($site['domain']) ?></h2>
<p>Aliases: <?= $escape(implode(', ', $site['aliases'])) ?> · <?= !empty($site['routing_active']) ? 'Varnish route selected' : 'Original route selected' ?></p>
<?php foreach (['toggle-site' => !empty($site['enabled']) ? 'Disable site cache' : 'Enable site cache', 'credentials' => 'View site token', 'flush' => 'Clear site cache'] as $operation => $label): ?>
<form method="post" style="display:inline-block">
<input type="hidden" name="token" value="<?= $escape($_SESSION['token']) ?>">
<input type="hidden" name="action" value="<?= $escape($operation) ?>"><input type="hidden" name="display" value="html">
<input type="hidden" name="domain" value="<?= $escape($site['domain']) ?>">
<input type="hidden" name="enabled" value="<?= !empty($site['enabled']) ? '0' : '1' ?>">
<button type="submit"><?= $escape($label) ?></button></form>
<?php endforeach; ?>
<details><summary>Profile and site VCL</summary>
<form method="post">
<input type="hidden" name="token" value="<?= $escape($_SESSION['token']) ?>">
<input type="hidden" name="action" value="configure-site"><input type="hidden" name="display" value="html">
<input type="hidden" name="domain" value="<?= $escape($site['domain']) ?>">
<p><label>Profile <select name="profile">
<?php foreach (['general' => 'General', 'wordpress' => 'WordPress', 'woocommerce' => 'WooCommerce', 'ultracache' => 'UltraCache for Hestia'] as $value => $label): ?>
<option value="<?= $escape($value) ?>" <?= $site['profile'] === $value ? 'selected' : '' ?>><?= $escape($label) ?></option>
<?php endforeach; ?></select></label></p>
<p><label>Request section<br><textarea name="custom_recv" rows="6" maxlength="16384" style="width:100%;font-family:monospace"><?= $escape($site['custom_recv']) ?></textarea></label></p>
<p><label>Backend response section<br><textarea name="custom_backend_response" rows="6" maxlength="16384" style="width:100%;font-family:monospace"><?= $escape($site['custom_backend_response']) ?></textarea></label></p>
<button type="submit">Validate and apply</button></form>
</details>
<details><summary>Change site purge token</summary><form method="post">
<input type="hidden" name="token" value="<?= $escape($_SESSION['token']) ?>">
<input type="hidden" name="action" value="token"><input type="hidden" name="display" value="html">
<input type="hidden" name="domain" value="<?= $escape($site['domain']) ?>">
<label>New token <input type="password" name="password" minlength="12" maxlength="256" pattern="[A-Za-z0-9_-]+" autocomplete="new-password" required></label>
<button type="submit">Change token</button></form></details>
</section>
<?php endforeach; ?>
<?php endif; ?>
<?php if (empty($data['service_installed']) && !isset($data['enabled'])): ?>
<table><thead><tr><th>Website</th><th>Aliases</th><th>Status</th></tr></thead><tbody>
<?php foreach ($data['sites'] as $site): ?>
<tr><td><?= $escape($site['domain']) ?></td><td><?= $escape(implode(', ', $site['aliases'])) ?></td><td><?= $site['suspended'] ? 'Suspended' : 'Active' ?></td></tr>
<?php endforeach; ?>
</tbody></table>
<form method="post">
<input type="hidden" name="token" value="<?= $escape($_SESSION['token']) ?>">
<input type="hidden" name="action" value="validate-site">
<label>Website <select name="domain">
<?php foreach ($data['sites'] as $site): ?>
<option value="<?= $escape($site['domain']) ?>"><?= $escape($site['domain']) ?></option>
<?php endforeach; ?>
</select></label> <button type="submit">Check site access</button>
</form>
<?php endif; ?>
<small>Version <?= $escape($meta['version']) ?></small>
</main></body></html>
