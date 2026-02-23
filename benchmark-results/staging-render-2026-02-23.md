# Staging Render Benchmark (2026-02-23)

- Workflow: `Benchmark Staging Render`
- Run ID: `22292838681`
- Commit: `5e85039`
- Host class: staging VPS (`8 vCores / 24 GB RAM`)
- Sample duration per case: `8s`
- Cases executed: `26`
- Failed cases: `0`

## Main Matrix (Maps Off, Source FPS)

| Resolution | Profile | Output | Elapsed (s) | Wall vs Realtime |
| --- | --- | --- | ---: | ---: |
| 720p | h264-fast | 1280x720 | 6.711 | 0.839x |
| 720p | h264-source | 1280x720 | 7.465 | 0.933x |
| 720p | h264-4k-compat | 1280x720 | 6.934 | 0.867x |
| 1080p | h264-fast | 1920x1080 | 9.452 | 1.182x |
| 1080p | h264-source | 1920x1080 | 9.850 | 1.231x |
| 1080p | h264-4k-compat | 1920x1080 | 10.176 | 1.272x |
| 2.7K | h264-fast | 2704x1520 | 17.117 | 2.140x |
| 2.7K | h264-source | 2704x1520 | 17.930 | 2.241x |
| 2.7K | h264-4k-compat | 2704x1520 | 20.127 | 2.516x |
| 4K | h264-fast | 3840x2160 | 28.142 | 3.518x |
| 4K | h264-source | 3840x2160 | 30.317 | 3.790x |
| 4K | h264-4k-compat | 3840x2160 | 29.583 | 3.698x |
| 5.3K | h264-fast | 5312x2988 | 86.208 | 10.776x |
| 5.3K | h264-source | 5312x2988 | 91.213 | 11.402x |
| 5.3K | h264-4k-compat | 3840x2160 | 89.670 | 11.209x |

## Key Findings

- `h264-4k-compat` does export 5.3K inputs at 4K output (`3840x2160`), but render time stayed close to 5.3K source profile timing on this host.
- Throughput is close to realtime at 720p, slightly above realtime at 1080p, and degrades steeply from 4K to 5.3K.
- Maps-enabled runs were near-neutral versus maps-off in this short-run benchmark (cache/warm-state likely dominates).
- `fixed 15 fps` reduced elapsed time compared to source-exact in both 1080p and 5.3K tests.

