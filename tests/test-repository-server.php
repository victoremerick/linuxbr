#!/usr/bin/env php
<?php
declare(strict_types=1);
/* Real loopback TLS requests against a disposable, read-only publication. */
require __DIR__ . '/../scripts/repository-server.php';

function check(bool $condition, string $message): void {
    if (!$condition) throw new RuntimeException($message);
}

function tlsFixture(string $root): void {
    $config = "$root/openssl.cnf";
    file_put_contents($config, "[req]\ndistinguished_name=dn\n[dn]\nCN=localhost\n[v3_ca]\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\n[server_cert]\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost,IP:127.0.0.1\n");
    $options = ['config'=>$config, 'digest_alg'=>'sha256', 'private_key_bits'=>2048, 'private_key_type'=>OPENSSL_KEYTYPE_RSA];
    $caKey = openssl_pkey_new($options);
    $caRequest = openssl_csr_new(['commonName'=>'Linux BR TLS test'], $caKey, $options);
    $ca = openssl_csr_sign($caRequest, null, $caKey, 1, $options + ['x509_extensions'=>'v3_ca'], 1);
    $serverKey = openssl_pkey_new($options);
    $serverRequest = openssl_csr_new(['commonName'=>'localhost'], $serverKey, $options);
    $serverCert = openssl_csr_sign($serverRequest, $ca, $caKey, 1, $options + ['x509_extensions'=>'server_cert'], 2);
    check($ca !== false && $serverCert !== false, 'Falha ao criar certificados de teste.');
    openssl_x509_export($ca, $caText); openssl_x509_export($serverCert, $serverText);
    openssl_pkey_export($serverKey, $keyText, null, $options);
    file_put_contents("$root/ca.crt", $caText); file_put_contents("$root/server.crt", $serverText);
    file_put_contents("$root/server.key", $keyText); chmod("$root/server.key", 0600);
}

function launch(array $args, array &$pipes) {
    global $root;
    $id = bin2hex(random_bytes(4));
    $pipes = ['stdout'=>"$root/stdout-$id.txt", 'stderr'=>"$root/stderr-$id.txt"];
    $handles = [];
    $process = proc_open(array_merge([PHP_BINARY, __DIR__ . '/../scripts/repository-server.php'], $args),
        [['file', PHP_OS_FAMILY === 'Windows' ? 'NUL' : '/dev/null','r'],
         ['file', $pipes['stdout'], 'w'], ['file', $pipes['stderr'], 'w']], $handles);
    check(is_resource($process), 'Não foi possível iniciar o processo de teste.');
    return $process;
}

function stop($process, array $pipes): void {
    if (proc_get_status($process)['running']) proc_terminate($process);
    $deadline = microtime(true) + 2;
    while (proc_get_status($process)['running'] && microtime(true) < $deadline) usleep(20000);
    if (proc_get_status($process)['running']) proc_terminate($process, 9);
    proc_close($process);
}

function request(int $port, string $ca, string $payload, string $peer = 'localhost'): string {
    $context = stream_context_create(['ssl'=>['cafile'=>$ca, 'verify_peer'=>true,
        'verify_peer_name'=>true, 'peer_name'=>$peer, 'crypto_method'=>STREAM_CRYPTO_METHOD_TLSv1_2_CLIENT | STREAM_CRYPTO_METHOD_TLSv1_3_CLIENT]]);
    $socket = @stream_socket_client("tls://127.0.0.1:$port", $number, $error, 5, STREAM_CLIENT_CONNECT, $context);
    if (!$socket) { $GLOBALS['lastTlsError'] = error_get_last()['message'] ?? $error; return ''; }
    stream_set_timeout($socket, 5);
    fwrite($socket, $payload);
    $response = stream_get_contents($socket);
    fclose($socket);
    return $response === false ? '' : $response;
}

function status(string $response): int {
    return preg_match('~^HTTP/1.1 ([0-9]{3}) ~', $response, $match) ? (int)$match[1] : 0;
}

function cleanup(string $root): void {
    $resolved = realpath($root);
    $temporary = realpath(sys_get_temp_dir());
    check($resolved !== false && $temporary !== false && inside($resolved, $temporary)
        && str_starts_with(basename($resolved), 'linuxbr-https-test-'), 'Diretório temporário fora do limite permitido.');
    $entries = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($resolved, FilesystemIterator::SKIP_DOTS), RecursiveIteratorIterator::CHILD_FIRST);
    foreach ($entries as $entry) {
        if ($entry->isDir() && !$entry->isLink()) rmdir($entry->getPathname());
        else unlink($entry->getPathname());
    }
    rmdir($resolved);
}

