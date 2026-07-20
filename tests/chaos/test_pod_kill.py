"""ChaosMesh pod-kill test (placeholder).

These tests verify that the application recovers gracefully when
Kubernetes pods are randomly terminated. Requires a running k8s cluster
with ChaosMesh installed.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.chaos


@pytest.mark.skip(reason="ChaosMesh not yet configured")
class TestPodKill:
    """Verify application resilience under pod termination.

    Once ChaosMesh is configured in the test cluster, these tests should:
    - Deploy the application to a kind/k8s cluster
    - Use ChaosMesh NetworkChaos / PodChaos CRDs to kill pods
    - Verify that in-flight requests complete or return graceful errors
    - Verify that the deployment recovers within the expected SLA
    """

    def test_single_pod_kill_recovery(self):
        """Killing one pod should not cause data loss or extended downtime."""
        raise NotImplementedError

    def test_pod_kill_during_sse_stream(self):
        """SSE streams should handle pod termination with client-side retry."""
        raise NotImplementedError

    def test_pod_kill_during_auth_flow(self):
        """Auth register/login should survive a pod restart (stateless JWT)."""
        raise NotImplementedError

    def test_network_partition_recovery(self):
        """App should recover after a temporary network partition."""
        raise NotImplementedError
