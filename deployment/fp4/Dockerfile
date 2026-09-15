# syntax=docker/dockerfile:1
FROM vllm/vllm-openai@sha256:c2914767605584b6d8f45686b82de173ecc99e781897aa3d0a66dacd72c51ae1 AS engine-deps
COPY deployment/fp4/requirements.lock /opt/ephemerai/requirements.lock
RUN --mount=type=bind,from=wheelhouse,target=/wheelhouse \
    python3 -m pip install --no-cache-dir --break-system-packages --no-deps \
      --no-index --find-links=/wheelhouse --require-hashes \
      -r /opt/ephemerai/requirements.lock && python3 -m pip check
FROM engine-deps AS final
COPY deployment/privacy/nodump.c /opt/ephemerai/nodump.c
RUN cc -shared -fPIC -O2 -Wall -Wextra -Werror -o /opt/ephemerai/libephemerai_nodump.so /opt/ephemerai/nodump.c
COPY deployment/fp4/qwen3_5.py deployment/fp4/upstream-patch.json deployment/fp4/apply_patch.py /opt/ephemerai/
RUN python3 /opt/ephemerai/apply_patch.py
COPY deployment/fp4/watchdog.py deployment/fp4/diagnostics.py deployment/fp4/supervise.py deployment/fp4/healthcheck.py deployment/fp4/launch.json deployment/fp4/model-files.json /opt/ephemerai/
COPY deployment/fp4/native /opt/ephemerai/native
COPY --from=native-object /native-nhd.o /opt/ephemerai/native/native-nhd.o
COPY --from=native-runtime /libcute_dsl_runtime-4.7.1.so /opt/ephemerai/native/libcute_dsl_runtime-4.7.1.so
RUN python3 /opt/ephemerai/native/apply_native.py
COPY deployment/fp4/numerics /opt/ephemerai/numerics
RUN python3 /opt/ephemerai/numerics/apply.py
ENV EPHEMERAI_FP8_UNSPLIT=1 VLLM_CACHE_ROOT=/root/.cache/ephemerai-numerics-v1
ENV PYTHONPATH=/opt/ephemerai/native EPHEMERAI_NATIVE_PREFILL=1
ENV LD_PRELOAD=/opt/ephemerai/libephemerai_nodump.so PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 VLLM_NO_USAGE_STATS=1 VLLM_DO_NOT_TRACK=1 VLLM_CONFIG_ROOT=/tmp/vllm
ENTRYPOINT ["python3", "/opt/ephemerai/supervise.py"]
CMD []
