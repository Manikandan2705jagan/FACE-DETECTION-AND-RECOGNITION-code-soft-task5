# Model Licensing

The JARVAS **source code** is MIT-licensed (`LICENSE`). **Pretrained model weights are separate
artifacts with their own licenses** and are *not* covered by the MIT license. Read this before any
commercial deployment.

---

## 1. InsightFace pretrained models

JARVAS optionally uses [InsightFace](https://github.com/deepinsight/insightface) models such as the
`buffalo_sc` pack (SCRFD face detection + ArcFace recognition).

- InsightFace's **code** is MIT-licensed.
- However, the **pretrained model weights** published by InsightFace are released for
  **non-commercial research purposes only**, unless you obtain a separate commercial license from the
  authors. This is stated in the InsightFace repository and model zoo.

**Implication:** Using the default InsightFace pretrained weights in a commercial product requires
you to secure an appropriate license or substitute compliant weights (see below). The MIT license of
JARVAS does **not** grant any rights to these weights.

---

## 2. Compliance options

Choose one and document it in your deployment:

1. **Obtain a commercial license** from the model authors (DeepInsight / InsightFace) and keep proof
   of license on file.
2. **Use weights you trained yourself** on a dataset you have the rights to use.
3. **Use a model with a permissive license** (e.g. weights released under Apache-2.0 or CC-BY that
   permit commercial use) — verify the exact terms on the model card.
4. **Assessment/non-commercial use only** — keep the deployment non-commercial and comply with the
   research license.

---

## 3. Datasets

Training or fine-tuning requires datasets whose licenses permit your intended use. Many popular face
datasets (e.g. MS1M, VGGFace2, and web-scraped corpora) have research-only or unclear terms, and some
carry legal/privacy risk around consent for the depicted individuals. Prefer datasets with explicit,
documented consent and commercial-use terms.

---

## 4. Runtime dependency licenses (informative)

| Component | License | Notes |
|-----------|---------|-------|
| FastAPI, Starlette, Pydantic | MIT / BSD | permissive |
| SQLAlchemy | MIT | permissive |
| ONNX Runtime | MIT | permissive |
| OpenCV (`opencv-python-headless`) | Apache-2.0 | permissive |
| Pillow | HPND | permissive |
| NumPy | BSD-3-Clause | permissive |
| `cryptography` | Apache-2.0 / BSD | permissive |
| Celery, Redis client | BSD | permissive |
| Next.js, React | MIT | permissive |
| Tailwind CSS | MIT | permissive |
| Radix UI | MIT | permissive |

This table is a convenience summary, not legal advice. Verify current license text for every
dependency before shipping.

---

## 5. JARVAS obligations

- JARVAS does **not** bundle model weights; you supply them.
- `/health` and `/admin/models` report `is_mock` so you can confirm whether real weights (and thus
  their licenses) are in use.
- If weights are absent, the deterministic **mock engine** is used and no third-party model license
  applies to that runtime.

> **Not legal advice.** Licensing is fact- and jurisdiction-specific. Consult qualified counsel before
> commercial deployment.
