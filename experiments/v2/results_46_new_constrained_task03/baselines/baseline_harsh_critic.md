# AI Tool Usage Policy

**Version:** 3.4
**Effective Date:** [YYYY-MM-DD — Policy Owner must populate before publication]
**Next Review Date:** [YYYY-MM-DD — 12 months from Effective Date — Policy Owner must populate before publication]
**Policy Owner:** Legal
**Operational Sponsor:** Engineering Leadership
**Applies To:** All Employees, Contractors, and Temporary Workers
**Questions / Approvals / Exception Requests / Violation Reports:** ai-policy@[company].com
*(Monitored by Legal; target response: 2 business days for general questions; 10 business days for complete tool approval requests, where the clock starts only upon receipt of a complete request as defined in Section 6.2; see Section 7 for violation reporting timelines)*

---

> **Pre-Publication Checklist — Policy Owner Action Required Before Distribution**
>
> The following items must be completed before this document is published or distributed. Do not distribute this document while any item remains unchecked.
>
> - [ ] Populate Effective Date and Next Review Date in the header block.
> - [ ] Replace every instance of `[Company]` throughout with the correct legal entity name.
> - [ ] Replace every instance of `[INTERNAL LINK — Policy Owner must populate before publication]` with the correct internal URL.
> - [ ] Replace `[privacy-officer email — Policy Owner must populate before publication]` in Section 7.2 with the correct address.
> - [ ] Replace `[whistleblower hotline number/URL — Policy Owner must populate before publication]` in Section 7.1 with the correct contact information.
> - [ ] Replace `[HR contact — Policy Owner must populate before publication]` in Section 8.2 with the correct name or title.
> - [ ] Replace `[governing law jurisdiction — Policy Owner must populate before publication]` in Section 12 with the correct jurisdiction.
> - [ ] Confirm the Approved Tools List is current and accessible at the linked location.
> - [ ] Confirm the IP Checklist is current and accessible at the linked location.
> - [ ] Confirm the Tool Request Form is current and accessible at the linked location.
> - [ ] Distribute to all covered persons and record acknowledgment per Section 10.

---

## Table of Contents

1. Purpose
2. Scope
3. Definitions
4. Approved Tools
5. Rules for All AI Tool Use
   - 5.1 Prohibition: Customer Data in AI Tools
   - 5.2 External Communications: Review Standard
   - 5.3 AI-Generated Code: Comment Requirement
   - 5.4 AI-Generated Code: License Review Before Commit
   - 5.5 Circumvention of IT-Disabled AI Features
   - 5.6 Customer-Facing Demos and Prototypes
6. Requesting Approval for a New AI Tool
7. Reporting Violations
   - 7.1 Obligation to Report
   - 7.2 Data Breach or Privacy Incident
   - 7.3 Non-Retaliation
   - 7.4 Timelines
8. Enforcement
   - 8.1 Consequences
   - 8.2 Process
9. Exception Requests
10. Acknowledgment and Training
11. Revision History
12. Governing Law and Severability

---

## 1. Purpose

This policy establishes binding rules for the use of artificial intelligence tools at [Company]. Its objectives are to protect Customer Data, manage intellectual property risk, and maintain compliance with applicable law and [Company]'s contractual obligations.

This policy applies to every employee, contractor, and temporary worker acting on behalf of [Company], regardless of role or seniority.

---

## 2. Scope

**2.1 Covered activities.** This policy governs all use of AI Tools—including code assistants, text generators, image generators, and chat interfaces—by any person within the scope defined in Section 1.

**2.2 Covered devices and services.** This policy applies regardless of whether the AI Tool is accessed on a company-owned device or a personal device, and regardless of whether the tool is company-licensed or personally subscribed.

**2.3 Supersession.** This policy supersedes all prior guidance—formal or informal—on AI tool use at [Company], including any prior written policies, team-level practices, and informal guidance. Where this policy conflicts with any prior guidance or practice, this policy controls.

---

## 3. Definitions

**AI Tool:** Any software product that uses machine learning or large language model technology to generate, complete, summarize, translate, or otherwise produce text, code, images, or other content.

**Approved AI Tool:** An AI Tool that has completed Legal's vendor review—including Data Processing Agreement review and IP risk assessment—and appears on the Approved Tools List maintained at [INTERNAL LINK — Policy Owner must populate before publication].

**Approved Tools List:** The authoritative, current list of Approved AI Tools maintained at [INTERNAL LINK — Policy Owner must populate before publication]. A tool not appearing on that list is not approved for any use under this policy. The list specifies, for each tool, the approved functions, approved use cases, and categories of data that may be submitted.

**Customer Data:** Any information that identifies or could reasonably identify a customer or their end users, including personally identifiable information, financial records, usage data, database schemas, API keys, and any data whose handling is governed by a customer contract or Data Processing Agreement.

**External Communication:** Any written content transmitted outside [Company]'s internal systems, including email, proposals, marketing copy, support ticket responses, and partner correspondence.

**IP Checklist:** The intellectual property review checklist maintained by Legal at [INTERNAL LINK — Policy Owner must populate before publication], used to submit code for Legal review prior to commit under Section 5.4.

