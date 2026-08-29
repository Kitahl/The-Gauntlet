"""Constants for the Gauntlet-owned isolated runtime boundary."""

from pathlib import Path

HOST_PROTOCOL_VERSION = "gauntlet.worker.v1"
WORKER_REQUEST_TYPE = "worker.request"
WORKER_RESULT_TYPE = "worker.result"
ADAPTER_PROTOCOL_VERSION = "gauntlet.adapter.v1"
OBSERVATION_PROTOCOL_VERSION = "gauntlet.tool-observation.v1"
FINALIZATION_PROTOCOL_VERSION = "gauntlet.finalization.v1"
MAX_JSONL_BYTES = 1_048_576
MAX_OPERATIONAL_ERROR_CHARS = 2_000

DEFAULT_LAUNCH_TIMEOUT_SECONDS = 180.0
MAX_LAUNCH_TIMEOUT_SECONDS = 600.0
DEFAULT_AGENT_RUN_BUDGET_SECONDS = 120.0
MAX_AGENT_RUN_BUDGET_SECONDS = 300.0
DEFAULT_ADAPTER_TIMEOUT_SECONDS = 20.0
DEFAULT_OBSERVATION_TIMEOUT_SECONDS = 10.0

GAUNTLET_PLUGIN_ID = "gauntlet"
GAUNTLET_TOOLSET = "gauntlet"
GAUNTLET_STATUS_TOOLS = (
    "gauntlet_task_status",
    "gauntlet_release_status",
)

REPO_ROOT = Path(__file__).resolve().parent.parent
HOST_ROOT = REPO_ROOT / "gauntlet_host"
VENDOR_ROOT = REPO_ROOT / "vendor" / "hermes-agent"
VENDOR_TOOLS_ROOT = VENDOR_ROOT / "tools"
GAUNTLET_TOOLS_ROOT = REPO_ROOT / "tools"
WORKER_MAIN = HOST_ROOT / "worker_main.py"
MODULE_CLI = HOST_ROOT / "module_cli.py"
OBSERVATION_BRIDGE = HOST_ROOT / "observation_bridge.py"
FINALIZER = HOST_ROOT / "finalizer.py"
GAUNTLET_PLUGIN_SOURCE = HOST_ROOT / "gauntlet_plugin.py"
VENDOR_SNAPSHOT_MANIFEST = REPO_ROOT / "vendor" / "HERMES_SNAPSHOT.json"

EXPECTED_HERMES_REPOSITORY = "NousResearch/hermes-agent"
EXPECTED_HERMES_TAG = "v2026.8.27"
EXPECTED_HERMES_COMMIT = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
