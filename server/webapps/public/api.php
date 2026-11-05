<?php
declare(strict_types=1);
use LinuxBR\Catalog;
header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');
header('Referrer-Policy: no-referrer');
header("Content-Security-Policy: default-src 'none'; frame-ancestors 'none'");

function reply(mixed $value, int $status=200): never {
    http_response_code($status);echo Catalog::encode($value);exit;
}
function rate(PDO $db, string $key, int $maximum, int $seconds): void {
    $bucket=hash('sha256',$key);$now=time();
    $db->beginTransaction();
    try {
        $s=$db->prepare('INSERT IGNORE INTO rate_limits(bucket,attempts,until_time) VALUES(?,0,?)');$s->execute([$bucket,$now+$seconds]);
        $s=$db->prepare('SELECT * FROM rate_limits WHERE bucket=? FOR UPDATE');$s->execute([$bucket]);$row=$s->fetch();
        $count=(int)$row['until_time']<$now?0:(int)$row['attempts'];
        $until=(int)$row['until_time']<$now?$now+$seconds:(int)$row['until_time'];
        if ($count >= $maximum) {$db->rollBack();throw new RuntimeException('Muitas tentativas. Aguarde antes de tentar novamente.',429);}
        $s=$db->prepare('UPDATE rate_limits SET attempts=?,until_time=? WHERE bucket=?');$s->execute([$count+1,$until,$bucket]);$db->commit();
    } catch (Throwable $e) {if($db->inTransaction())$db->rollBack();throw $e;}
}
try {
    require __DIR__.'/../src/bootstrap.php';
    $secure=($_SERVER['HTTPS'] ?? '')==='on';
    if (!$secure && (($config['require_https'] ?? true) || !in_array($_SERVER['REMOTE_ADDR'] ?? '',['127.0.0.1','::1'],true))) throw new RuntimeException('HTTPS obrigatório.',403);
    $action=$_GET['action'] ?? 'catalog';$method=$_SERVER['REQUEST_METHOD'];
    if ($method==='GET' && in_array($action,['catalog','discovery','search'],true)) {
        if ($action==='discovery') {
            $key=base64_decode(trim(file_get_contents($config['secret_key_file'])),true);
            $public=sodium_crypto_sign_publickey_from_secretkey($key);sodium_memzero($key);
            reply(['schema'=>1,'source_id'=>$config['source_id'],'name'=>$config['source_name'],
                'catalog_url'=>rtrim($config['public_url'],'/').'/api.php?action=catalog',
                'public_key'=>base64_encode($public),'fingerprint'=>hash('sha256',$public)]);
        }
        $envelope=$catalog->envelope();
        if ($action==='catalog') reply($envelope);
        $payload=json_decode(base64_decode($envelope['payload'],true),true,512,JSON_THROW_ON_ERROR);
        $query=strtolower(substr((string)($_GET['q'] ?? ''),0,120));$category=(string)($_GET['category'] ?? '');
        $rows=array_values(array_filter($payload['apps'],fn($r)=>$r['status']==='published' && (!$category || $r['category']===$category) && (!$query || str_contains(strtolower($r['name'].' '.$r['description']),$query))));
        $page=max(1,min(1000,(int)($_GET['page'] ?? 1)));
        reply(['revision'=>$payload['revision'],'total'=>count($rows),'page'=>$page,'apps'=>array_slice($rows,($page-1)*30,30)]);
    }
    if (!is_dir($config['session_path'])) throw new RuntimeException('Armazenamento de sessões indisponível.',503);
    session_save_path($config['session_path']);ini_set('session.use_strict_mode','1');
    session_name('linuxbr_catalog');session_set_cookie_params(['secure'=>$secure,'httponly'=>true,'samesite'=>'Strict','path'=>'/']);session_start();
    if (isset($_SESSION['last_seen']) && time()-(int)$_SESSION['last_seen']>1800) {$_SESSION=[];session_regenerate_id(true);}
    $_SESSION['last_seen']=time();$_SESSION['csrf'] ??= bin2hex(random_bytes(32));
    if ($method==='GET' && $action==='session') reply(['csrf'=>$_SESSION['csrf'],'user'=>$_SESSION['user'] ?? null,'role'=>$_SESSION['role'] ?? null]);
    if ($method==='POST') {
        if (!hash_equals($_SESSION['csrf'],$_SERVER['HTTP_X_CSRF_TOKEN'] ?? '')) throw new RuntimeException('Sessão expirada. Atualize a página.',403);
        if (isset($_SERVER['HTTP_ORIGIN']) && rtrim($_SERVER['HTTP_ORIGIN'],'/')!==rtrim($config['public_url'],'/')) throw new RuntimeException('Origem não autorizada.',403);
        if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0)>65536) throw new InvalidArgumentException('Pedido muito grande.');
        $raw=file_get_contents('php://input',false,null,0,65537);
        if (strlen($raw)>65536) throw new InvalidArgumentException('Pedido muito grande.');
        $input=json_decode($raw,true,64,JSON_THROW_ON_ERROR);
        if (!is_array($input)) throw new InvalidArgumentException('Pedido inválido.');
        if ($action==='login') {
            rate($db,'login:'.($_SERVER['REMOTE_ADDR'] ?? ''),10,900);
            $username=$input['username'] ?? '';$password=$input['password'] ?? '';
            if (!is_string($username)||!is_string($password)||strlen($username)>120||strlen($password)>1024) throw new InvalidArgumentException('Credenciais inválidas.');
            $s=$db->prepare('SELECT * FROM administrators WHERE username=?');$s->execute([$username]);$user=$s->fetch();
            if (!$user || !password_verify($password,$user['password_hash'])) throw new RuntimeException('Usuário ou senha incorretos.',401);
            session_regenerate_id(true);$_SESSION['user']=$user['username'];$_SESSION['role']=$user['role'];$_SESSION['csrf']=bin2hex(random_bytes(32));
            $catalog->audit($user['username'],'login','panel');reply(['user'=>$user['username'],'role'=>$user['role'],'csrf'=>$_SESSION['csrf']]);
        }
        if ($action==='suggest') {
            rate($db,'suggest:'.($_SERVER['REMOTE_ADDR'] ?? ''),5,3600);
            $document=Catalog::document($input);
            $s=$db->prepare('INSERT INTO submissions(document) VALUES(?)');$s->execute([Catalog::encode($document)]);reply(['message'=>'Sugestão enviada para revisão.'],201);
        }
    }
    if (!isset($_SESSION['user'])) throw new RuntimeException('Entre para administrar o catálogo.',401);
    if ($method==='GET') {
        if ($action==='applications') reply(['apps'=>$catalog->rows()]);
        if ($action==='audit') reply(['events'=>$db->query('SELECT * FROM audit_log ORDER BY id DESC LIMIT 200')->fetchAll()]);
        if ($action==='checks') reply(['checks'=>$db->query('SELECT * FROM checks ORDER BY checked_at DESC LIMIT 1000')->fetchAll()]);
        if ($action==='submissions') reply(['submissions'=>$db->query('SELECT * FROM submissions ORDER BY id DESC LIMIT 200')->fetchAll()]);
    }
    if ($method==='POST') {
        if ($action==='logout') {$_SESSION=[];session_regenerate_id(true);reply(['ok'=>true]);}
        if ($action==='check') {
            rate($db,'check:'.$_SESSION['user'],20,3600);
            require __DIR__.'/../src/Verifier.php';
            reply(\LinuxBR\Verifier::store($catalog,Catalog::identifier($input['id'] ?? '')));
        }
        if ($action==='save') {
            $status=$input['status'] ?? 'draft';
            if ($status!=='draft' && $_SESSION['role']!=='admin') throw new RuntimeException('Somente administradores podem publicar ou desativar.',403);
            $expected=$input['expected_revision'] ?? 0;
            if (!is_int($expected)||$expected<0) throw new InvalidArgumentException('Revisão inválida.');
            reply($catalog->save($input['document'] ?? [],$expected,$status,$_SESSION['user']));
        }
        if ($action==='publish') {
            if ($_SESSION['role']!=='admin') throw new RuntimeException('Permissão insuficiente.',403);
            reply($catalog->publish($_SESSION['user']));
        }
        if ($action==='review-submission') {
            if ($_SESSION['role']!=='admin') throw new RuntimeException('Permissão insuficiente.',403);
            if (!in_array($input['state'] ?? '',['accepted','rejected'],true)) throw new InvalidArgumentException('Decisão inválida.');
            $s=$db->prepare('UPDATE submissions SET state=? WHERE id=? AND state=?');$s->execute([$input['state'],(int)($input['id'] ?? 0),'pending']);
            $catalog->audit($_SESSION['user'],'submission-'.$input['state'],(string)($input['id'] ?? 0));reply(['updated'=>$s->rowCount()]);
        }
    }
    reply(['error'=>'Operação não encontrada.'],404);
} catch (Throwable $e) {
    $status=$e instanceof InvalidArgumentException || $e instanceof JsonException ? 400 : (in_array($e->getCode(),[401,403,409,429,503],true)?$e->getCode():500);
    http_response_code($status);
    echo json_encode(['error'=>$status===500?'Falha no servidor. Consulte o registro administrativo.':$e->getMessage()],JSON_UNESCAPED_UNICODE);
    if($status===500)error_log('Linux BR catálogo: '.get_class($e));
}
