# Role catalog

Pick a role mailbox to implement. Unused roles stay unused. Each one is a separate decision boundary with its own skill file. The default for every role is human approval of every external send.

Load [shared/core/SKILL.md](../shared/core/SKILL.md) with the role skill. Authorization lives in [the default policy](../shared/policies/auto-reply-authorization.example.json), not in the skill text.

Hello is the only role for which an observed deployment described a narrow first-reply exception. That exception is a disabled example in [hello-first-reply.example.json](../shared/policies/hello-first-reply.example.json). Sales, support, and projects had no auto-reply permission in that deployment. The table below is the library default: no automatic external send.

| Role | Example address | Use it for | Default auto-send | Skill |
| --- | --- | --- | --- | --- |
| Sales | `sales@example.com` | New business inquiries, demos, and quote requests. | No | [sales](../Job/sales/SKILL.md) |
| Support | `support@example.com` | Help for people already using an ACME product. | No | [support](../Job/support/SKILL.md) |
| Projects | `projects@example.com` | Status and coordination for an in-flight ACME delivery. | No | [projects](../Job/projects/SKILL.md) |
| Hello | `hello@example.com` | Front door for general ACME mail and first-stop routing. | No | [hello](../Job/hello/SKILL.md) |
| Billing | `billing@example.com` | Customer invoices, charges, receipts, and billing contacts. | No | [billing](../Job/billing/SKILL.md) |
| Recruiting | `recruiting@example.com` | Candidates and applications. | No | [recruiting](../Job/recruiting/SKILL.md) |
| HR | `hr@example.com` | Employee-relations intake. | No | [hr](../Job/hr/SKILL.md) |
| Partnerships | `partnerships@example.com` | Commercial partnership inquiries. | No | [partnerships](../Job/partnerships/SKILL.md) |
| Press | `press@example.com` | Journalists and media requests. | No | [press](../Job/press/SKILL.md) |
| Customer onboarding | `onboarding@example.com` | Kickoff and access checklists for a new ACME customer. | No | [customer-onboarding](../Job/customer-onboarding/SKILL.md) |
| Customer success | `customer-success@example.com` | Adoption and relationship health after go-live. | No | [customer-success](../Job/customer-success/SKILL.md) |
| Security | `security@example.com` | Vulnerability reports and security questions. | No | [security](../Job/security/SKILL.md) |
| Privacy | `privacy@example.com` | Privacy questions and data-subject request intake. | No | [privacy](../Job/privacy/SKILL.md) |
| Legal intake | `legal@example.com` | Notices, counsel, contracts, and legal demands. | No | [legal-intake](../Job/legal-intake/SKILL.md) |
| Finance | `finance@example.com` | Accounts payable, tax forms, and company financial inquiries. | No | [finance](../Job/finance/SKILL.md) |
| Procurement | `procurement@example.com` | Purchase orders and buying from suppliers. | No | [procurement](../Job/procurement/SKILL.md) |
| Operations | `operations@example.com` | Cross-team operational coordination that is not a customer project or a facilities ticket. | No | [operations](../Job/operations/SKILL.md) |
| IT helpdesk | `helpdesk@example.com` | Employee technology support. | No | [it-helpdesk](../Job/it-helpdesk/SKILL.md) |
| Engineering | `engineering@example.com` | Product defects that need an engineering owner. | No | [engineering](../Job/engineering/SKILL.md) |
| Product feedback | `feedback@example.com` | Suggestions and product ideas. | No | [product-feedback](../Job/product-feedback/SKILL.md) |
| Returns | `returns@example.com` | Return merchandise authorization intake. | No | [returns](../Job/returns/SKILL.md) |
| Shipping | `shipping@example.com` | Delivery and address questions. | No | [shipping](../Job/shipping/SKILL.md) |
| Events | `events@example.com` | Questions about ACME events. | No | [events](../Job/events/SKILL.md) |
| Community | `community@example.com` | Community programs and user groups. | No | [community](../Job/community/SKILL.md) |
| Vendor management | `vendors@example.com` | Performance of vendors ACME already uses. | No | [vendor-management](../Job/vendor-management/SKILL.md) |
| Executive office | `office@example.com` | Mail addressed to ACME leadership aliases. | No | [executive-office](../Job/executive-office/SKILL.md) |
| Compliance | `compliance@example.com` | Regulatory questions and audit-evidence intake. | No | [compliance](../Job/compliance/SKILL.md) |
| Quality assurance | `quality@example.com` | Quality escapes and corrective-action intake. | No | [quality-assurance](../Job/quality-assurance/SKILL.md) |
| Documentation | `docs@example.com` | Corrections and requests about ACME docs. | No | [documentation](../Job/documentation/SKILL.md) |
| Training | `training@example.com` | Training questions. Enrollment is a commitment. | No | [training](../Job/training/SKILL.md) |
| Facilities | `facilities@example.com` | Workplaces, badges, and physical access. | No | [facilities](../Job/facilities/SKILL.md) |
| Travel | `travel@example.com` | Itinerary questions. No booking changes. | No | [travel](../Job/travel/SKILL.md) |
| Investor relations | `investors@example.com` | Investor and analyst inquiries. | No | [investor-relations](../Job/investor-relations/SKILL.md) |
| Renewals | `renewals@example.com` | Commercial renewal inquiries. | No | [renewals](../Job/renewals/SKILL.md) |
| Developer relations | `developers@example.com` | External developer audience, APIs, and SDKs. | No | [developer-relations](../Job/developer-relations/SKILL.md) |
| Trust and safety | `trust@example.com` | Abuse and misuse reports. | No | [trust-and-safety](../Job/trust-and-safety/SKILL.md) |
| Accessibility | `accessibility@example.com` | Product and service accessibility requests. | No | [accessibility](../Job/accessibility/SKILL.md) |
| Ethics | `ethics@example.com` | Ethics and whistleblower intake. | No | [ethics](../Job/ethics/SKILL.md) |
| Marketing | `marketing@example.com` | Brand, campaigns, and co-marketing. | No | [marketing](../Job/marketing/SKILL.md) |
| Warranty | `warranty@example.com` | Warranty claim intake. | No | [warranty](../Job/warranty/SKILL.md) |

Addresses are placeholders on `example.com`. Replace them in an operator config that is not committed with real domains unless the domain is a documentation example.

