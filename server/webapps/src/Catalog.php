<?php
declare(strict_types=1);
namespace LinuxBR;

final class Catalog {
    public function __construct(public readonly \PDO $db, public readonly array $config) {}

    public static function encode(mixed $data): string {
        return json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
    }

    public static function identifier(mixed $id): string {
        if (!is_string($id) || !preg_match('/\A[a-z0-9][a-z0-9._-]{0,79}\z/', $id)) {
            throw new \InvalidArgumentException('Identificador inválido.');
        }
        return $id;
    }

    public static function url(mixed $url): string {
        if (!is_string($url) || strlen($url) > 2048 || preg_match('/[\x00-\x20\x7f\\\\]/', $url)) {
            throw new \InvalidArgumentException('Endereço inválido.');
        }
        $p = parse_url($url);
        if (!$p || ($p['scheme'] ?? '') !== 'https' || isset($p['user']) || isset($p['pass']) ||
            isset($p['fragment']) || (($p['port'] ?? 443) !== 443) ||
            !preg_match('/\A(?=.{1,253}\z)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\z/i', $p['host'] ?? '') ||
            !str_contains($p['host'], '.') || filter_var($p['host'], FILTER_VALIDATE_IP)) {
            throw new \InvalidArgumentException('Use um domínio público HTTPS, sem credenciais ou fragmentos.');
        }
        foreach (explode('.', $p['host']) as $label) {
            if (!$label || strlen($label) > 63 || str_starts_with($label, '-') || str_ends_with($label, '-')) {
                throw new \InvalidArgumentException('Domínio inválido.');
            }
        }
        if (preg_match('/\.(local|localhost|internal|test|invalid)\z/i', $p['host'])) {
            throw new \InvalidArgumentException('Use um domínio público.');
        }
        return $url;
    }

    public static function document(array $input): array {
        $out = ['id' => self::identifier($input['id'] ?? null)];
        foreach (['name'=>120,'description'=>2000,'category'=>80,'changelog'=>4000] as $field=>$limit) {
            $value = $input[$field] ?? '';
            if (!is_string($value) || strlen($value) > $limit || preg_match('/[\x00-\x08\x0b\x0c\x0e-\x1f]/', $value) ||
                ($field !== 'changelog' && trim($value) === '')) throw new \InvalidArgumentException('Campo inválido: '.$field);
            $out[$field] = trim($value);
        }
        foreach (['url','source','favicon'] as $field) $out[$field] = self::url($input[$field] ?? '');
        $out['host'] = strtolower(parse_url($out['url'], PHP_URL_HOST));
        if (parse_url($out['url'], PHP_URL_QUERY) !== null) throw new \InvalidArgumentException('A página inicial não pode conter parâmetros de sessão.');
        $out['linux_available'] = $input['linux_available'] ?? 'unknown';
        if (!in_array($out['linux_available'], ['yes','no','unknown'], true)) throw new \InvalidArgumentException('Disponibilidade inválida.');
        $out['screenshots'] = $input['screenshots'] ?? [];
        if (!is_array($out['screenshots']) || !array_is_list($out['screenshots']) || count($out['screenshots']) > 8) throw new \InvalidArgumentException('Capturas inválidas.');
        foreach ($out['screenshots'] as $url) self::url($url);
        $out['upstream_version'] = $input['upstream_version'] ?? null;
        $out['upstream_release_url'] = $input['upstream_release_url'] ?? null;
        if ($out['upstream_version'] !== null) {
            if (!is_string($out['upstream_version']) || strlen($out['upstream_version']) > 80 || trim($out['upstream_version']) === '') throw new \InvalidArgumentException('Versão inválida.');
            self::url($out['upstream_release_url']);
        } else $out['upstream_release_url'] = null;
        $out['kind'] = 'web';
        return $out;
    }

    public function audit(string $actor, string $action, string $subject): void {
        $s = $this->db->prepare('INSERT INTO audit_log(actor,action,subject) VALUES(?,?,?)');
        $s->execute([$actor,$action,$subject]);
    }

