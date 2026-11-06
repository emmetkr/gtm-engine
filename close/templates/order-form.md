<!--
Order Form template, for founders who do not yet have one from a lawyer.

EVERY CLAUSE MARKED [[LAWYER: ...]] IS A PLACEHOLDER. Have your lawyer write it. The generator
refuses to build a sendable order form while any [[LAWYER marker is left in this file (it will
build a preview into clients/<slug>/close/preview/ with --preview, which is never sent).

Better: once a lawyer has given you an Order Form in Word, put {{placeholders}} into its order
table only and pass it with --order-form-base. The generator then fills those cells and leaves
every other word of the lawyer's document exactly as it was. See close/CLOSE.md §3.

Figures: the {{fees_table}} block is built from commercial.md (or the client's custom offer).
Never type a figure here.
-->
**{{seller.company_name}}**

# Order Form

| Field | Detail |
|---|---|
| Customer | {{client.legal_name}} |
| Customer address | {{client.address}} |
| Customer contact | {{contact.name}}, {{contact.title}}, {{contact.email}} |
| Provider | {{seller.legal_name}} |
| Order Form date | {{date_long}} |
| Subscription start | {{start_date_long}} |
| Subscription term | {{term_months}} months |

## Fees

{{fees_table}}

**Payment terms.** {{payment_terms}}

## Service

[[LAWYER: Describe the service being sold, in the words of your product reference. State only capabilities that product-context lists as live.]]

## Term and renewal

[[LAWYER: Initial term, renewal mechanism, notice period for non-renewal.]]

## Agreement

[[LAWYER: Which terms and conditions govern this Order Form (your MSA or online terms), and how a conflict between the two is resolved.]]

## Signatures

| | {{seller.legal_name}} | {{client.legal_name}} |
|---|---|---|
| Signature | | |
| Name | {{seller.signer_name}} | {{signer.name}} |
| Title | {{seller.signer_title}} | {{signer.title}} |
| Date | | |
