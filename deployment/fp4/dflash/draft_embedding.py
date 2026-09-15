"""Draft-only INT4 embedding storage; target stage0 embeddings/head unchanged.

Pinned DFlash2/PP2/TP1 only. Group32 symmetric INT4 with FP16 scales, fused
GPU gather to BF16, exact BF16 mask row. CPU staging occurs only at load time.
"""

import os
import torch
import triton
import triton.language as tl


def maybe_convert(root, config):
    if os.environ.get("EPHEMERAI_DFLASH_EMBEDDING_INT4") != "1":
        return
    from vllm.distributed import get_pp_group

    if get_pp_group().is_first_rank:
        return
    assert get_pp_group().is_last_rank and get_pp_group().world_size == 2
    p = config.parallel_config
    s = config.speculative_config
    assert p.pipeline_parallel_size == 2 and p.tensor_parallel_size == 1
    assert s is not None and s.method == "dflash" and config.lora_config is None
    hf = s.draft_model_config.hf_config
    assert "DFlash2DraftModel" in hf.architectures, hf.architectures
    assert os.environ.get("EPHEMERAI_DFLASH_SHARED_MODULES") == "1"
    assert type(root).__name__ == "Qwen3_5ForConditionalGeneration"
    lang = root.language_model
    embedding = lang.model.embed_tokens
    assert type(embedding).__name__ == "VocabParallelEmbedding"
    assert embedding.weight.is_contiguous() and embedding.weight.stride() == (5120, 1)
    assert not embedding.weight.requires_grad
    assert not hasattr(embedding, "_draft_row_scale"), "Duplicate conversion"
    assert lang.config.num_hidden_layers == 64
    embed_ptr = embedding.weight.untyped_storage().data_ptr()
    assert all(
        p is embedding.weight or p.untyped_storage().data_ptr() != embed_ptr
        for p in root.parameters()
    )
    assert not lang.config.tie_word_embeddings
    assert tuple(embedding.weight.shape) == (248320, 5120)
    assert all(
        embedding.weight.untyped_storage().data_ptr() != p.untyped_storage().data_ptr()
        for p in lang.lm_head.parameters()
    )
    draft_cfg = getattr(hf, "dflash_config", {})
    mask_id = draft_cfg.get("mask_token_id", getattr(hf, "mask_token_id", None))
    assert isinstance(mask_id, int)
    result = convert_int4(embedding, mask_id)
    print("EPHEMERAI_DRAFT_EMBEDDING_QUANTIZED", result, flush=True)


@triton.jit
def _gather_int4(
    W,
    S,
    M,
    Ids,
    Out,
    N: tl.constexpr,
    H: tl.constexpr,
    G: tl.constexpr,
    MASK_ID: tl.constexpr,
    B: tl.constexpr,
):
    x = tl.program_id(0) * B + tl.arange(0, B)
    token = tl.load(Ids + x // H, x < N * H, other=0)
    col = x % H
    packed = tl.load(W + token * (H // 2) + col // 2, x < N * H, other=136).to(tl.int32)
    quant = ((packed >> ((col % 2) * 4)) & 15) - 8
    scale = tl.load(S + token * (H // G) + col // G, x < N * H, other=1.0).to(
        tl.float32
    )
    exact = tl.load(M + col, x < N * H, other=0).to(tl.float32)
    value = tl.where(token == MASK_ID, exact, quant.to(tl.float32) * scale)
    tl.store(Out + x, value, x < N * H)


class DraftInt4Embedding:
    def embedding(self, layer, input_ids):
        if not input_ids.is_contiguous():
            input_ids = input_ids.contiguous()
        h = layer._draft_hidden_size
        out = torch.empty(
            (*input_ids.shape, h), device=input_ids.device, dtype=torch.bfloat16
        )
        n = input_ids.numel()
        if n:
            _gather_int4[(triton.cdiv(n * h, 1024),)](
                layer.weight,
                layer._draft_row_scale,
                layer._draft_mask_row,
                input_ids,
                out,
                n,
                h,
                layer._draft_group_size,
                layer._draft_mask_id,
                1024,
            )
        return out


def convert_int4(layer, mask_id, group_size=32):
    weight = layer.weight
    assert weight.dtype == torch.bfloat16 and weight.is_cuda and weight.ndim == 2
    rows, h = weight.shape
    device = weight.device
    assert h % group_size == 0 and h % 2 == 0 and 0 <= mask_id < rows
    exact = weight[mask_id].clone()
    packed = torch.empty((rows, h // 2), dtype=torch.uint8, device="cpu")
    scales = torch.empty((rows, h // group_size), dtype=torch.float16, device="cpu")
    for start in range(0, rows, 512):
        chunk = weight[start : start + 512].to(device="cpu", dtype=torch.float32)
        if not torch.isfinite(chunk).all():
            raise ValueError("Nonfinite draft embedding weights")
        groups = chunk.reshape(len(chunk), h // group_size, group_size)
        maximum = groups.abs().amax(dim=-1)
        scale = torch.where(
            maximum == 0, 1.0, (maximum / 7.0).clamp_min(2.0**-24)
        ).half()
        if not torch.isfinite(scale).all():
            raise ValueError("Invalid draft embedding scale")
        quant = (
            torch.round(groups / scale.float()[..., None])
            .clamp(-7, 7)
            .reshape(len(chunk), h)
            .to(torch.int16)
            + 8
        )
        packed[start : start + len(chunk)] = (
            quant[:, 0::2] | (quant[:, 1::2] << 4)
        ).to(torch.uint8)
        scales[start : start + len(chunk)] = scale
    old_bytes = weight.untyped_storage().nbytes()
    del layer._parameters["weight"]
    del weight
    torch.cuda.empty_cache()
    layer.register_parameter(
        "weight", torch.nn.Parameter(packed.to(device), requires_grad=False)
    )
    layer.register_buffer("_draft_row_scale", scales.to(device))
    layer.register_buffer("_draft_mask_row", exact)
    layer._draft_mask_id = mask_id
    layer._draft_group_size = group_size
    layer._draft_hidden_size = h
    layer.quant_method = DraftInt4Embedding()
    torch.cuda.synchronize()
    return {
        "old_bytes": old_bytes,
        "new_bytes": layer.weight.nbytes + layer._draft_row_scale.nbytes + exact.nbytes,
        "mask_id": mask_id,
        "dtype": "symmetric_int4",
        "group_size": group_size,
        "scale_dtype": "float16",
        "output_dtype": "bfloat16",
    }
