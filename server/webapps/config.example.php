<?php
declare(strict_types=1);
// Copie para ../private/config.php, fora da raiz pública, e restrinja as permissões.
return [
    'dsn' => 'mysql:host=localhost;dbname=linuxbr_catalog;charset=utf8mb4',
    'db_user' => 'linuxbr_catalog',
    'db_password' => '',
    'public_url' => 'https://catalogo.example.com',
    'source_id' => 'linuxbr-official',
    'source_name' => 'Catálogo Linux BR',
    'secret_key_file' => __DIR__ . '/signing.key',
    'require_https' => true,
    'session_path' => __DIR__ . '/sessions',
];