**Tool Request Form:** The standardized intake form maintained by Legal at [INTERNAL LINK — Policy Owner must populate before publication], used to submit requests for approval of a new AI Tool under Section 6. Use of the Tool Request Form is required; requests submitted by email without using the form are not complete requests for purposes of Section 6.2.

**Vendor-DPA-Covered Tool:** An Approved AI Tool operated by a third-party vendor under a current, executed Data Processing Agreement that has been reviewed and approved by Legal, where that DPA expressly governs the vendor's handling of data submitted through the tool and covers the specific data type and use case in question.

---

## 4. Approved Tools

**4.1 Engineering — GitHub Copilot Business.** GitHub Copilot Business is approved for code completion, generation, and review within approved repositories. Eighty licensed seats are available; Engineering leadership manages seat allocation. An engineer who does not hold an assigned seat may not use Copilot. An engineer without a seat who needs AI coding assistance must either request a seat from Engineering leadership or submit a request for an alternative tool under Section 6 before any use begins.

**4.2 All Functions — Drafting Assistance.** Employees in any function may use Approved AI Tools to produce internal drafts, outlines, and summaries. The current list of approved drafting tools for non-engineering functions is maintained on the Approved Tools List at [INTERNAL LINK — Policy Owner must populate before publication]. That list is the authoritative reference; this document does not duplicate it. AI-generated content used in any External Communication must satisfy the requirements in Section 5.2.

**4.3 Authoritative reference.** The Approved Tools List at [INTERNAL LINK — Policy Owner must populate before publication] controls. If a tool does not appear on that list, it is not approved for any purpose under this policy. In the event of any conflict between a description in this document and the Approved Tools List, the Approved Tools List controls.

---

## 5. Rules for All AI Tool Use

### 5.1 Prohibition: Customer Data in AI Tools

**Rule.** No employee, contractor, or temporary worker may input Customer Data into any AI Tool, including an Approved AI Tool, unless all three of the following conditions are satisfied:

**(a)** the tool is a Vendor-DPA-Covered Tool;

**(b)** the specific data type to be submitted is within the scope of the applicable Data Processing Agreement; and

**(c)** Legal has confirmed in writing that conditions (a) and (b) are satisfied for that tool and data type.

This prohibition applies to all data fields and all forms of Customer Data, including test data, anonymized exports that retain structural identifiers, and database schemas. Satisfying conditions (a) and (b) without written Legal confirmation under condition (c) does not authorize submission.

**What this means in practice.** Before submitting any data to an AI Tool, ask: could this data identify a customer or their end users, or is it governed by a customer contract? If yes, do not submit it unless Legal has confirmed in writing that the specific tool and data type are covered by a current Data Processing Agreement. If you are unsure, contact ai-policy@[company].com before proceeding.

*Why this rule exists:* An engineer inputted a customer database schema into an external AI service. Outside counsel assessed this as a likely violation of existing Data Processing Agreement terms. [Company]'s SOC 2 Type II certification, GDPR obligations, and pending FedRAMP authorization each impose data handling controls that this rule enforces.

---

### 5.2 External Communications: Review Standard

**Rule.** AI-generated text included in any External Communication must satisfy all three of the following conditions before the communication is sent:

**(a) Full read.** The employee sending the communication must have read the AI-generated content in its entirety.

**(b) Substantive edit and verification.** The employee must have independently verified factual claims and confirmed that the content accurately reflects [Company]'s intended meaning. "Verification" means the employee has a reasonable basis—through their own knowledge or independent checking—for each material factual claim. Content the employee cannot verify must be removed or rewritten in the employee's own words based on verified sources.

**(c) Copyright clearance.** The employee must not include any passage that the employee knows or reasonably suspects reproduces third-party copyrighted material without authorization.

Forwarding, copying, or paraphrasing AI output without satisfying all three conditions is a violation of this policy.

*Why this rule exists:* A sales representative transmitted verbatim competitor-copyrighted marketing copy that had been generated by an AI tool. The review standard above is designed to prevent recurrence.

---

### 5.3 AI-Generated Code: Comment Requirement

**Rule.** All AI-generated or AI-assisted code merged into any branch must include a structured comment in the following format, placed immediately above each discrete AI-generated or AI-assisted function or block:

```
AI-ASSISTED: [Tool name] | Reviewed by: [Author handle] | Date: [YYYY-MM-DD]
```

**Note on syntax.** The comment delimiter must conform to the language in which the code is written—for example, `//` in JavaScript or Java, `#` in Python or shell scripts, `--` in SQL, `/* */` for multi-line blocks in C-family languages, or the appropriate delimiter for any other language. The content between the delimiter and the closing of the comment must follow the format above exactly.

**Scope of the requirement.** This requirement applies to every discrete AI-generated or AI-assisted function or block within a file. A single comment per file does not satisfy this requirement when a file contains multiple AI-generated or AI-assisted sections.

