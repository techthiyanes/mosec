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

"""MOSEC worker interface.

This module provides the interface to define a worker with such behaviors:

    1. initialize
    2. serialize/deserialize data to/from another worker
    3. serialize/deserialize data to/from the client side
    4. data processing
"""

import abc
import json
import pickle
from typing import Any, Sequence

from .errors import DecodingError, EncodingError


class Worker(abc.ABC):
    """MOSEC worker interface.

    It provides default IPC (de)serialization methods, stores the worker
    meta data including its stage and maximum batch size, and leaves the
    ``forward`` method to be implemented by the users.

    By default, we use `JSON <https://www.json.org/>`__ encoding. But users
    are free to customize via simply overriding the ``deserialize`` method
    in the **first** stage (we term it as *ingress* stage) and/or the
    ``serialize`` method in the **last** stage (we term it as *egress*
    stage).

    For the encoding customization, there are many choices including
    `MessagePack <https://msgpack.org/index.html>`__, `Protocol
    Buffer <https://developers.google.com/protocol-buffers>`__ and many
    other out-of-the-box protocols. Users can even define their own protocol
    and use it to manipulate the raw bytes! A naive customization can be
    found in this :doc:`PyTorch example </examples/pytorch>`.
    """

    # pylint: disable=no-self-use

    example: Any = None
    multi_examples: Sequence[Any] = []
    _worker_id: int = 0
    _stage: str = ""
    _max_batch_size: int = 1

    def __init__(self):
        """Initialize the worker.

        This method doesn't require the child class to override.
        """

    def serialize_ipc(self, data: Any) -> bytes:
        """Define IPC serialization method.

        Args:
            data: returned data from :py:meth:`forward`
        """
        return pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)

    def deserialize_ipc(self, data: bytes) -> Any:
        """Define IPC deserialization method.

        Args:
            data: input data for :py:meth:`forward`
        """
        return pickle.loads(data)

    @property
    def stage(self) -> str:
        """Return the stage name."""
        return self._stage

    @stage.setter
    def stage(self, stage):
        self._stage = stage

    @property
    def max_batch_size(self) -> int:
        """Return the maximum batch size."""
        return self._max_batch_size

    @max_batch_size.setter
    def max_batch_size(self, max_batch_size):
        self._max_batch_size = max_batch_size

    @property
    def worker_id(self) -> int:
        """Return the ID of this worker instance.

        This property returns the worker ID in the range of [1, ... , ``num``]
        (``num`` as configured in
        :py:meth:`append_worker(num) <mosec.server.Server.append_worker>`)
        to differentiate workers in the same stage.
        """
        return self._worker_id

    @worker_id.setter
    def worker_id(self, worker_id):
        self._worker_id = worker_id

    def serialize(self, data: Any) -> bytes:
        """Serialize the last stage (egress).

        Default response serialization method: JSON.

        Check :py:mod:`mosec.mixin` for more information.

        Arguments:
            data: the same type as the output of the :py:meth:`forward`

        Returns:
            the bytes you want to put into the response body

        Raises:
            EncodingError: if the data cannot be serialized with JSON
        """
        try:
            data_bytes = json.dumps(data, indent=2).encode()
        except Exception as err:
            raise EncodingError from err
        return data_bytes

    def deserialize(self, data: bytes) -> Any:
        """Deserialize the first stage (ingress).

        Default request deserialization method: JSON.

        Check :py:mod:`mosec.mixin` for more information.

        Arguments:
            data: the raw bytes extracted from the request body

        Returns:
            the same type as the input of the :py:meth:`forward`

        Raises:
            DecodingError: if the data cannot be deserialized with JSON
        """
        try:
            data_json = json.loads(data) if data else {}
        except Exception as err:
            raise DecodingError from err
        return data_json

    @abc.abstractmethod
    def forward(self, data: Any) -> Any:
        """Model inference, data processing or computation logic.

        Args:
            data: input data to be processed

        **Must be overridden** by the subclass.

        If any code in this :py:meth:`forward` needs to access other resources (e.g.
        a model, a memory cache, etc.), the user should initialize these resources
        as attributes of the class in the :py:class:`__init__ <mosec.worker.Worker>`.

        .. note::

            For a stage that enables dynamic batching, please return the results
            that have the same length and the same order of the input data.

        .. note::

            - for a single-stage worker, data will go through
                ``<deserialize> -> <forward> -> <serialize>``

            - for a multi-stage worker that is neithor `ingress` not `egress`, data
                will go through ``<deserialize_ipc> -> <forward> -> <serialize_ipc>``
        """
        raise NotImplementedError
