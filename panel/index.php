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
$headerOwner = $owner;
$actorData = get_user_data($actor)[$actor] ?? [];
$isAdmin = ($actorData['ROLE'] ?? '') === 'admin' && empty($_SESSION['look']);
$requestedOwner = $_POST['owner'] ?? $_GET['owner'] ?? null;
if ($requestedOwner !== null) {
    if (!is_string($requestedOwner) || (!$isAdmin && $requestedOwner !== $owner)) {
        $respond(403, ['ok' => false, 'error' => 'Another account cannot be selected.']);
    }
    $owner = $requestedOwner;
}
$adminOverview = $isAdmin && $requestedOwner === null;
$action = $adminOverview ? 'admin-inventory' : 'inventory';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!is_string($_POST['token'] ?? null) ||
        !hash_equals($_SESSION['token'] ?? '', $_POST['token']) || !empty($read_only)) {
        $respond(403, ['ok' => false, 'error' => 'Request token invalid or account is read only.']);
    }
    $action = $_POST['action'] ?? '';
} elseif ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    $respond(405, ['ok' => false, 'error' => 'Method not supported.']);
}
if (!is_string($action)) {
    $respond(400, ['ok' => false, 'error' => 'Invalid operation.']);
}
$request = ['actor' => $actor, 'owner' => $owner, 'action' => $action,
            'domain' => $_POST['domain'] ?? null,
            'enabled' => ($_POST['enabled'] ?? '') === '1',
            'profile' => $_POST['profile'] ?? null,
            'password' => $_POST['password'] ?? null,
            'custom_recv' => $_POST['custom_recv'] ?? '',
            'custom_backend_response' => $_POST['custom_backend_response'] ?? ''];
if (str_starts_with((string)$action, 'admin-')) {
    if (!$isAdmin || !in_array($action, ['admin-inventory', 'admin-bulk', 'admin-server-settings', 'admin-memory'], true)) {
        $respond(403, ['ok' => false, 'error' => 'Administrator access required.']);
    }
    $adminOverview = true;
    if ($action === 'admin-server-settings') {
        $request['first_byte_timeout_seconds'] = filter_var($_POST['first_byte_timeout_seconds'] ?? '', FILTER_VALIDATE_INT);
    }
    $request['scope'] = $_POST['scope'] ?? null;
    $request['operation'] = $_POST['operation'] ?? null;
    $request['profile'] = $_POST['profile'] ?? null;
    $request['accounts'] = $_POST['accounts'] ?? [];
    $targets = $_POST['targets'] ?? [];
    if (!is_array($targets)) {
        $respond(400, ['ok' => false, 'error' => 'Invalid website selection.']);
    }
    $request['targets'] = array_map(static fn($value) => is_string($value) ? json_decode($value, true) : null, $targets);
}
$jsonResponse = ($_GET['format'] ?? '') === 'json' ||
    ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_POST['display'] ?? '') !== 'html');
$bridge = static function (array $payload) use ($root, $meta): array {
    $pipes = [];
    $process = proc_open(['/usr/bin/sudo', '-n', $root . '/bin/' . $meta['command']],
        [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
    if (!is_resource($process)) {
        return [1, null];
    }
    fwrite($pipes[0], json_encode($payload, JSON_THROW_ON_ERROR));
    fclose($pipes[0]);
    $output = stream_get_contents($pipes[1], 1048576);
    fclose($pipes[1]);
    stream_get_contents($pipes[2], 4096);
    fclose($pipes[2]);
    return [proc_close($process), json_decode($output, true)];
};
[$code, $data] = $bridge($request);
$pageError = '';
if ($code !== 0 || !is_array($data) || empty($data['ok'])) {
    if ($jsonResponse) {
        $respond(403, ['ok' => false, 'error' => 'Request refused or service unavailable.']);
    }
    // Hestia intercepts 4xx pages. Render form errors normally; JSON requests
    // still receive the 403 response above.
    $pageError = $action === 'configure-site'
        ? 'The profile or VCL could not be applied. The previous configuration is still active.'
        : 'The operation could not be completed. Check that the service is running and access is enabled.';
    if ($adminOverview) {
        $pageError = $action === 'admin-server-settings' ? 'The server timeout could not be applied. The previous setting remains active.' : ($action === 'admin-memory' ? 'The native memory snapshot is unavailable.' : ($action === 'admin-bulk'
            ? 'The bulk change could not be applied. Check the selection and that the service is running.'
            : 'Could not load accounts. Check that the service is installed and running.'));
    }
    [$status, $current] = $bridge(['actor' => $actor, 'owner' => $owner, 'action' => $adminOverview ? 'admin-inventory' : 'inventory']);
    $data = $status === 0 && is_array($current) && !empty($current['ok']) ? $current : ['sites' => []];
} elseif ($jsonResponse) {
    $respond(200, $data);
}
header('Content-Type: text/html; charset=utf-8');
$escape = static fn($s) => htmlspecialchars((string)$s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
$managed = !empty($data['service_installed']) || isset($data['enabled']);
$selectedDomain = is_string($_POST['domain'] ?? $_GET['domain'] ?? null) ? ($_POST['domain'] ?? $_GET['domain']) : ($data['sites'][0]['domain'] ?? '');
$message = '';
$messageType = 'success';
if ($pageError === '' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    if ($action === 'test' && isset($data['connection_ok'])) {
        $messageType = $data['connection_ok'] ? 'success' : 'danger';
        $message = $data['connection_ok']
            ? 'Connection test passed for ' . $selectedDomain . ': Dragonfly authenticated, stored, read and deleted a test key.'
            : 'Connection test failed for ' . $selectedDomain . ': the stored value could not be read back.';
    } elseif ($action === 'flush') {
        $message = isset($data['removed_keys']) ? 'Cleared ' . $data['removed_keys'] . ' cache entries for ' . $selectedDomain . '.'
            : 'The cache for ' . $selectedDomain . ' was cleared.';
    } elseif ($action === 'password') {
        $message = 'Your Dragonfly password was changed.';
    } elseif ($action === 'token') {
        $message = 'The purge token for ' . $selectedDomain . ' was changed.';
    } elseif ($action === 'configure-site') {
        $message = 'The profile and VCL for ' . $selectedDomain . ' were applied.';
    } elseif ($action === 'toggle-site') {
        $message = 'Cache access for ' . $selectedDomain . ' was ' . (!empty($request['enabled']) ? 'enabled.' : 'disabled.');
    } elseif ($action === 'toggle-account') {
        $message = 'Cache access for this account was ' . (!empty($data['enabled']) ? 'enabled.' : 'disabled.');
    } elseif ($action === 'validate-site') {
        $message = 'Website access was verified.';
    }
}
$formFields = static function (string $operation, ?string $domain = null) use ($escape, $isAdmin, $adminOverview, $owner): void {
    echo '<input type="hidden" name="token" value="' . $escape($_SESSION['token']) . '">';
    echo '<input type="hidden" name="display" value="html">';
    echo '<input type="hidden" name="action" value="' . $escape($operation) . '">';
    if ($isAdmin && !$adminOverview) {
        echo '<input type="hidden" name="owner" value="' . $escape($owner) . '">';
    }
    if ($domain !== null) {
        echo '<input type="hidden" name="domain" value="' . $escape($domain) . '">';
    }
};
require $adminOverview ? '__INSTALL_ROOT__/panel/admin-view.php' : '__INSTALL_ROOT__/panel/view.php';
