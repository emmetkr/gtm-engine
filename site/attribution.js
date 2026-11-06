/* Inbound attribution for your website. One file, no dependencies.
 *
 * Paste it into every page (or load it with <script src="/attribution.js" defer>). It does three
 * things, and the inbound receiver (ops/receivers/api/inbound-CHANGE-ME.js) depends on all three:
 *
 *   1. FIRST TOUCH. On the first landing, store the UTMs, ad click ids, the referring site and the
 *      landing page in a 90-day first-party cookie. A visitor who arrives from a tagged link and
 *      books two weeks later still carries the source. Without this, most bookings arrive
 *      "untagged".
 *   2. CALENDLY HANDOFF. Append those params to every Calendly link and embed, so Calendly's
 *      invitee.created webhook carries them in `tracking` (the booking receiver reads them).
 *   3. FORM FIELDS. window.gtmAttribution.hubspotFields() returns hidden fields for the HubSpot
 *      Forms API: inbound_utm_*, inbound_referrer, inbound_landing_page, inbound_form_page and,
 *      if PostHog is on the page, posthog_distinct_id (the Slack card links to that visitor).
 *
 * Set OWN_DOMAIN below. Create the inbound_* contact properties first (ops/receivers/INBOUND.md).
 *
 * Consent: this sets one first-party cookie that holds campaign parameters, no personal data.
 * Check your own consent rules. If you gate it behind a banner, run it on Accept.
 */
(function () {
  'use strict';
  var OWN_DOMAIN = 'example.com';   // CHANGE ME: your site's domain, so internal clicks are not "referrals"
  var COOKIE = 'gtm_attr';
  var KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'gclid', 'li_fat_id', 'fbclid'];

  // 1. First touch. Never overwritten once set: the first source is the one that earned the lead.
  try {
    if (!new RegExp('(^|;\\s*)' + COOKIE + '=').test(document.cookie)) {
      var q = new URLSearchParams(location.search), parts = [];
      KEYS.forEach(function (k) { var v = q.get(k); if (v) parts.push(k + '=' + encodeURIComponent(v)); });
      // Store the bare hostname. The receiver adds a scheme before parsing it (a scheme-less
      // hostname once made every LinkedIn visitor read as "Direct").
      var ref = ''; try { ref = new URL(document.referrer).hostname; } catch (e) {}
      if (ref && ref.slice(-OWN_DOMAIN.length) !== OWN_DOMAIN) parts.push('ref=' + encodeURIComponent(ref));
      parts.push('land=' + encodeURIComponent(location.pathname));
      document.cookie = COOKIE + '=' + encodeURIComponent(parts.join('&')) + ';path=/;max-age=7776000;samesite=lax';
    }
  } catch (e) {}

  function stored() {
    var m = document.cookie.match(new RegExp('(?:^|;\\s*)' + COOKIE + '=([^;]+)'));
    return new URLSearchParams(m ? decodeURIComponent(m[1]) : '');
  }
  // UTMs only (Calendly ignores the rest). This page's own query string wins over the cookie on a
  // first visit, before the cookie exists.
  function utmQuery() {
    var here = new URLSearchParams(location.search), c = stored(), parts = [];
    KEYS.forEach(function (k) { var v = here.get(k) || c.get(k); if (v) parts.push(k + '=' + encodeURIComponent(v)); });
    return parts.join('&');
  }
  function withAttr(url) {
    var extra = utmQuery();
    return extra ? url + (url.indexOf('?') < 0 ? '?' : '&') + extra : url;
  }

  // 2. Calendly handoff: links, inline iframes, and the Calendly widget's data-url.
  function patchCalendly() {
    document.querySelectorAll('a[href*="calendly.com/"]:not([data-attr])').forEach(function (a) {
      a.href = withAttr(a.href); a.setAttribute('data-attr', '1');
    });
    document.querySelectorAll('iframe[src*="calendly.com/"]:not([data-attr])').forEach(function (f) {
      // Calendly embeds need embed_domain to be the host actually serving the page, or they
      // render blank on preview and staging domains.
      var src = f.src.indexOf('embed_domain=') < 0 ? f.src + (f.src.indexOf('?') < 0 ? '?' : '&') + 'embed_domain=' + encodeURIComponent(location.hostname) : f.src;
      f.src = withAttr(src); f.setAttribute('data-attr', '1');
    });
    document.querySelectorAll('.calendly-inline-widget[data-url]:not([data-attr])').forEach(function (w) {
      w.setAttribute('data-url', withAttr(w.getAttribute('data-url'))); w.setAttribute('data-attr', '1');
    });
  }
  if (document.readyState !== 'loading') patchCalendly(); else document.addEventListener('DOMContentLoaded', patchCalendly);

  // 3. Hidden fields for the HubSpot Forms API (api.hsforms.com/submissions/v3/integration/submit).
  function hubspotFields() {
    try {
      var here = new URLSearchParams(location.search), c = stored();
      var g = function (k) { return (here.get(k) || c.get(k) || '').slice(0, 250); };
      var ph = ''; try { ph = (window.posthog && posthog.get_distinct_id && posthog.get_distinct_id()) || ''; } catch (e) {}
      return [
        // An untagged arrival says so out loud instead of leaving a blank nobody notices.
        { objectTypeId: '0-1', name: 'inbound_utm_source', value: g('utm_source') || '(none: untagged link or direct)' },
        { objectTypeId: '0-1', name: 'inbound_utm_medium', value: g('utm_medium') },
        { objectTypeId: '0-1', name: 'inbound_utm_campaign', value: g('utm_campaign') },
        { objectTypeId: '0-1', name: 'inbound_utm_content', value: g('utm_content') },
        { objectTypeId: '0-1', name: 'inbound_form_page', value: (location.origin + location.pathname).slice(0, 250) },
        { objectTypeId: '0-1', name: 'inbound_referrer', value: c.get('ref') || '' },
        { objectTypeId: '0-1', name: 'inbound_landing_page', value: c.get('land') || location.pathname },
        { objectTypeId: '0-1', name: 'posthog_distinct_id', value: ph }
      ];
    } catch (e) { return []; }
  }

  window.gtmAttribution = { hubspotFields: hubspotFields, withAttr: withAttr, utmQuery: utmQuery, patchCalendly: patchCalendly };
})();

/* Example: a custom form posting to HubSpot with the attribution attached.
 *
 *   fetch('https://api.hsforms.com/submissions/v3/integration/submit/' + PORTAL_ID + '/' + FORM_GUID, {
 *     method: 'POST', headers: { 'Content-Type': 'application/json' }, keepalive: true,
 *     body: JSON.stringify({
 *       fields: [
 *         { objectTypeId: '0-1', name: 'email', value: email },
 *         { objectTypeId: '0-1', name: 'firstname', value: first },
 *         { objectTypeId: '0-1', name: 'lastname', value: last },
 *       ].concat(window.gtmAttribution.hubspotFields()),
 *       context: { pageUri: location.href, pageName: document.title }
 *     })
 *   });
 *
 * Every inbound_* field must exist as a contact property AND be added to the form in HubSpot,
 * or the Forms API rejects the whole submission.
 */
