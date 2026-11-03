# Managed by varnish-for-hestia
# Additional Hestia proxy template. Native templates remain unchanged.
upstream hvh_http_%user%_%domain_idn% {
    server 127.0.0.1:6081;
    server %ip%:%web_port% backup;
}
server {
    listen %ip%:%proxy_port%;
    server_name %domain_idn% %alias_idn%;
    error_log /var/log/%web_system%/domains/%domain%.error.log error;
    include %home%/%user%/conf/web/%domain%/nginx.forcessl.conf*;
    if ($request_method ~ ^(PURGE|BAN)$) { return 405; }
    location ~ /\.(?!well-known\/|file) { deny all; return 404; }
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Port $server_port;
    proxy_set_header Early-Data $rfc_early_data;
    proxy_set_header Connection "";
    proxy_next_upstream error timeout;
    location / {
        proxy_pass http://hvh_http_%user%_%domain_idn%;
        location ~* ^.+\.(%proxy_extensions%)$ {
            try_files $uri @fallback;
            root %docroot%;
            access_log /var/log/%web_system%/domains/%domain%.log combined;
            access_log /var/log/%web_system%/domains/%domain%.bytes bytes;
            expires max;
        }
    }
    location @fallback { proxy_pass http://hvh_http_%user%_%domain_idn%; }
    location /error/ { alias %home%/%user%/web/%domain%/document_errors/; }
    include %home%/%user%/conf/web/%domain%/nginx.conf_*;
}
