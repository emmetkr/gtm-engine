<!--
Summary of Terms template. One page, plain, reads like contract paperwork.
Filled by close/make-close-docs.py. Every {{field}} comes from the deal file, seller.json,
commercial.md or the client's custom-offer.md. Never type a figure into this file: the
{{terms_table}} block is built by the script from canon, and a figure written here would
bypass that.
Edit the wording freely. Keep the shape: header line, who it is for, one table, footer.
-->
**{{seller.company_name}} | {{seller.product_line}}**

# Summary of Terms

Prepared for **{{client.legal_name}}**, {{date_long}}

{{terms_table}}

**Contacts.** {{client.display_name}}: {{contact.name}}, {{contact.title}}. {{seller.company_name}}: {{seller.signer_name}}, {{seller.signer_title}}.

**Next step.** On your approval we send the Order Form for signature. Work starts on {{start_date_long}}.

---

*Summary for discussion purposes only. Final terms are set by the {{seller.company_name}} Order Form and Agreement. Confidential.*
