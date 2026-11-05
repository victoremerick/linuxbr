<?php
declare(strict_types=1);
if (PHP_SAPI!=='cli') exit(1);
require __DIR__.'/../src/bootstrap.php';
require __DIR__.'/../src/Verifier.php';
$lock=$db->query("SELECT GET_LOCK('linuxbr_catalog_maintenance',0)")->fetchColumn();
if ((int)$lock!==1) {echo "Já existe uma manutenção em andamento.\n";exit;}
try {
    $rows=$db->query("SELECT a.id FROM applications a LEFT JOIN checks c ON c.app_id=a.id WHERE a.status<>'disabled' ORDER BY c.checked_at ASC LIMIT 3")->fetchAll();
    foreach($rows as $row) {
        try {\LinuxBR\Verifier::store($catalog,$row['id']);echo $row['id'].": verificado\n";}
        catch(Throwable $e) {echo $row['id'].": verificação indisponível\n";}
    }
    $last=$db->query('SELECT UNIX_TIMESTAMP(created_at) FROM publications ORDER BY revision DESC LIMIT 1')->fetchColumn();
    if ($last && time()-(int)$last>86400) {$catalog->publish('maintenance');echo "Assinatura e validade renovadas.\n";}
    $db->exec('DELETE FROM rate_limits WHERE until_time<UNIX_TIMESTAMP()-86400');
} finally {$db->query("SELECT RELEASE_LOCK('linuxbr_catalog_maintenance')");}
