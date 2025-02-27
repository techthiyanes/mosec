# Copyright 2022 MOSEC Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Command line arguments.

Arguments parsing for two parts:

    * prepared for the Rust service part
    * consumed by the Python worker part
"""

import argparse
import errno
import os
import random
import socket
import tempfile
import warnings

from .env import get_env_namespace


def is_port_available(addr: str, port: int) -> bool:
    """Check if the port is available to use."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    err = sock.connect_ex((addr, port))
    sock.close()
    # https://docs.python.org/3/library/errno.html
    if 0 == err:
        return False
    if errno.ECONNREFUSED == err:
        return True
    raise RuntimeError(
        f"Check {addr}:{port} socket connection err: {err}{errno.errorcode[err]}"
    )


def parse_arguments() -> argparse.Namespace:
    """Parse user configurations."""
    parser = argparse.ArgumentParser(
        description="Mosec Server Configurations",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="The following arguments can be set through environment variables: "
        "(path, capacity, timeout, address, port, namespace, debug, dry_run). "
        "Note that the environement variable should start with `MOSEC_` with upper "
        "case. For example: `MOSEC_PORT=8080 MOSEC_TIMEOUT=5000 python main.py`.",
    )

    parser.add_argument(
        "--path",
        help="Unix Domain Socket address for internal Inter-Process Communication",
        type=str,
        default=os.path.join(
            tempfile.gettempdir(), f"mosec_{random.randrange(2**32):x}"
        ),
    )

    parser.add_argument(
        "--capacity",
        help="Capacity of the request queue, beyond which new requests will be "
        "rejected with status 429",
        type=int,
        default=1024,
    )

    parser.add_argument(
        "--timeout",
        help="Service timeout for one request (milliseconds)",
        type=int,
        default=3000,
    )

    parser.add_argument(
        "--wait",
        help="[deprecated] Wait time for the batcher to batch (milliseconds)",
        type=int,
        default=10,
    )

    parser.add_argument(
        "--address",
        help="Address of the HTTP service",
        type=str,
        default="0.0.0.0",
    )

    parser.add_argument(
        "--port",
        help="Port of the HTTP service",
        type=int,
        default=8000,
    )

    parser.add_argument(
        "--namespace",
        help="Namespace for prometheus metrics",
        type=str,
        default="mosec_service",
    )

    parser.add_argument(
        "--debug",
        help="Enable log format",
        action="store_true",
    )

    parser.add_argument(
        "--dry-run",
        help="Dry run the service with provided warmup examples (if any). "
        "This will omit the worker number for each stage.",
        action="store_true",
    )

    args, _ = parser.parse_known_args(namespace=get_env_namespace())

    if args.wait != 10:
        warnings.warn(
            "`--wait` is deprecated and will be removed in v1, please configure"
            "the `max_wait_time` on `Server.append_worker`",
            DeprecationWarning,
        )

    if not is_port_available(args.address, args.port):
        raise RuntimeError(
            f"{args.address}:{args.port} is in use. "
            "Please change to a free one (use `--port`)."
        )

    return args


mosec_args = parse_arguments()
