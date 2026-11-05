#!/usr/bin/env php
<?php
declare(strict_types=1);
/* Read-only HTTPS endpoint for a reviewed, signed local APT publication. */

function inside(string $path, string $root): bool {
    $prefix = rtrim(str_replace('\\', '/', $root), '/') . '/';
    $candidate = str_replace('\\', '/', $path);
    return PHP_OS_FAMILY === 'Windows'
        ? str_starts_with(strtolower($candidate), strtolower($prefix))
        : str_starts_with($candidate, $prefix);
}

function publicPath(string $target): ?string {
    if (strlen($target) > 4096 || !str_starts_with($target, '/') ||
        preg_match('/[\x00-\x20\x7f\\\\?#]/', $target) ||
        preg_match('/%(?![a-fA-F0-9]{2})/', $target) ||
        preg_match('/%(?:2f|5c)/i', $target)) return null;
    $path = rawurldecode(substr($target, 1));
    if (preg_match('/[\x00-\x20\x7f\\\\%]/', $path)) return null;
    foreach (explode('/', $path) as $part) {
        if ($part === '' || $part === '.' || $part === '..') return null;
    }
    $fixed = ['linuxbr-archive-keyring.gpg', 'linuxbr.sources', 'linuxbr.pref',
              'linuxbr-local-ca.crt', 'client.sources', 'client-https.conf',
              'client.pref', 'client-archive-keyring.gpg', 'client-readme.txt'];
    if (in_array($path, $fixed, true)) return $path;
    if (preg_match('~\Adists/trixie/(?:InRelease|Release(?:\.gpg)?|main/binary-amd64/Packages(?:\.gz)?)\z~D', $path)) return $path;
    if (preg_match('#\Apool/main/[a-z0-9][a-z0-9+.-]*_[A-Za-z0-9.+:~\-]+_(?:amd64|all)\.deb\z#D', $path)) return $path;
    return null;
}

function reply($socket, int $status, string $text, bool $head = false): void {
    $reasons = [400=>'Bad Request',403=>'Forbidden',404=>'Not Found',405=>'Method Not Allowed',408=>'Request Timeout',431=>'Request Header Fields Too Large',500=>'Internal Server Error'];
    $body = $text . "\n";
    $extra = $status === 405 ? "Allow: GET, HEAD\r\n" : '';
    @fwrite($socket, "HTTP/1.1 $status {$reasons[$status]}\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: " . strlen($body) . "\r\nConnection: close\r\nX-Content-Type-Options: nosniff\r\n$extra\r\n" . ($head ? '' : $body));
}

function serve($socket, string $root): int {
    $request = '';
    $headerDeadline = microtime(true) + 10;
    while (!str_contains($request, "\r\n\r\n")) {
        if (microtime(true) >= $headerDeadline) {
            reply($socket, 408, 'O tempo da solicitação terminou.'); return 408;
        }
        stream_set_timeout($socket, max(1, (int)ceil($headerDeadline - microtime(true))));
        $line = @fgets($socket, 4098);
        if ($line === false) {
            reply($socket, 408, 'O tempo da solicitação terminou.'); return 408;
        }
        $request .= $line;
        if (strlen($request) > 16384 || strlen($line) > 4096) {
            reply($socket, 431, 'Solicitação muito longa.'); return 431;
        }
        if (!str_ends_with($line, "\r\n")) {
            reply($socket, 400, 'Solicitação inválida.'); return 400;
        }
    }
    $lines = explode("\r\n", trim($request, "\r\n"));
    $first = array_shift($lines);
    if (!preg_match('~\A([A-Z]+) ([^ ]+) HTTP/(1\.[01])\z~D', $first, $match)) {
        reply($socket, 400, 'Solicitação inválida.'); return 400;
    }
    [$all, $method, $target, $http] = $match;
    $head = $method === 'HEAD';
    if (!in_array($method, ['GET', 'HEAD'], true)) {
        reply($socket, 405, 'Use GET ou HEAD.', $head); return 405;
    }
    $headers = [];
    if (count($lines) > 64) {
        reply($socket, 431, 'Muitos cabeçalhos.', $head); return 431;
    }
    foreach ($lines as $line) {
        if (!preg_match('/\A([A-Za-z0-9-]+):[ \t]*([^\x00-\x08\x0a-\x1f\x7f]*)\z/D', $line, $field)) {
            reply($socket, 400, 'Cabeçalho inválido.', $head); return 400;
        }
        $name = strtolower($field[1]);
        if (array_key_exists($name, $headers)) {
            reply($socket, 400, 'Cabeçalho repetido.', $head); return 400;
        }
        $headers[$name] = trim($field[2]);
    }
    if (($http === '1.1' && empty($headers['host'])) || isset($headers['transfer-encoding']) ||
        isset($headers['authorization']) || isset($headers['proxy-authorization']) ||
        (isset($headers['content-length']) && $headers['content-length'] !== '0')) {
        reply($socket, 400, 'Solicitação sem suporte.', $head); return 400;
    }
    $relative = publicPath($target);
    if ($relative === null) {
        reply($socket, 404, 'Arquivo não publicado.', $head); return 404;
    }
    $candidate = $root . DIRECTORY_SEPARATOR . str_replace('/', DIRECTORY_SEPARATOR, $relative);
    $resolved = realpath($candidate);
    if ($resolved === false || !is_file($resolved)) {
        reply($socket, 404, 'Arquivo não publicado.', $head); return 404;
    }
    if (!inside($resolved, $root)) {
        reply($socket, 403, 'Arquivo fora da publicação.', $head); return 403;
    }
    // Refuse symlink components, including links pointing back into the publication.
    $component = $root;
    foreach (explode('/', $relative) as $part) {
        $component .= DIRECTORY_SEPARATOR . $part;
        if (is_link($component)) {
            reply($socket, 403, 'Links não são publicados.', $head); return 403;
        }
    }
    $expected = @stat($resolved);
    $file = @fopen($resolved, 'rb');
    $actual = $file === false ? false : fstat($file);
    if ($file === false || !$expected || !$actual || $expected['dev'] !== $actual['dev'] || $expected['ino'] !== $actual['ino']) {
        if (is_resource($file)) fclose($file);
        reply($socket, 500, 'Não foi possível ler a publicação.', $head); return 500;
    }
    $type = str_ends_with($relative, '.deb') ? 'application/vnd.debian.binary-package' : 'application/octet-stream';
    stream_set_timeout($socket, 8);
    $header = "HTTP/1.1 200 OK\r\nContent-Type: $type\r\nContent-Length: {$actual['size']}\r\nConnection: close\r\nX-Content-Type-Options: nosniff\r\nCache-Control: no-cache\r\n\r\n";
    @fwrite($socket, $header);
    $deadline = microtime(true) + 120;
    if (!$head) while (!feof($file) && microtime(true) < $deadline) {
        $chunk = fread($file, 65536);
        if ($chunk === false || $chunk === '') break;
        $offset = 0;
        while ($offset < strlen($chunk)) {
            $written = @fwrite($socket, substr($chunk, $offset));
            if ($written === false || $written === 0 || microtime(true) >= $deadline) break 2;
            $offset += $written;
        }
    }
    fclose($file);
    return 200;
}

