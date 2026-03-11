# Local Probe Integration

## Purpose

This resource shows the supported way to sample a function-local STM32 variable from the host side.

ELF debug info alone is not enough to recover a live stack variable address reliably from a running task. The supported pattern is:

1. Add one global probe slot in firmware.
2. In the target function or task, publish `&local_var` into that slot every loop.
3. On the host, use `data_acq.py --pointer-symbol ... --seq-symbol ...` to read the slot and then sample the pointed value.

## Firmware Integration

Add the resource files to your module or app layer:

- `local_probe_runtime.h`
- `local_probe_runtime.c`

Example:

```c
#include "local_probe_runtime.h"

BFD_LOCAL_PROBE_DEFINE_SLOT(g_stack_probe_slot);

void SomeTask(void *argument)
{
    volatile float local_value = 0.0f;
    volatile uint32_t counter = 0U;

    (void)argument;
    BfdLocalProbeInit(&g_stack_probe_slot);

    for (;;)
    {
        counter++;
        local_value = ((float)(counter % 400U) - 200.0f) * 0.125f;
        BfdLocalProbePublish(&g_stack_probe_slot, &local_value, sizeof(local_value), BFD_LOCAL_PROBE_TYPE_F32);
        osDelay(10);
    }
}
```

Expected exported symbols:

- `g_stack_probe_slot`
- `g_stack_probe_slot.addr`
- `g_stack_probe_slot.seq`

If your toolchain does not expose struct fields as standalone symbols, define separate global aliases or a wrapper struct that the host script can resolve directly.

## Host Capture

Non-stop capture:

```bash
python3 ./.codex/skills/bfd-data-acquisition/scripts/data_acq.py \
  --elf builds/gcc/debug/RSCF_A.elf \
  --pointer-symbol g_local_probe_addr \
  --seq-symbol g_local_probe_seq \
  --layout f32x1 \
  --count 20 \
  --interval-ms 20 \
  --max-retries 10 \
  --mode nonstop \
  --output logs/data_acq/local_probe_nonstop.csv
```

Snapshot capture:

```bash
python3 ./.codex/skills/bfd-data-acquisition/scripts/data_acq.py \
  --elf builds/gcc/debug/RSCF_A.elf \
  --pointer-symbol g_local_probe_addr \
  --seq-symbol g_local_probe_seq \
  --layout f32x1 \
  --count 8 \
  --interval-ms 20 \
  --max-retries 10 \
  --mode snapshot \
  --output logs/data_acq/local_probe_snapshot.csv
```

## Notes

- `nonstop` keeps the target running and is preferred for live observation.
- `snapshot` halts briefly, so use it only when an intrusive capture is acceptable.
- The `seq` field must be even and unchanged before/after the pointed-value read.
