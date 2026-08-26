# RPS v0.6.1 small shadow attempt — stopped before predictions

Outcome: `INVALID_SCHEMA / NO_BENCHMARK_RESULT`

The first Terra Low positive-control request returned HTTP 400 because the live
structured-output validator does not permit `uniqueItems` on the `hinges` array.
The public failed receipt records no answer and zero usage. Its stderr digest is
`adc1610256464b277edfe62032c90a6ac085855cf7e2cc252dc54f6f34561af8`.

The preregistered no-retry rule was followed: the original output directory was
not reused and no HLE observer call ran. A separately named schema-fixed revision
removes only the unsupported schema keyword while retaining the identical
uniqueness check in the Python parser.