function main(): int {
    if (PHP_SAPI !== 'cli' || !extension_loaded('openssl')) throw new RuntimeException('Use PHP CLI com a extensão OpenSSL.');
    $options = getopt('', ['root:', 'cert:', 'key:', 'bind:', 'port:', 'allow-lan']);
    foreach (['root', 'cert', 'key'] as $required) {
        if (empty($options[$required]) || !is_string($options[$required])) throw new RuntimeException("Informe --$required com um caminho explícito.");
    }
    $root = realpath($options['root']);
    $cert = realpath($options['cert']);
    $key = realpath($options['key']);
    if (!$root || !is_dir($root) || !$cert || !is_file($cert) || !$key || !is_file($key)) throw new RuntimeException('Diretório, certificado ou chave não encontrados.');
    if (inside($cert, $root) || inside($key, $root)) throw new RuntimeException('O certificado e a chave devem ficar fora do diretório publicado.');
    if (PHP_OS_FAMILY !== 'Windows' && (fileperms($key) & 0077) !== 0) throw new RuntimeException('A chave TLS precisa de permissão 0600, acessível apenas ao proprietário.');
    $bind = $options['bind'] ?? '127.0.0.1';
    $port = $options['port'] ?? '8443';
    if (!is_string($bind) || !filter_var($bind, FILTER_VALIDATE_IP) || !is_string($port) || !ctype_digit($port) || (int)$port < 1 || (int)$port > 65535) throw new RuntimeException('Endereço ou porta inválidos.');
    if (!in_array($bind, ['127.0.0.1', '::1'], true) && !array_key_exists('allow-lan', $options)) throw new RuntimeException('Para escutar na rede local, informe --allow-lan explicitamente.');
    $context = stream_context_create(['ssl'=>[
        'local_cert'=>$cert, 'local_pk'=>$key, 'verify_peer'=>false,
        'disable_compression'=>true, 'crypto_method'=>STREAM_CRYPTO_METHOD_TLSv1_2_SERVER | STREAM_CRYPTO_METHOD_TLSv1_3_SERVER,
    ]]);
    $endpoint = 'tcp://' . (str_contains($bind, ':') ? "[$bind]" : $bind) . ':' . $port;
    $server = @stream_socket_server($endpoint, $number, $error, STREAM_SERVER_BIND | STREAM_SERVER_LISTEN, $context);
    if (!$server) throw new RuntimeException('Não foi possível abrir a porta HTTPS: ' . $error);
    fwrite(STDOUT, json_encode(['status'=>'ready', 'listen'=>stream_socket_get_name($server, false)], JSON_UNESCAPED_SLASHES) . "\n");
    while (true) {
        $socket = @stream_socket_accept($server, 1);
        if (!$socket) continue;
        stream_set_timeout($socket, 8);
        $crypto = @stream_socket_enable_crypto($socket, true, STREAM_CRYPTO_METHOD_TLSv1_2_SERVER | STREAM_CRYPTO_METHOD_TLSv1_3_SERVER);
        if ($crypto === true) {
            try { $status = serve($socket, $root); }
            catch (Throwable $error) { reply($socket, 500, 'Não foi possível atender à solicitação.'); $status = 500; }
            fwrite(STDOUT, json_encode(['status'=>$status]) . "\n");
        }
        fclose($socket);
    }
}

if (realpath($_SERVER['SCRIPT_FILENAME'] ?? '') === __FILE__) {
    try { exit(main()); }
    catch (Throwable $error) { fwrite(STDERR, $error->getMessage() . "\n"); exit(1); }
}
