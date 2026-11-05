<?php
declare(strict_types=1);
if (PHP_SAPI!=='cli') exit(1);
require __DIR__.'/../src/bootstrap.php';
$db->exec(file_get_contents(__DIR__.'/../schema.sql'));
if (!is_dir($config['session_path'])) mkdir($config['session_path'],0700,true);
if (!is_file($config['secret_key_file'])) {
    $pair=sodium_crypto_sign_keypair();$secret=sodium_crypto_sign_secretkey($pair);
    $f=fopen($config['secret_key_file'],'x');chmod($config['secret_key_file'],0600);fwrite($f,base64_encode($secret));fclose($f);sodium_memzero($secret);
}
// As credenciais chegam pela entrada padrão, nunca por argumentos de processo.
$raw=stream_get_contents(STDIN,8193);
if (strlen($raw)>8192) throw new RuntimeException('Entrada muito grande.');
$input=json_decode($raw,true,32,JSON_THROW_ON_ERROR);
if (!preg_match('/\A[a-zA-Z0-9_.@-]{3,120}\z/',$input['username'] ?? '') || strlen($input['password'] ?? '')<14) throw new RuntimeException('Use um nome válido e uma senha com pelo menos 14 caracteres.');
$s=$db->prepare('INSERT INTO administrators(username,password_hash,role) VALUES(?,?,?)');
$s->execute([$input['username'],password_hash($input['password'],PASSWORD_DEFAULT),'admin']);
echo "Banco inicializado e administrador criado.\n";
