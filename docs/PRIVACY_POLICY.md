# Privacy Policy (Template)

> **Template — not legal advice.** This is a starting point for a deployment-specific policy. Adapt
> it to your jurisdiction (GDPR, UK DPA, CCPA/CPRA, BIPA, state biometric laws, etc.) and have it
> reviewed by qualified counsel before use.

JARVAS is built so that **face detection is the default** and **recognition is optional, consented,
and advisory**. This document describes what the software does with personal data by design; the
operator deploying it is the **data controller** and must fill in the specifics.

---

## 1. What we process and why

| Data | Purpose | Lawful basis (example) |
|------|---------|------------------------|
| Uploaded images/videos | Face **detection** (count/locate faces) | Operator's stated basis |
| Face embeddings (biometric templates) | Optional **recognition** of enrolled, consented people | **Explicit consent** |
| Identity name + notes | Human-readable label for an enrollment | Explicit consent |
| Consent records | Prove consent; enforce purpose/expiry/retention | Legal obligation / consent |
| Audit logs | Security, accountability, abuse prevention | Legitimate interest / legal obligation |
| Account data (email, hash) | Authentication and access control | Contract / legitimate interest |

We do **not** infer emotion, age, gender, ethnicity, or health, and we do **not** perform
surveillance, tracking, or public-face search. No such features exist in the product.

---

## 2. Consent is the gate for biometrics

- A face is **never enrolled** without an explicit, purpose-bound consent record
  (`consent_granted = true`, a written purpose, an expiry date, and a retention date). The API
  rejects enrollment otherwise.
- Consent is **revocable** at any time. Revocation instantly excludes templates from recognition.
- Consent is **time-limited**: it expires automatically, and retention dates drive scheduled purging.

---

## 3. How biometric templates are protected

- Embeddings are **encrypted at rest** (Fernet/AES) before they are written to the database.
  Plaintext templates are never stored, indexed, or logged.
- Recognition searches only the deploying tenant's **active, consented** templates; a revoked or
  expired template is not a candidate.
- Templates are decrypted in memory only for the moment of comparison.

---

## 4. Data minimisation and hygiene

- Only the data needed for the stated purpose is collected.
- **EXIF is stripped** from every upload (removing GPS, device, and timestamp metadata) before
  storage.
- Detections store a bounding box, confidence, and quality metrics — not identity, unless
  recognition was explicitly invoked.
- Recognition output is **candidates only** and always flagged `manual_review_required`; no automated
  decision is made about any person.

---

## 5. Retention and deletion

- Every consent carries a **retention date** for the biometric template; a scheduled retention sweep
  enforces it and records what it purged.
- Operators can configure **retention policies** per resource type (media, identity, audit, video)
  with actions `delete` or `anonymize`.
- **Deletion is irreversible**: erasing an identity removes the identity, its consent records, and
  its templates. The act is logged (without retaining the deleted biometric).
- Backups, if present, expire under their own schedule — document that schedule.

---

## 6. Your rights (data subjects)

Depending on your jurisdiction, individuals may have the right to:

- **Access / portability** — `GET /gallery/identities/{id}/export` returns the identity, consents,
  and enrollment metadata in a portable JSON form.
- **Erasure** — `DELETE /gallery/identities/{id}` irreversibly removes the individual's data.
- **Withdraw consent** — `PATCH /gallery/identities/{id}/consent {"revoked": true}` disables
  biometric processing immediately.
- **Rectification** — identity names/notes are editable.

Operators should publish a contact channel and response timelines.

---

## 7. Security measures

- Role-based access control (viewer < auditor < operator < admin); recognition requires `operator`.
- Cross-tenant isolation; cross-tenant lookups return 404 to avoid leaking existence.
- Passwords hashed with bcrypt; JWTs with configurable expiry.
- **Append-only audit trail** of authentication, consent, enrollment, recognition, deletion, admin,
  and retention actions.
- Transport encryption (TLS) is expected in production.

See `THREAT_MODEL.md` for the full model and residual risks.

---

## 8. What this software will not do

- No live surveillance, persistent tracking, or re-identification across time/locations.
- No scraping or bulk ingestion of third-party faces.
- No demographic, emotion, or health inference.
- No automated decisions with legal or similarly significant effects.
- No confirmed-identity claims — outputs are advisory candidates for human review.

---

## 9. Operator responsibilities

As the controller, the operator must:

- Establish a lawful basis and, where required, obtain and record **explicit consent**.
- Publish this policy with concrete contact details and jurisdiction-specific disclosures.
- Honour data-subject requests and honour retention limits.
- Configure model licensing appropriately (see `MODEL_LICENSING.md`).
- Conduct a DPIA where required and keep the calibration/audit records described in
  `CALIBRATION.md`.

**Last reviewed:** 2026 — replace with your deployment date.
