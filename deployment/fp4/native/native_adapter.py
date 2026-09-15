"""Pinned SM120 prefill specialization with original FlashInfer fallback.

This is approximate FP8 query/probability arithmetic, qualified for the selected
EphemerAI model. Decode, unsupported layouts and shapes use the original path.
No prompts, tensor values, logits, or dynamic debug controls are retained.
"""
import ctypes
import math
import os
from pathlib import Path

import torch
import triton
import triton.language as tl

_ROOT = Path(__file__).resolve().parent
_ENABLED = os.environ.get('EPHEMERAI_NATIVE_PREFILL', '1') == '1'
_functions = {}
_capabilities = {}
_counts = {'native_calls': 0, 'native_query_tokens': 0, 'fallback_calls': 0}
_runtime = None

@triton.jit
def zero_tail(K, V, T, L, PS: tl.constexpr, HS: tl.constexpr, TS: tl.constexpr, B: tl.constexpr):
    seq = tl.load(L)
    # A positive host sequence is required by eligibility; this guard also
    # prevents a negative table index if upstream metadata ever becomes invalid.
    page = tl.load(T + tl.maximum(seq - 1, 0) // 64)
    x = tl.program_id(0) * B + tl.arange(0, B)
    head = x // (64 * 256)
    tok = x // 256 % 64
    dim = x % 256
    mask = (seq > 0) & (x < 4 * 64 * 256) & (tok >= ((seq - 1) % 64 + 1))
    offset = page.to(tl.int64) * PS + head * HS + tok * TS + dim
    tl.store(K + offset, 0., mask)
    tl.store(V + offset, 0., mask)

def eligible(wrapper, q, kv, out, q_scale, k_scale, v_scale, kv_cache_sf):
    info = getattr(wrapper, '_ephemerai_native_info', None)
    if not _ENABLED or info is None or not isinstance(kv, tuple) or len(kv) != 2:
        return False
    k, v = kv
    tensors = (q, k, v, out)
    if not all(isinstance(t, torch.Tensor) and t.is_cuda for t in tensors):
        return False
    if any(t.device != q.device for t in tensors):
        return False
    if q.ndim != 3 or q.shape[0] < 64 or tuple(q.shape[1:]) != (24, 256):
        return False
    if out.shape != q.shape or q.dtype != torch.bfloat16 or out.dtype != torch.bfloat16:
        return False
    if not q.is_contiguous() or not out.is_contiguous():
        return False
    if k.ndim != 4 or tuple(k.shape[1:]) != (64, 4, 256) or v.shape != k.shape:
        return False
    if k.dtype != torch.float8_e4m3fn or v.dtype != k.dtype:
        return False
    if k.stride() != (131072, 2048, 512, 1) or v.stride() != k.stride():
        return False
    # Exported ABI interleaves K/V at each head: [page, token, head, K+V].
    if v.data_ptr() - k.data_ptr() != 256:
        return False
    if not wrapper._causal or wrapper._window_left != -1 or wrapper._logits_soft_cap:
        return False
    if q_scale != 1. or kv_cache_sf is not None:
        return False
    if not all(isinstance(s, (float, int)) and math.isfinite(s) and s > 0
               for s in (wrapper._sm_scale, k_scale, v_scale)):
        return False
    table, lengths, qptr, host_seq = info
    if not isinstance(host_seq, int) or not q.shape[0] <= host_seq <= 131072:
        return False
    for t in (table, lengths, qptr):
        if not isinstance(t, torch.Tensor) or t.device != q.device or t.dtype != torch.int32 or not t.is_contiguous():
            return False
    if table.ndim != 2 or table.shape[0] != 1 or table.shape[1] < (host_seq + 63) // 64:
        return False
    if lengths.numel() != 1 or qptr.numel() != 2:
        return False
    if q.device not in _capabilities:
        _capabilities[q.device] = torch.cuda.get_device_capability(q.device)
    return _capabilities[q.device] == (12, 0)

def get_kernel(device):
    global _runtime
    if device not in _functions:
        import cutlass.cute as cute
        if _runtime is None:
            _runtime = ctypes.CDLL(str(_ROOT / 'libcute_dsl_runtime-4.7.1.so'), mode=ctypes.RTLD_GLOBAL)
        module = cute.runtime.load_module(str(_ROOT / 'native-nhd.o'), enable_tvm_ffi=True)
        fn = getattr(module, 'ephemerai_scaled_nhd_h24_k4_d256_page64_q128_k128')
        _functions[device] = (module, fn)
    return _functions[device][1]

def run_prefill(wrapper, q, kv, *, q_scale, k_scale, v_scale, out, kv_cache_sf=None):
    if not eligible(wrapper, q, kv, out, q_scale, k_scale, v_scale, kv_cache_sf):
        _counts['fallback_calls'] += 1
        return wrapper.run(q, kv, q_scale=q_scale, k_scale=k_scale,
                           v_scale=v_scale, out=out, kv_cache_sf=kv_cache_sf)
    import cutlass
    kernel = get_kernel(q.device)
    table, lengths, qptr, _ = wrapper._ephemerai_native_info
    k, v = (t.permute(0, 2, 1, 3) for t in kv)
    zero_tail[(64,)](k, v, table, lengths, *k.stride()[:3], 1024)
    q8 = q.to(torch.float8_e4m3fn)
    kernel(q8, k, v, out, None,
           cutlass.Float32(wrapper._sm_scale * k_scale * math.log2(math.e)),
           cutlass.Float32(v_scale / 256.), lengths, qptr, table, None,
           cutlass.Int32(q.shape[0]), False)
    if _counts['native_calls'] == 0:
        # Fixed content-free marker; the supervisor records only GPU0/GPU1.
        print('EPHEMERAI_NATIVE_READY_DEVICE_' + str(q.device.index), flush=True)
    _counts['native_calls'] += 1
    _counts['native_query_tokens'] += q.shape[0]
    return out
