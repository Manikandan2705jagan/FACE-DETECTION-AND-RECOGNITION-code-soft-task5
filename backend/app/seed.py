"""Seed the database with SYNTHETIC-ONLY demo data.

No real faces are used or downloaded — every image is drawn procedurally with
Pillow. Safe to run in development; refuses to run in production.
"""
from __future__ import annotations

import io
import random
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import Role
from app.db.session import SessionLocal, init_db
from app.models.identity import ConsentRecord, Identity
from app.models.media import MediaAsset
from app.models.tenant import Tenant
from app.models.user import User
from app.services import enrollment as enrollment_service
from app.services.audit import record as audit_record
from app.services.pipeline import run_image_pipeline
from app.services.storage import get_storage

logger = get_logger(__name__)


def synthetic_face(seed: int, size: int = 512) -> Image.Image:
    """Draw a clearly-synthetic face image (not a real person)."""
    rng = random.Random(seed)
    img = Image.new("RGB", (size, size), (18, 24, 44))
    draw = ImageDraw.Draw(img)

    # Background gradient.
    for y in range(size):
        shade = int(18 + (y / size) * 40)
        draw.line([(0, y), (size, y)], fill=(shade // 2, shade // 2 + 8, shade + 20))

    # Head.
    cx, cy = size // 2, int(size * 0.52)
    rw, rh = int(size * 0.30), int(size * 0.38)
    skin = (232, 190, 160)
    draw.ellipse([cx - rw, cy - rh, cx + rw, cy + rh], fill=skin)

    # Hair.
    draw.ellipse([cx - rw - 6, cy - rh - 30, cx + rw + 6, cy - rh + 90], fill=(40, 30, 28))

    # Eyes.
    eye_dx, eye_y, eye_r = int(rw * 0.55), cy - int(rh * 0.20), max(4, size // 40)
    for sign in (-1, 1):
        ex = cx + sign * eye_dx
        draw.ellipse([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r], fill=(250, 250, 250))
        draw.ellipse([ex - eye_r // 2, eye_y - eye_r // 2, ex + eye_r // 2, eye_y + eye_r // 2], fill=(30, 30, 60))

    # Nose + mouth.
    draw.polygon([(cx, cy), (cx - 8, cy + 22), (cx + 8, cy + 22)], fill=(210, 165, 140))
    draw.arc([cx - 40, cy + 30, cx + 40, cy + 80], start=10, end=170, fill=(150, 60, 60), width=max(3, size // 90))

    # Fine texture so the image has realistic high-frequency detail (and passes
    # the sharpness check the same way a real photo would).
    import numpy as np

    arr = np.asarray(img, dtype=np.int16)
    noise = np.random.RandomState(seed).randint(-14, 15, arr.shape, dtype=np.int16)
    arr = np.clip(arr + noise, 0, 255).astype("uint8")
    img = Image.fromarray(arr, "RGB")

    return img


def _img_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def run_seed(tenant_slug: str = "default") -> dict:
    if settings.is_production:
        raise SystemExit("Refusing to seed production. Set JARVAS_ENV=development.")

    init_db()
    db = SessionLocal()
    created = {"identities": 0, "enrollments": 0, "media": 0}
    try:
        tenant = db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
        if tenant is None:
            tenant = Tenant(name=settings.bootstrap_tenant_name, slug=tenant_slug)
            db.add(tenant)
            db.flush()

        admin = db.query(User).filter(User.tenant_id == tenant.id).first()
        actor_id = admin.id if admin else None
        actor_email = admin.email if admin else "seed@jarvis.local"

        storage = get_storage()
        now = datetime.now(timezone.utc)

        people = [
            ("Synthetic Person Alpha", "Access control pilot group"),
            ("Synthetic Person Beta", "Event check-in demonstration"),
            ("Synthetic Person Gamma", "Lab verification set"),
        ]
        for idx, (name, purpose) in enumerate(people):
            existing = db.query(Identity).filter(
                Identity.tenant_id == tenant.id, Identity.full_name == name
            ).first()
            if existing:
                continue
            identity = Identity(tenant_id=tenant.id, full_name=name, notes="Synthetic demo identity", created_by=actor_id)
            db.add(identity)
            db.flush()

            consent = ConsentRecord(
                tenant_id=tenant.id,
                identity_id=identity.id,
                purpose=purpose,
                granted_by=actor_id,
                expires_at=now + timedelta(days=365),
                retention_until=now + timedelta(days=settings.default_retention_days),
                evidence_hash=enrollment_service.consent_evidence_hash(
                    name, purpose, now + timedelta(days=365), now + timedelta(days=settings.default_retention_days)
                ),
            )
            db.add(consent)
            db.flush()
            created["identities"] += 1

            face = synthetic_face(seed=1000 + idx)
            try:
                enrollment_service.enroll_identity(
                    db, tenant_id=tenant.id, identity=identity, image_rgb=face,
                    user_id=actor_id,
                )
                created["enrollments"] += 1
            except enrollment_service.EnrollmentError as exc:
                logger.warning("Seed enrollment failed for %s: %s", name, exc.message)
        db.commit()

        # A couple of detection-only media samples.
        for idx in range(2):
            face = synthetic_face(seed=2000 + idx)
            media = MediaAsset(
                tenant_id=tenant.id, kind="image", original_filename=f"synthetic-{idx}.jpg",
                content_type="image/jpeg", exif_stripped=True, status="processing",
                width=face.width, height=face.height, created_by=actor_id,
            )
            db.add(media)
            db.flush()
            key = f"uploads/{tenant.id}/{media.id}/original.jpg"
            storage.put(key, _img_bytes(face), "image/jpeg")
            media.storage_key = key
            result = run_image_pipeline(
                db, tenant_id=tenant.id, media=media, image_rgb=face, mode="detection", user_id=actor_id
            )
            rkey = f"results/{tenant.id}/{media.id}/annotated.jpg"
            storage.put(rkey, result.annotated_bytes or b"", "image/jpeg")
            media.result_key = rkey
            db.commit()
            created["media"] += 1

        audit_record(
            db, tenant_id=tenant.id, action="system.seed", actor_user_id=actor_id, actor_email=actor_email,
            detail=created,
        )
        logger.info("Seed complete: %s", created)
        return created
    finally:
        db.close()


if __name__ == "__main__":
    print(run_seed())
