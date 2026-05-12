# Native Circle Graph Generators

The native generator CLI is exposed through:

```bash
three_col_native instance generate
three_col_native instance generate-sequence
```

## Families

- `rc_fast`: prior-work compatible connected `K4`-free circle graph generator.
- `rcy_fast`: prior-work compatible connected yes-instance generator with a maintained coloring.
- `rccy_alpha`: parameterized constructive yes-instance generator.
- `rccy_alpha0`: alias for `rccy_alpha --alpha 0`.
- `rccy_alpha1`: alias for `rccy_alpha --alpha 1`.

The older constructive variants `rccy_tuned`,
`rccy_full_sweep_weighted_active`, and `rccy_full_sweep_max_active` are still
accepted for compatibility, but new experiments should prefer `rccy_alpha`.

## `rccy_alpha`

`rccy_alpha` constructs connected circle graphs that are colorable with the
configured number of colors.

For each inserted chord:

1. Choose the first endpoint insertion gap uniformly.
2. Sweep once around the endpoint order and maintain counters for the colors of
   currently crossed chords.
3. A second endpoint gap is feasible if it crosses at least one chord and at
   least one color is unused among the crossed neighbors.
4. Choose a feasible second endpoint with probability proportional to
   `crossed_chords^alpha`.
5. Choose the new chord color uniformly among the available colors.

Special cases:

- `alpha = 0`: uniform choice among feasible second endpoints.
- `alpha = 1`: linear density bias.
- `alpha > 1`: stronger density bias.

Example:

```bash
three_col_native instance generate \
  --family rccy_alpha \
  --alpha 0.5 \
  --n 1000 \
  --seed 1 \
  --output instances/rccy_alpha-alpha0p5-k03-n1000-seed1.col
```

## Output Formats

Use `--output-format col|circle`.

- `col` writes a DIMACS edge list with circle metadata comments. Generic graph
  coloring tools can read the edge list.
- `circle` writes the same metadata and endpoint order with a compact
  `p circle n m` problem line and no `e u v` edge lines. This is intended for
  circle-aware native tools and avoids writing very large dense edge lists.

Example compact output:

```bash
three_col_native instance generate \
  --family rccy_alpha \
  --alpha 1 \
  --n 10000 \
  --seed 1 \
  --output-format circle \
  --output instances/rccy_alpha-alpha1-k03-n10000-seed1.circle
```

## Benchmark Specs

Parameterized generators use instance `params`, analogous to solver `params`:

```json
{
  "family": "rccy_alpha",
  "label": "Dense-Yes",
  "params": {"alpha": 1},
  "output_format": "circle",
  "num_colors": 3,
  "n_values": [100, 1000, 10000],
  "seeds": [1, 2, 3]
}
```

The instance id includes canonical generator parameters, for example:

```text
rccy_alpha-alpha0p5-k03-n10000-seed1
```