$root = sys_get_temp_dir() . '/linuxbr-https-test-' . bin2hex(random_bytes(8));
mkdir($root, 0700);
$process = null; $pipes = []; $checks = 0; $symlink = false;
try {
    tlsFixture($root);
    $public = "$root/public"; mkdir("$public/dists/trixie/main/binary-amd64", 0755, true); mkdir("$public/pool/main", 0755, true);
    file_put_contents("$public/dists/trixie/InRelease", "signed-fixture\n");
    file_put_contents("$public/dists/trixie/main/binary-amd64/Packages.gz", gzencode("Package: linuxbr-fixture\n"));
    $deb = str_repeat("package\0bytes", 10000);
    file_put_contents("$public/pool/main/linuxbr-fixture_0.7.0~beta1_amd64.deb", $deb);
    file_put_contents("$public/client.sources", "Types: deb\n");
    file_put_contents("$public/private.key", "PRIVATE SENTINEL\n");
    file_put_contents("$root/private.txt", "PRIVATE SENTINEL\n");
    file_put_contents("$public/execute.php", '<?php file_put_contents("' . str_replace('\\', '/', $root) . '/executed", "bad");');
    $reservation = stream_socket_server('tcp://127.0.0.1:0', $number, $error);
    $port = (int)substr(strrchr(stream_socket_get_name($reservation, false), ':'), 1); fclose($reservation);
    $args = ['--root', $public, '--cert', "$root/server.crt", '--key', "$root/server.key", '--port', (string)$port];
    $process = launch($args, $pipes);
    $output = ''; $deadline = microtime(true) + 10;
    while (!str_contains($output, "\n") && microtime(true) < $deadline) { $output = file_get_contents($pipes['stdout']); usleep(20000); }
    check(str_contains($output, '"ready"'), 'Servidor não ficou pronto: ' . file_get_contents($pipes['stderr']));
    $get = fn(string $path, string $method='GET') => request($port, "$root/ca.crt", "$method $path HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n");
    $response = $get('/dists/trixie/InRelease'); check(status($response) === 200 && str_ends_with($response, "signed-fixture\n"), 'GET autenticado falhou: ' . ($GLOBALS['lastTlsError'] ?? substr($response, 0, 400)) . ' ' . file_get_contents($pipes['stderr'])); $checks++;
    $response = $get('/pool/main/linuxbr-fixture_0.7.0~beta1_amd64.deb');
    check(status($response) === 200 && hash('sha256', explode("\r\n\r\n", $response, 2)[1]) === hash('sha256', $deb), 'Download do pacote foi alterado.'); $checks++;
    $response = $get('/dists/trixie/InRelease', 'HEAD'); check(status($response) === 200 && str_ends_with($response, "\r\n\r\n") && str_contains($response, 'Content-Length: 15'), 'HEAD com corpo ou tamanho incorreto.'); $checks++;
    foreach (['/../private.txt','/%2e%2e/private.txt','/%252e%252e/private.txt','/pool%2fmain/file','/pool%5cmain/file','/private.key','/execute.php','/client-secret.key','/dists/trixie/InRelease?file=private','/dists/trixie/%00Release','/dists//trixie/InRelease','http://localhost/dists/trixie/InRelease'] as $path) {
        $response = $get($path); check(status($response) === 404 && !str_contains($response, 'PRIVATE SENTINEL'), 'Caminho indevido publicado: ' . $path); $checks++;
    }
    foreach (['POST','PUT','DELETE','OPTIONS'] as $method) { check(status($get('/client.sources', $method)) === 405, 'Método indevido aceito.'); $checks++; }
    $response = request($port, "$root/ca.crt", "GET /client.sources HTTP/1.1\r\nHost: localhost\r\nHost: other\r\n\r\n"); check(status($response) === 400, 'Host duplicado aceito.'); $checks++;
    $response = request($port, "$root/ca.crt", "GET /client.sources HTTP/1.1\r\nHost: localhost\r\nTransfer-Encoding: chunked\r\n\r\n"); check(status($response) === 400, 'Corpo chunked aceito.'); $checks++;
    $response = request($port, "$root/ca.crt", "GET /client.sources HTTP/1.1\r\nHost: localhost\r\nAuthorization: Basic Zml4dHVyZQ==\r\n\r\n"); check(status($response) === 400, 'Credencial HTTP indevida aceita.'); $checks++;
    $response = request($port, "$root/ca.crt", "GET /client.sources HTTP/1.1\r\nHost: localhost\r\nX-Long: " . str_repeat('a', 5000) . "\r\n\r\n"); check(status($response) === 431, 'Cabeçalho excessivo aceito.'); $checks++;
    check(request($port, "$root/ca.crt", "GET /client.sources HTTP/1.1\r\nHost: localhost\r\n\r\n", 'wrong.invalid') === '', 'Nome TLS incorreto aceito.'); $checks++;
    mkdir("$root/other", 0700); tlsFixture("$root/other");
    check(request($port, "$root/other/ca.crt", "GET /client.sources HTTP/1.1\r\nHost: localhost\r\n\r\n") === '', 'Autoridade TLS desconhecida aceita.'); $checks++;
    check(!is_file("$root/executed"), 'Conteúdo PHP foi executado.'); $checks++;
    $link = "$public/pool/main/linuxbr-secret_1_all.deb";
    if (@symlink("$root/private.txt", $link)) {
        $symlink = true; $response = $get('/pool/main/linuxbr-secret_1_all.deb');
        check(status($response) === 403 && !str_contains($response, 'PRIVATE SENTINEL'), 'Symlink externo foi publicado.'); $checks++;
    } else check(PHP_OS_FAMILY === 'Windows', 'Não foi possível preparar a verificação de symlink.');
    stop($process, $pipes); $process = null;
    foreach ([array_merge($args, ['--bind','0.0.0.0']), array_merge($args, ['--root',$root])] as $unsafe) {
        $testPipes = []; $test = launch($unsafe, $testPipes); $deadline = microtime(true) + 5;
        while (proc_get_status($test)['running'] && microtime(true) < $deadline) usleep(20000);
        check(!proc_get_status($test)['running'], 'Configuração insegura iniciou o servidor.');
        check(!str_contains(file_get_contents($testPipes['stdout']), '"ready"'), 'Configuração insegura publicada.'); stop($test, $testPipes); $checks++;
    }
    echo json_encode(['status'=>'PASS','checks'=>$checks,'tls_peer_verified'=>true,'tls_host_verified'=>true,
        'symlink_escape_test'=>$symlink ? 'PASS' : 'SKIP Windows sem permissão de symlink', 'php_executed'=>false], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT), "\n";
} catch (Throwable $error) {
    fwrite(STDERR, $error->getMessage() . "\n");
    $failed = true;
} finally {
    if (is_resource($process)) stop($process, $pipes);
    cleanup($root);
}
exit(isset($failed) ? 1 : 0);
