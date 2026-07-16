"""
Shared anatomical orientation for the HCM beat-video pipeline.

PCA IS BANNED here (it failed: the heart + atria + great vessels is too globular,
so its max-variance axis is not the apex-base axis). Orientation is anatomical,
from the elemTags, and is shared by the renderer and the cross-section extractor
so their world frames agree exactly.

World axes returned (rows of R): X=right, Y=anterior, Z=up (apex points down).
"""
import numpy as np


def tag_vertices(faces, face_tags, tg):
    return np.unique(faces[face_tags == tg])


def compute_orientation(P, faces, face_tags, valve_tags=(7, 8, 9, 10), lv_endo_tag=25):
    """P: (N,3) surface points of the reference frame (raw units).
    valve_tags = (mitral, tricuspid, aortic, pulmonary). Returns dict with
    R (3x3 rows=world X,Y,Z), center gc, apex, base, and the up/anterior axes."""
    mitral, tricuspid, aortic, pulmonary = valve_tags
    valve_bary = {v: P[tag_vertices(faces, face_tags, v)].mean(0) for v in valve_tags}
    M = valve_bary[mitral]
    B = np.mean(list(valve_bary.values()), axis=0)           # valve-plane centroid (base)
    lv_endo = P[tag_vertices(faces, face_tags, lv_endo_tag)]
    apex = lv_endo[np.linalg.norm(lv_endo - M, axis=1).argmax()]   # farthest LV-endo pt from mitral
    U = B - apex; U /= np.linalg.norm(U)                     # up: apex down
    A = valve_bary[pulmonary] - B                            # anterior ~ pulmonary valve side
    A = A - np.dot(A, U) * U; A /= np.linalg.norm(A)
    ex = np.cross(A, U); ex /= np.linalg.norm(ex)
    ey = np.cross(U, ex)                                     # = anterior (world +Y)
    R = np.array([ex, ey, U])
    return dict(R=R, gc=P.mean(0), apex=apex, base=B, up=U, anterior=ey,
                valve_bary=valve_bary, valve_tags=valve_tags, lv_endo_tag=lv_endo_tag)