    public function save(array $input, int $expected, string $status, string $actor): array {
        $document = self::document($input);
        if (!in_array($status, ['draft','published','disabled'], true)) throw new \InvalidArgumentException('Estado inválido.');
        $this->db->beginTransaction();
        try {
            $s = $this->db->prepare('SELECT revision FROM applications WHERE id=? FOR UPDATE');$s->execute([$document['id']]);
            $old = $s->fetchColumn();
            if (($old === false ? 0 : (int)$old) !== $expected) throw new \RuntimeException('O registro mudou. Atualize antes de salvar.', 409);
            $revision = $expected + 1;
            if ($old === false) {
                $s = $this->db->prepare('INSERT INTO applications(id,revision,status,document) VALUES(?,?,?,?)');
                $s->execute([$document['id'],$revision,$status,self::encode($document)]);
            } else {
                $s = $this->db->prepare('UPDATE applications SET revision=?,status=?,document=? WHERE id=?');
                $s->execute([$revision,$status,self::encode($document),$document['id']]);
            }
            $this->audit($actor,'save-'.$status,$document['id']);$this->db->commit();
            return ['id'=>$document['id'],'revision'=>$revision];
        } catch (\Throwable $e) {$this->db->rollBack();throw $e;}
    }

    public function rows(): array {
        return array_map(function($row) {
            return array_merge(json_decode($row['document'],true,512,JSON_THROW_ON_ERROR),
                ['revision'=>(int)$row['revision'],'status'=>$row['status'],'updated_at'=>$row['updated_at']]);
        }, $this->db->query('SELECT * FROM applications ORDER BY id')->fetchAll());
    }

    public function publish(string $actor): array {
        $key = base64_decode(trim(file_get_contents($this->config['secret_key_file'])), true);
        if ($key === false || strlen($key) !== SODIUM_CRYPTO_SIGN_SECRETKEYBYTES) throw new \RuntimeException('Chave de assinatura inválida.');
        // A transação mantém a revisão pública e o catálogo assinado consistentes.
        $this->db->beginTransaction();
        try {
            $this->db->exec('INSERT INTO publications(envelope) VALUES(NULL)');
            $revision = (int)$this->db->lastInsertId();
            $rows = array_values(array_filter($this->rows(), fn($row)=>$row['status'] !== 'draft'));
            if (count($rows) > 1000) throw new \RuntimeException('Limite de 1.000 aplicativos por fonte excedido.');
            $payload = self::encode(['schema'=>1,'source_id'=>$this->config['source_id'],'revision'=>$revision,
                'issued_at'=>gmdate('Y-m-d\TH:i:s\Z'),'expires_at'=>gmdate('Y-m-d\TH:i:s\Z',time()+7*86400), 'apps'=>$rows]);
            if (strlen($payload) > 2097152) throw new \RuntimeException('Catálogo maior que 2 MiB.');
            $public = sodium_crypto_sign_publickey_from_secretkey($key);
            $envelope = ['algorithm'=>'ed25519','key_id'=>hash('sha256',$public),'payload'=>base64_encode($payload),
                'signature'=>base64_encode(sodium_crypto_sign_detached($payload,$key))];
            $s=$this->db->prepare('UPDATE publications SET envelope=? WHERE revision=?');$s->execute([self::encode($envelope),$revision]);
            $this->audit($actor,'publish',(string)$revision);$this->db->commit();sodium_memzero($key);
            return ['revision'=>$revision,'apps'=>count($rows)];
        } catch (\Throwable $e) {$this->db->rollBack();sodium_memzero($key);throw $e;}
    }

    public function envelope(): array {
        $value=$this->db->query('SELECT envelope FROM publications WHERE envelope IS NOT NULL ORDER BY revision DESC LIMIT 1')->fetchColumn();
        if (!$value) throw new \RuntimeException('O catálogo ainda não foi publicado.',503);
        return json_decode($value,true,512,JSON_THROW_ON_ERROR);
    }
}
