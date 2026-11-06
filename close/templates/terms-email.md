<!--
The terms-send email. Filled by close/make-close-docs.py into
clients/<slug>/close/<date>-<slug>-email.txt and .html, which the agent passes to the Gmail
connector as body and htmlBody. A person reads it and sends it.

Keep a closing email short: thanks, the attachment, one ask. A long email at the close gives
the buyer things to react to instead of a document to sign. Prices live in the attachment,
never in the body. Replace this wording with your own from a real sent email.

Lines starting "Subject:" set the subject. Everything after the first blank line is the body.
The signature block comes from seller.json and is appended to the body, because drafts made
through the Gmail connector carry no signature.
-->
Subject: {{seller.company_name}} | Summary of Terms for {{client.display_name}}

Hi {{contact.first_name}},

Thanks for the time. Attached is the Summary of Terms we discussed.

If it looks right, tell me who handles signature and vendor onboarding on your side and I will send the Order Form today.
