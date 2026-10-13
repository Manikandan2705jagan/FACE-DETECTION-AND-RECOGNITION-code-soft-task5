# Calibration

Recognition in JARVAS is **advisory**. It answers "which *consented* enrolled identities are
*similar* to this face?" — never "who is this person?". This document explains how the similarity
threshold behaves and how to calibrate it responsibly.

---

## 1. How matching works

1. The probe face is encoded to a 512-d ArcFace embedding.
2. The embedding is compared (exact **cosine similarity**) against the tenant's active, consented
   embeddings.
3. Every candidate with `similarity >= threshold` is returned with `status="candidate"` and
   `manual_review_required=true`. Below threshold, `status="no_match"` with **no identity attached**.

The score is a similarity, **not** a probability of identity. It must never be presented as one.

---

## 2. Threshold trade-offs

Lower threshold → more candidates (higher recall, more false positives).
Higher threshold → fewer candidates (higher precision, more false negatives).

| Threshold | Behaviour | Typical use |
|-----------|-----------|-------------|
| 0.30–0.35 | Very permissive; many false candidates | Only as a coarse "possible" filter for a human |
| 0.38–0.45 | **Default band** (`DEFAULT_SIMILARITY_THRESHOLD`, e.g. 0.40) | Candidate generation with review |
| 0.50–0.60 | Conservative; high precision | Small, high-quality galleries |
| > 0.60 | Very strict; may miss true matches | Only where false positives are unacceptable |

### Important: no auto-decisions

Even at high thresholds, JARVAS never auto-accepts a match. Anything with a legal, financial, or
access-control consequence **must** be confirmed by a human through a separate, accountable process.
Thresholds only order the review queue.

---

## 3. Factors that change the score distribution

- **Image quality** — blur, low light, and off-angle faces lower similarity. The pipeline's quality
  gate (`FaceDetection.quality`) filters most of these before enrollment.
- **Age / appearance drift** — templates age; re-enroll with fresh data periodically.
- **Number of enrolled identities** — larger galleries increase the chance a random face exceeds the
  threshold. A threshold that is fine for 50 identities may be unsafe for 50,000.
- **Demographic variance** — accuracy is not uniform across all populations. Measure it on data
  representative of your users, not on a generic benchmark.

---

## 4. Recommended calibration procedure

1. **Assemble a representative probe set** with ground-truth labels. Include true matches
   (same person, different image) and impostor pairs (different people). Include your real cameras,
   lighting, and demographics.
2. **Sweep the threshold** from e.g. 0.20 to 0.70 and compute FAR (false accept rate) and FRR
   (false reject rate) at each point.
3. **Pick an operating point** that satisfies your policy — e.g. cap FAR at an acceptable level for
   your review capacity, then accept the resulting FRR.
4. **Set `DEFAULT_SIMILARITY_THRESHOLD`** to that value and let callers override per request only
   within a documented range.
5. **Re-measure** after any model, gallery, camera, or population change and at least periodically.

---

## 5. Metrics to track

| Metric | Definition | Use |
|--------|------------|-----|
| FAR | impostor pairs above threshold / all impostor pairs | False-alarm risk |
| FRR | genuine pairs below threshold / all genuine pairs | Missed-match risk |
| TAR@FAR | true accept rate at a fixed FAR | Standard comparison point |
| Candidates/review | candidates surfaced per review | Operator workload |
| Confirm rate | reviews confirmed true / reviews performed | Real-world precision |

---

## 6. Detection-only tuning (no threshold)

For pure detection, tune instead for:

- **`min_confidence`** — detector score cutoff (higher → fewer, more reliable boxes).
- **`MIN_FACE_SIZE_PX`** — ignore tiny/far faces.
- **Quality gate** — `blur` / `lighting` / `pose` / `face_size_px` thresholds in
  `services/quality.py` and the video frame sampler (`sample_fps`).

---

## 7. Governance

- Document the chosen threshold, the calibration dataset, and the measured FAR/FRR.
- Keep `manual_review_required` intact — it is a hard invariant of the product, not a setting.
- Revisit thresholds whenever the model, weights, gallery size, or user population changes.
