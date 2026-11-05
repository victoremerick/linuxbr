<?php
declare(strict_types=1);
if(PHP_SAPI!=='cli')exit(1);
require __DIR__.'/../src/bootstrap.php';
umask(0077);
$tables=['administrators','applications','audit_log','publications','rate_limits','checks','submissions'];
$operation=$argv[1]??'';$filename=$argv[2]??'';$keyfile=$argv[3]??'';
function protectedPath(string $path):void {
    if(!str_starts_with($path,'/')||str_contains($path,"\0")||preg_match('~/(public_html|htdocs|www|public)/~',$path))throw new RuntimeException('Escolha um caminho privado absoluto.');
    $parent=realpath(dirname($path));
    if($parent===false||is_link($path)||($parent!==dirname($path)))throw new RuntimeException('Caminho privado inválido.');
    if((fileperms($parent)&0077)!==0)throw new RuntimeException('O diretório privado deve ter permissão 0700.');
}
function exclusiveWrite(string $path,string $bytes):void {
    $file=fopen($path,'x');if($file===false)throw new RuntimeException('O arquivo de destino já existe ou não pode ser criado.');
    try{if(fwrite($file,$bytes)!==strlen($bytes)||!fflush($file))throw new RuntimeException('Falha na gravação.');}finally{fclose($file);}
}
try{
    if(!in_array($operation,['create','restore'],true))throw new RuntimeException('Uso: php bin/backup.php create|restore /diretorio-privado/copia.lbr /diretorio-privado/chave');
    protectedPath($filename);protectedPath($keyfile);
    if($operation==='create'&&!file_exists($keyfile))exclusiveWrite($keyfile,random_bytes(SODIUM_CRYPTO_SECRETBOX_KEYBYTES));
    if(!is_file($keyfile)||(fileperms($keyfile)&0077)!==0)throw new RuntimeException('Chave de backup privada inválida.');
    $key=file_get_contents($keyfile);if(strlen($key)!==SODIUM_CRYPTO_SECRETBOX_KEYBYTES)throw new RuntimeException('Tamanho de chave inválido.');
    if($operation==='create'){
        $db->exec('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ');$db->beginTransaction();
        try{
            $snapshot=['schema'=>1,'source_id'=>$config['source_id'],'created_at'=>gmdate(DATE_ATOM),'signing_key'=>trim(file_get_contents($config['secret_key_file'])),'tables'=>[]];
            foreach($tables as $table)$snapshot['tables'][$table]=$db->query('SELECT * FROM `'.$table.'`')->fetchAll();
            $db->commit();
        }catch(Throwable $error){if($db->inTransaction())$db->rollBack();throw $error;}
        $plain=\LinuxBR\Catalog::encode($snapshot);$nonce=random_bytes(SODIUM_CRYPTO_SECRETBOX_NONCEBYTES);
        exclusiveWrite($filename,"LBRBACKUP1\n".$nonce.sodium_crypto_secretbox($plain,$nonce,$key));sodium_memzero($plain);
        echo json_encode(['backup'=>basename($filename),'bytes'=>filesize($filename),'sha256'=>hash_file('sha256',$filename)]),"\n";
    }else{
        if($db->query('SHOW TABLES')->fetchColumn()!==false)throw new RuntimeException('A restauração exige um banco vazio e exclusivo. Nenhuma tabela existente será substituída.');
        if(!is_file($filename)||filesize($filename)>67108864)throw new RuntimeException('Arquivo ausente ou maior que 64 MiB.');
        $raw=file_get_contents($filename);if(!str_starts_with($raw,"LBRBACKUP1\n"))throw new RuntimeException('Formato de backup desconhecido.');
        $offset=strlen("LBRBACKUP1\n");$nonce=substr($raw,$offset,SODIUM_CRYPTO_SECRETBOX_NONCEBYTES);
        $plain=sodium_crypto_secretbox_open(substr($raw,$offset+SODIUM_CRYPTO_SECRETBOX_NONCEBYTES),$nonce,$key);
        if($plain===false)throw new RuntimeException('A cópia foi alterada ou a chave não corresponde.');
        $snapshot=json_decode($plain,true,512,JSON_THROW_ON_ERROR);sodium_memzero($plain);
        if(($snapshot['schema']??null)!==1||($snapshot['source_id']??null)!==$config['source_id']||array_keys($snapshot['tables']??[])!==$tables)throw new RuntimeException('Identidade ou estrutura do backup inválida.');
        $signing=base64_decode($snapshot['signing_key'],true);if($signing===false||strlen($signing)!==SODIUM_CRYPTO_SIGN_SECRETKEYBYTES)throw new RuntimeException('Chave de assinatura inválida.');
        if(file_exists($config['secret_key_file']))throw new RuntimeException('O destino já possui uma chave de assinatura. Use uma instalação vazia.');
        protectedPath($config['secret_key_file']);
        $db->exec(file_get_contents(__DIR__.'/../schema.sql'));$db->beginTransaction();
        try{
            foreach($tables as $table){
                $columns=$db->query('SHOW COLUMNS FROM `'.$table.'`')->fetchAll(PDO::FETCH_COLUMN);
                foreach($snapshot['tables'][$table] as $row){
                    if(array_diff(array_keys($row),$columns)||array_diff($columns,array_keys($row)))throw new RuntimeException('Colunas divergentes na tabela '.$table);
                    $statement=$db->prepare('INSERT INTO `'.$table.'` (`'.implode('`,`',$columns).'`) VALUES ('.implode(',',array_fill(0,count($columns),'?')).')');
                    $statement->execute(array_map(fn($column)=>$row[$column],$columns));
                }
            }
            exclusiveWrite($config['secret_key_file'],base64_encode($signing));$db->commit();
        }catch(Throwable $error){if($db->inTransaction())$db->rollBack();throw $error;}
        if(!is_dir($config['session_path']))mkdir($config['session_path'],0700,true);
        sodium_memzero($signing);echo "Banco e chave restaurados em destino vazio. Sessões administrativas antigas não foram importadas.\n";
    }
    sodium_memzero($key);
}catch(Throwable $error){fwrite(STDERR,$error->getMessage()."\n");exit(1);}
