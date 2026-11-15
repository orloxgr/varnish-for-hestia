# Basic HTTP/WordPress/WooCommerce policy, also used by UltraCache.
# A public read is not private merely because it is search, REST or AJAX.
sub hvh_common_recv {
    if (req.http.Authorization) {
        set req.http.X-HVH-Pass-Reason = "authorization";
        return (pass);
    }
    if (req.http.Upgrade) {
        set req.http.X-HVH-Pass-Reason = "protocol-upgrade";
        return (pass);
    }
    if (req.method != "GET" && req.method != "HEAD") {
        set req.http.X-HVH-Pass-Reason = "request-method";
        return (pass);
    }
    if (req.url ~ "^/[.]well-known/(acme-challenge|pki-validation)/") {
        set req.http.X-HVH-Pass-Reason = "certificate-validation";
        return (pass);
    }
    if (req.http.X-WP-Nonce || req.http.Cart-Token || req.http.Nonce ||
        req.http.X-WC-Store-API-Nonce ||
        req.url ~ "(?i)[?&](_wpnonce|_ajax_nonce|consumer_key|consumer_secret)=") {
        set req.http.X-HVH-Pass-Reason = "authenticated-request";
        return (pass);
    }
    if (req.url ~ "(?i)^/(wp-admin(?:/|[?]|$)|wp-login[.]php(?:[?]|$)|xmlrpc[.]php(?:[?]|$)|wp-cron[.]php(?:[?]|$)|wp-comments-post[.]php(?:[?]|$))") {
        set req.http.X-HVH-Pass-Reason = "wordpress-private-route";
        return (pass);
    }
    if (req.url ~ "(?i)[?&](preview|preview_id|preview_nonce|customize_changeset_uuid|elementor-preview|et_fb|vc_editable|nocache)=" ||
        req.url ~ "(?i)[?&]context=edit(&|$)") {
        set req.http.X-HVH-Pass-Reason = "wordpress-preview";
        return (pass);
    }
    if (req.url ~ "(?i)^/(cart|checkout|my-account|wc-api)(/|[?]|$)" ||
        req.url ~ "(?i)[?&](add-to-cart|remove_item|undo_item|wc-ajax|wc-api|apply_coupon|remove_coupon|order_again|cancel_order|pay_for_order|download_file)=" ||
        req.url ~ "(?i)[?&]key=wc_order_") {
        set req.http.X-HVH-Pass-Reason = "woocommerce-private-route";
        return (pass);
    }
    # Store API reads can carry cart/notices state even without mutation.
    # Public products and other REST reads retain normal HTTP caching.
    if (req.url ~ "(?i)^/wp-json/(wc/store/v[0-9]+/(cart|checkout|order)|wp/v[0-9]+/(users/me|settings))(/|[?]|$)" ||
        req.url ~ "(?i)[?&]rest_route=(/|%2f)(wc(/|%2f)store(/|%2f)v[0-9]+(/|%2f)(cart|checkout|order)|wp(/|%2f)v[0-9]+(/|%2f)(users(/|%2f)me|settings))(/|%2f|&|$)") {
        set req.http.X-HVH-Pass-Reason = "private-rest-route";
        return (pass);
    }
    call hvh_private_cookie_recv;
    call hvh_cart_cookie_recv;

    # Keep all query values, including ref and campaign attribution, in the
    # request and the cache key. Never erase information needed by the app.
    # Public requests with these parameters are cache candidates, not PASSes.

    # Collapse only grammar-equivalent OWS. Quoted Accept parameters and all
    # media types/quality values (including q=0) retain their original meaning.
    std.collect(req.http.Accept);
    if (req.http.Accept && req.http.Accept !~ {"["]"}) {
        set req.http.Accept = regsuball(req.http.Accept, "[[:blank:]]*,[[:blank:]]*", ",");
        set req.http.Accept = regsuball(req.http.Accept, "[[:blank:]]*;[[:blank:]]*", ";");
        set req.http.Accept = regsuball(req.http.Accept, "^[[:blank:]]+|[[:blank:]]+$", "");
    }
    call hvh_cookie_variation;
}

sub hvh_cookie_variation {
    # The origin still receives the complete Cookie header. Only an explicit
    # Vary: Cookie is keyed by the functional remainder, without analytics IDs.
    # Unknown/consent/referral/language cookies are retained, never whitelisted.
    unset req.http.X-HVH-Vary-Cookie;
    if (req.http.Cookie) {
        set req.http.X-HVH-Vary-Cookie = regsuball(req.http.Cookie, __TRACKING_COOKIES__, "");
        set req.http.X-HVH-Vary-Cookie = regsuball(req.http.X-HVH-Vary-Cookie, "^[;[:blank:]]+|[;[:blank:]]+$", "");
        set req.http.X-HVH-Vary-Cookie = regsuball(req.http.X-HVH-Vary-Cookie, ";[[:blank:]]*", "; ");
        if (req.http.X-HVH-Vary-Cookie == "") { unset req.http.X-HVH-Vary-Cookie; }
    }
}

sub hvh_response_privacy {
    # The reason is stored only on uncacheable decisions; no private body is
    # retained. Mandatory origin privacy cannot be overridden by local TTLs.
    if (beresp.http.Surrogate-Control ~ "(?i)(^|[[:space:],])(no-store|private)([[:space:],=]|$)") {
        set beresp.http.X-HVH-Pass-Reason = "origin-surrogate-control";
        # ESI can consume Surrogate-Control. Preserve its privacy decision for
        # downstream caches as well as this Varnish instance.
        set beresp.http.Cache-Control = "private, no-store";
    } else if (beresp.http.Set-Cookie) {
        set beresp.http.X-HVH-Pass-Reason = "origin-set-cookie";
    } else if (beresp.http.Cache-Control ~ "(?i)(^|[[:space:],])(private|no-cache|no-store)([[:space:],=]|$)" ||
               beresp.http.Pragma ~ "(?i)(^|[[:space:],])no-cache([[:space:],=]|$)") {
        set beresp.http.X-HVH-Pass-Reason = "origin-cache-control";
    } else if (beresp.http.Vary ~ "(^|,)[[:blank:]]*[*][[:blank:]]*(,|$)") {
        set beresp.http.X-HVH-Pass-Reason = "origin-vary-star";
    } else if (beresp.ttl <= 0s) {
        set beresp.http.X-HVH-Pass-Reason = "origin-ttl";
    }
    if (beresp.http.X-HVH-Pass-Reason) { call hvh_mark_uncacheable; }
}

sub hvh_response_variants {
    if (!beresp.uncacheable && beresp.http.Vary ~ "(?i)(^|,)[[:blank:]]*Cookie[[:blank:]]*(,|$)") {
        set beresp.http.Vary = regsuball(beresp.http.Vary,
            "(?i)(^|,)[[:blank:]]*Cookie[[:blank:]]*(?=,|$)", "\1X-HVH-Vary-Cookie");
    }
}
