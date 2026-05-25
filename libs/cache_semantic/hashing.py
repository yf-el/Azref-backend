import hashlib

import numpy as np


def quantize_embedding(vec: np.ndarray, bits: int = 8) -> np.ndarray:
    """L2-normalize then quantize each dim to `bits` buckets in [-1, 1].

    Two embeddings that are semantically close (cosine ≈ 1) will hash to the
    same bucket vector after normalization + quantization, giving us
    approximate-match lookups via exact key equality in Redis.
    """
    v = np.asarray(vec, dtype=np.float32)
    norm = np.linalg.norm(v)
    if norm > 0:
        v = v / norm
    levels = (1 << bits) - 1
    q = np.round((v + 1.0) * 0.5 * levels).astype(np.uint8)
    return q


def hash_key(namespace: str, vec: np.ndarray, bits: int = 8) -> str:
    q = quantize_embedding(vec, bits=bits)
    digest = hashlib.sha256(q.tobytes()).hexdigest()
    return f"cache:{namespace}:{digest}"