**Definition of "discrete block."** A discrete block is any logically distinct unit of code that was generated or materially completed by an AI Tool. Examples include: a function or method, a class definition, a SQL query, a configuration block, or any contiguous section of logic that was produced or substantially rewritten by an AI Tool. If the AI Tool generated or substantially rewrote more than half of a file's lines, each generated or rewritten section must be commented individually; a single file-level comment does not suffice.

**Auto-generated files.** Where a file is produced entirely by build tooling or a code-generation pipeline that incorporates an AI Tool, a single file-level comment satisfies this requirement, provided the comment identifies the tool and pipeline and the engineer of record reviews and signs off on the file before merge. Engineers must not use this provision to avoid per-block commenting in files they author manually with AI assistance.

*Why this rule exists:* Identifying AI-assisted code at the point of authorship enables Legal and Engineering to trace IP exposure, respond to audit inquiries, and fulfill license review obligations under Section 5.4.

---

### 5.4 AI-Generated Code: License Review Before Commit

**Rule.** Before committing AI-generated code, engineers must submit the code for Legal review using the IP Checklist at [INTERNAL LINK — Policy Owner must populate before publication] if any of the following conditions is true:

**(a)** the code contains a license header or comment referencing any license;

**(b)** the AI tool's license filter flags the code; or

**(c)** the engineer recognizes the code as substantially similar to a known open-source implementation, regardless of whether a license header is present.

Condition (c) addresses the common case in which an AI tool reproduces licensed code without attribution. When in doubt, engineers must submit for review rather than proceed.

**Timeline for Legal review of IP Checklist submissions.** Legal will complete its review of a submitted IP Checklist within 5 business days of receipt of a complete submission. Legal will notify the submitting engineer of the outcome—cleared to commit, cleared with modifications required, or blocked pending further review—in writing. Engineers must not commit the code under review until Legal provides written clearance.

*Why this rule exists:* An intern committed GPL-licensed AI-generated code. Outside counsel separately assessed that AI-generated code may lack independent copyright protection, compounding [Company]'s IP exposure. The review requirement above is designed to catch both problems before code is committed.

---

### 5.5 Circumvention of IT-Disabled AI Features

**Rule.** Employees must not attempt to enable, activate, or use any AI feature that IT has disabled in [Company]'s configuration of any tool. This prohibition applies regardless of whether the feature could be enabled through user-level settings, browser extensions, third-party integrations, or any other means.

IT's current configuration disables AI features within Slack. This configuration is maintained by IT and reviewed quarterly. If a business need arises that requires enabling any currently disabled AI feature in any tool, the request must be submitted under Section 6 before any attempt to enable or use the feature.

*Why this rule exists:* Enabling unreviewed AI features within communication platforms creates data exposure channels inconsistent with [Company]'s current security posture and vendor agreements. IT's configuration decisions reflect assessed risk; circumventing them—even unintentionally—undermines those controls.

---

### 5.6 Customer-Facing Demos and Prototypes

**Rule.** AI Tools must not be used to generate demo content, prototype outputs, or proof-of-concept materials presented to customers or prospects unless:

**(a)** the materials satisfy the review standard in Section 5.2; and

**(b)** the materials contain no Customer Data.

Both conditions must be satisfied. Satisfying one does not excuse the other.

*Why this rule exists:* Demo and prototype materials are External Communications and create the same IP and data exposure risks as other external content. Customer Data submitted to an AI Tool to produce demo output would violate Section 5.1 regardless of the demo context.

---

## 6. Requesting Approval for a New AI Tool

**6.1 Requirement to request before use.** Any employee, contractor, or temporary worker who wants to use an AI Tool not on the Approved Tools List must submit a request to ai-policy@[company].com using the Tool Request Form at [INTERNAL LINK — Policy Owner must populate before publication] before any use begins. Use of an unapproved tool while a request is pending is a violation of this policy. Employees who need temporary access while a Section 6 review is pending must submit a concurrent exception request under Section 9.

**6.2 Required request contents.** A request must be submitted using the Tool Request Form and must include:

- the tool name and vendor;
- the intended use case, described specifically enough for Legal to assess data handling risk;
- the categories of data that would be inputted (do not include actual data in the request);
- the function or team that would use the tool; and
- the business justification.

A request submitted without using the Tool Request Form, or that omits any of the above items, is not a complete request and will not start the 10-business-day review clock. Legal will notify the requester of any missing information within 3 business days of receipt.

**6.3 Review process.** Legal will conduct a vendor review that includes, at minimum: assessment of the vendor's data processing terms; IP risk assessment; and evaluation of the proposed use case against [Company]'s current contractual and regulatory obligations. Legal may request additional information from the requester during the review period; such requests pause the review clock until the information is received.

**6.4 Review timeline.** Legal will complete its review within 10 business days of receipt of a complete request. The clock starts only upon receipt of a complete request as defined in Section 6.2. Legal will notify the requester of the outcome—approval, conditional approval, or denial—in writing.

**6.5 Outcomes.** Legal may approve, conditionally approve, or deny a request. A conditional approval will specify the conditions that must be satisfied before use begins and will remain valid only so long as those conditions are met. A denial will include a brief statement of the basis for denial. Denials may be appealed by resubmitting with additional information addressing the stated basis