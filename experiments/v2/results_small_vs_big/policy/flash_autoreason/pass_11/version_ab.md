**MEMORANDUM**

**TO**: All Employees
**FROM**: [CEO Name], CEO
**DATE**: October 26, 2023
**SUBJECT**: Policy on the Use of Artificial Intelligence (AI) Tools

This policy outlines the acceptable and prohibited uses of AI tools within the company. Its purpose is to enable productivity gains while mitigating security, legal, and compliance risks associated with AI technology, particularly concerning customer Personally Identifiable Information (PII) and Intellectual Property (IP) based on legal review from outside counsel (Base Fact: Legal review).

**1. Scope**

This policy applies to all employees, contractors, and other individuals working on behalf of the company when used in connection with company business.

1.  AI coding assistants (e.g., tools that suggest code completions or generate code snippets).
2.  AI writing and communication tools used for generating drafts of written content.

**2. Permitted Uses**

The following uses of AI tools are permitted, subject to the restrictions outlined in Section 3:

1.  Use of GitHub Copilot Business subject to license availability (Base Fact: Already licensed). If all 80 licenses are in use, employees must relinquish their license when not in use, or wait until one becomes available.

**3. Prohibited Uses**

The following uses of AI tools are strictly prohibited:

1.  Inputting any customer PII, financial data, or database schemas into any AI tool (Base Fact: Handles customer PII and financial data, GDPR obligations, Incident #1). This includes both real and synthetic PII.
2.  Using AI tools to generate content that infringes upon the intellectual property rights of others, including copyrighted text or verbatim use of a competitor's marketing copy (Base Fact: Incident #2, Incident #3, Legal review).
3.  Using AI tools to generate code licensed under a copyleft license (Base Fact: Incident #3, Legal Review).
4.  Using AI features within company Slack (Base Fact: Slack AI Features Disabled).
5.  Using any AI tool other than GitHub Copilot Business for code generation without express written permission from the Director of Engineering.
6.  Incorporating AI-generated code into the codebase without a review by an engineer with at least two years of experience at the company. The review must confirm that the code does not include verbatim content from another source and that the license is compatible with our existing codebase (Base Fact: Incident #3, Legal Review).

**4. Enforcement**

Violations of this policy may result in disciplinary action, up to and including termination of employment or contract.

1.  Engineering managers will ensure that code review processes include a check to confirm that the code does not include verbatim content from another source and that the license is compatible with our existing codebase *before* code is committed. Any concerns should be escalated to the Legal Department.
2.  Sales managers will review AI-assisted email drafts for potential copyright issues by comparing the output to competitor marketing materials as part of existing sales process reviews.
3.  The Security Team will investigate any data exfiltration alerts involving customer PII, utilizing existing intrusion detection systems.
4.  Employees are required to report any suspected violations of this policy to their manager or the Security Team.
5.  Non-compliance will result in a warning for the first offense unless the violation involves the exposure of customer PII or financial data. Repeated violations or severe violations, such as inputting customer PII into an unapproved AI tool after previous warnings, will result in restriction of access to specific company code repositories, sales tools, and network resources relevant to the violation, pending investigation not to exceed one week unless otherwise directed by Legal. Human Resources, in conjunction with the Legal Department and the relevant department head, will determine the appropriate disciplinary action based on the severity and frequency of the violation, as well as the employee's history with the company.
