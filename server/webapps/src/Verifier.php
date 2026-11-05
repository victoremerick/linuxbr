<?php
declare(strict_types=1);
namespace LinuxBR;

final class Verifier {
    public static function publicAddresses(string $host): array {
        $records=dns_get_record($host,DNS_A | DNS_AAAA);
        if (!$records) throw new \RuntimeException('Não foi possível resolver o domínio.');
        $addresses=[];
        foreach ($records as $record) {
            $ip=$record['ip'] ?? $record['ipv6'] ?? null;
            if (!$ip) continue;
            if (!filter_var($ip,FILTER_VALIDATE_IP,FILTER_FLAG_GLOBAL_RANGE)) throw new \RuntimeException('O domínio aponta para uma rede não pública.');
            $addresses[]=$ip;
        }
        if (!$addresses) throw new \RuntimeException('Domínio sem endereço público.');
        return array_unique($addresses);
    }

    public static function check(string $url): array {
        Catalog::url($url);$host=parse_url($url,PHP_URL_HOST);
        $ip=self::publicAddresses($host)[0];$address=str_contains($ip,':')?'['.$ip.']':$ip;
        $body='';$headers='';$curl=curl_init($url);
        curl_setopt_array($curl,[CURLOPT_RESOLVE=>[$host.':443:'.$address],CURLOPT_FOLLOWLOCATION=>false,
            CURLOPT_CONNECTTIMEOUT=>5,CURLOPT_TIMEOUT=>12,CURLOPT_PROTOCOLS=>CURLPROTO_HTTPS,
            CURLOPT_SSL_VERIFYPEER=>true,CURLOPT_SSL_VERIFYHOST=>2,CURLOPT_PROXY=>'',
            CURLOPT_USERAGENT=>'LinuxBR-Catalog/1',
            CURLOPT_WRITEFUNCTION=>function($handle,$chunk)use(&$body){if(strlen($body)+strlen($chunk)>262144)return 0;$body.=$chunk;return strlen($chunk);},
            CURLOPT_HEADERFUNCTION=>function($handle,$chunk)use(&$headers){if(strlen($headers)+strlen($chunk)>16384)return 0;$headers.=$chunk;return strlen($chunk);}]);
        $ok=curl_exec($curl);$code=curl_getinfo($curl,CURLINFO_RESPONSE_CODE);$redirect=curl_getinfo($curl,CURLINFO_REDIRECT_URL);$error=curl_errno($curl);curl_close($curl);
        $result=['url'=>$url,'http_status'=>$code,'checked_at'=>gmdate('Y-m-d\TH:i:s\Z'),
            'available'=>$code>=200 && $code<400,'complete'=>$ok!==false,'review_required'=>false];
        if ($redirect) {$result['redirect_url']=$redirect;$result['review_required']=true;}
        if ($ok!==false) $result['content_sha256']=hash('sha256',$body);
        if ($error) $result['transport_error']=$error;
        return $result;
    }

    public static function store(Catalog $catalog, string $id): array {
        Catalog::identifier($id);$s=$catalog->db->prepare('SELECT document FROM applications WHERE id=?');$s->execute([$id]);$raw=$s->fetchColumn();
        if (!$raw) throw new \InvalidArgumentException('Aplicativo não encontrado.');
        $document=json_decode($raw,true,512,JSON_THROW_ON_ERROR);
        $result=self::check($document['url']);
        $s=$catalog->db->prepare('SELECT result FROM checks WHERE app_id=?');$s->execute([$id]);$old=$s->fetchColumn();
        if ($old) {
            $old=json_decode($old,true,512,JSON_THROW_ON_ERROR);
            if (isset($old['content_sha256'],$result['content_sha256']) && $old['content_sha256']!==$result['content_sha256']) $result['review_required']=true;
        }
        $s=$catalog->db->prepare('INSERT INTO checks(app_id,result) VALUES(?,?) ON DUPLICATE KEY UPDATE result=VALUES(result),checked_at=CURRENT_TIMESTAMP');
        $s->execute([$id,Catalog::encode($result)]);return $result;
    }
}
