<?php
declare(strict_types=1);
require_once __DIR__.'/Catalog.php';
$configPath = getenv('LINUXBR_CATALOG_CONFIG') ?: dirname(__DIR__).'/private/config.php';
if (!is_file($configPath)) throw new RuntimeException('Configuração privada não encontrada.');
$config = require $configPath;
$db = new PDO($config['dsn'], $config['db_user'], $config['db_password'], [
    PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,
    PDO::ATTR_EMULATE_PREPARES=>false,
]);
$catalog = new \LinuxBR\Catalog($db,$config);
