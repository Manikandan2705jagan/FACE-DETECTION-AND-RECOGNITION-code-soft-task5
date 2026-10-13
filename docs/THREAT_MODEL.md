# Threat Model

A pragmatic security & privacy threat model for JARVAS. It names the assets, the trust boundaries,
the threats we design against, the mitigations present in code, and the risks that remain.

---

## 1. Assets

| Asset | Where it lives | Sensitivity |
|-------|----------------|-------------|
| Face embeddings (biometric templates) | `enrollments.embedding_ciphertext` (Fernet) | **Critical** |
| Uploaded media (images/videos) | Object storage (S3/MinIO) or `data/storage` in dev | High |
| Consent records & evidence hashes | `consent_records` | High |
| Identity metadata (names, notes) | `identities` | High |
| Credentials (password hashes) | `users.hashed_password` (bcrypt) | High |
| JWTs & signing secret | client storage / `JWT_SECRET` | High |
| Audit trail | `audit_logs` | Medium |
| Annotated results | object storage | Medium |

---

## 2. Trust boundaries

1. **Browser ⇄ API** — untrusted network; TLS expected in production.
2. **API ⇄ database** — trusted network; contains encrypted + metadata rows.
3. **API/worker ⇄ object storage** — trusted network; contains media and reports.
4. **API/worker ⇄ model runtime** — in-process ONNX; weights are third-party artifacts.
5. **Tenant ⇄ tenant** — hard isolation boundary enforced at the query layer.

---

## 3. Threats, mitigations, residuals

### T1 — Unauthorized recognition / identity inference
- **Mitigation:** Recognition requires `operator` role and `RECOGNITION_ENABLED=true`. It searches
  only the caller's tenant and only identities with **active, unexpired, non-revoked** consent.
  Results are candidates (`manual_review_required=true`), never confirmed identities.
- **Residual:** An operator with a legitimate image can still generate candidates. Authorization is
  role-based, not use-case-based; deploy only where operators are accountable.

### T2 — Enrollment without consent
- **Mitigation:** `enroll_identity()` refuses to create an enrollment without an active consent row
  (`ConsentError`). Consent is purpose-bound, expiring, and carries an evidence hash.
- **Residual:** The system cannot verify that consent was *genuinely* given; the consent checkbox is
  an attestation by the operator. Process controls are required.

### T3 — Biometric template exfiltration
- **Mitigation:** Embeddings are Fernet-encrypted before storage. Plaintext templates are never
  written to the DB, index, logs, or object store. Keys come from `BIOMETRIC_ENCRYPTION_KEY`.
- **Residual:** Whoever holds the encryption key *and* DB access can decrypt. Rotate the key and
  restrict access; consider a KMS/HSM in production.

### T4 — Cross-tenant access (IDOR)
- **Mitigation:** Every tenant-scoped row has `tenant_id`; all reads filter by the caller's tenant.
  Cross-tenant lookups return **404** (no existence leak). Covered by `test_tenant_isolation.py`.
- **Residual:** A code path that forgets the tenant filter would regress isolation. Tests and code
  review are the control.

### T5 — Privilege escalation / role abuse
- **Mitigation:** Roles are a strict hierarchy (viewer < auditor < operator < admin). Admin-only
  endpoints use `require_role(admin)`. Users cannot deactivate themselves or escalate via token
  claims (role is re-read from the DB user object). Role changes are audited.
- **Residual:** A compromised admin account is high impact — enforce MFA at the IdP.

### T6 — Credential attacks (brute force, stuffing)
- **Mitigation:** Passwords hashed with bcrypt; login failures return a generic message; every login
  is audited. JWT expiry is configurable (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- **Residual:** No built-in rate limiting/lockout in the app. Add rate limiting at the edge
  (nginx/API gateway) and enforce strong passwords.
- **Note:** bcrypt truncates inputs beyond 72 bytes; the code caps password length accordingly.

### T7 — Sensitive data in media (EXIF/GPS)
- **Mitigation:** Uploads are decoded and re-encoded, **stripping EXIF** (GPS, device, timestamps)
  before storage. `exif_stripped=true` is recorded on the media row. Covered by `test_exif.py`.
- **Residual:** Visual content itself may still be sensitive; retention and access controls apply.

### T8 — Malicious uploads (RCE / decompression bombs / parser exploits)
- **Mitigation:** Strict content-type allow-lists, size limits, and full decode via Pillow/OpenCV
  (rejects corrupt or oversized images). Files are never executed; filenames are not used as paths.
- **Residual:** Image/video parsers remain a large attack surface — keep Pillow/OpenCV updated and
  run the worker with least privilege.

### T9 — Timing / existence oracles
- **Mitigation:** Cross-tenant and missing resources return 404 uniformly; below-threshold
  recognition returns `no_match` **with no identity attached**.
- **Residual:** Login timing could differ for unknown vs. wrong-password users; acceptable but can be
  hardened with constant-time dummy hashing.

### T10 — Repudiation
- **Mitigation:** Append-only audit trail for auth, enrollment, consent changes, recognition,
  deletion, admin actions, and retention sweeps (actor, action, resource, outcome, IP, detail).
- **Residual:** The audit table is append-only by application convention only. Ship it to
  write-once storage / a SIEM for tamper resistance.

### T11 — Data retention & the right to be forgotten
- **Mitigation:** Consent expiry and retention dates drive a retention sweep that purges expired
  biometrics and evaluates media. Deletion (`purge_identity`) is irreversible and audited; consent
  revocation immediately marks templates `revoked` (excluded from search).
- **Residual:** Backups may retain deleted data until their own expiry — document backup retention.

### T12 — Model supply chain
- **Mitigation:** Models are optional; `model_info()` exposes `is_mock`/`provider` so operators know
  what is running. Weights are not fetched at runtime by default.
- **Residual:** Downloaded weights are third-party binaries with their own licenses and trust
  assumptions — verify checksums/signatures and read `MODEL_LICENSING.md`.

### T13 — Denial of service (large media / expensive jobs)
- **Mitigation:** Upload size caps (`MAX_UPLOAD_MB`, `VIDEO_MAX_UPLOAD_MB`), video duration cap, and
  frame-sampling controls bound work. Video runs in a background worker.
- **Residual:** CPU inference is expensive; autoscale workers and cap concurrent jobs.

---

## 4. Explicitly out of scope (misuse we refuse to enable)

JARVAS provides **no** endpoints or features for:

- Live/real-time video surveillance or persistent tracking.
- Public-face search, scraping, or bulk ingestion of third-party faces.
- Emotion, age, gender, ethnicity, or other demographic inference.
- Law-enforcement, immigration, or "watchlist" workflows.
- Covert or non-consensual identification.

These are absent by design, not merely disabled by configuration. Any fork adding them is outside the
scope of this threat model and this project's stated purpose.

---

## 5. Reporting

Security or privacy issues should be reported privately to the maintainers. Include steps to
reproduce and the affected version.
