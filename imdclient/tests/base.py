from imdclient.IMDClient import IMDClient
import pytest
from pathlib import Path
import os
import signal
import subprocess
import time
import MDAnalysis as mda
from MDAnalysisTests.coordinates.base import assert_timestep_almost_equal
from numpy.testing import (
    assert_array_almost_equal,
    assert_almost_equal,
    assert_allclose,
)
import numpy as np

import logging

logger = logging.getLogger("imdclient.IMDClient")


def assert_allclose_with_logging(a, b, rtol=1e-07, atol=0, equal_nan=False):
    """
    Custom function to compare two arrays element-wise, similar to np.testing.assert_allclose,
    but logs all non-matching values.

    Parameters:
    a, b : array_like
        Input arrays to compare.
    rtol : float
        Relative tolerance.
    atol : float
        Absolute tolerance.
    equal_nan : bool
        Whether to compare NaNs as equal.
    """
    # Convert inputs to numpy arrays
    a = np.asarray(a)
    b = np.asarray(b)

    # Compute the absolute difference
    diff = np.abs(a - b)

    # Check if values are within tolerance
    not_close = diff > (atol + rtol * np.abs(b))

    # Check if there are any NaNs and handle them if necessary
    if equal_nan:
        nan_mask = np.isnan(a) & np.isnan(b)
        not_close &= ~nan_mask

    # Log all the values that are not close
    if np.any(not_close):
        print("The following values do not match within tolerance:")
        for idx in np.argwhere(not_close):
            logger.debug(
                f"a[{tuple(idx)}]: {a[tuple(idx)]}, b[{tuple(idx)}]: {b[tuple(idx)]}, diff: {diff[tuple(idx)]}"
            )
        # Optionally raise an error after logging if you want it to behave like assert
        raise AssertionError("Arrays are not almost equal.")
    else:
        print("All values are within tolerance.")


class IMDv3IntegrationTest:

    @pytest.fixture()
    def run_sim_and_wait(self, command, match_string, simulation):
        p = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            text=True,
            bufsize=0,
            preexec_fn=os.setsid,
        )
        t = time.time()

        for stdout_line in iter(p.stdout.readline, ""):
            logger.debug(f"stdout: {stdout_line}")
            if match_string in stdout_line:

                break
            if time.time() - t > 10:
                raise TimeoutError("Timeout waiting for match string")

        logger.debug("Match string found")
        yield p
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)

    @pytest.fixture()
    def simulation(self, tmp_path):
        old_cwd = Path.cwd()
        os.chdir(tmp_path)
        yield
        os.chdir(old_cwd)

    @pytest.fixture()
    def client(self, run_sim_and_wait, universe):
        client = IMDClient("localhost", 8888, universe.trajectory.n_atoms)
        yield client
        client.stop()

    def test_compare_imd_to_true_traj(self, universe, client, first_frame):
        imdsinfo = client.get_imdsessioninfo()

        for ts in universe.trajectory[first_frame:]:
            imdf = client.get_imdframe()
            if imdsinfo.time:
                assert_allclose(imdf.time, ts.time)
                assert_allclose(imdf.step, ts.data["step"])
            if imdsinfo.box:
                assert_allclose_with_logging(
                    imdf.box,
                    ts.triclinic_dimensions,
                    atol=1e-02,
                )
            if imdsinfo.positions:
                assert_allclose_with_logging(
                    imdf.positions, ts.positions, atol=1e-02
                )
            if imdsinfo.velocities:
                assert_allclose_with_logging(
                    imdf.velocities, ts.velocities, atol=1e-02
                )
            if imdsinfo.forces:
                assert_allclose_with_logging(imdf.forces, ts.forces, atol=1e-02)

        # imdf = client.get_imdframe()
        # if imdsinfo.time:
        #     assert_allclose(imdf.time, universe.trajectory[1].time)
        #     assert_allclose(imdf.step, universe.trajectory[1].data["step"])
        # if imdsinfo.box:
        #     assert_allclose_with_logging(
        #         imdf.box,
        #         universe.trajectory[1].triclinic_dimensions,
        #         atol=1e-03,
        #     )
        # if imdsinfo.positions:
        #     assert_allclose_with_logging(
        #         imdf.positions, universe.trajectory[1].positions, atol=1e-03
        #     )
        # if imdsinfo.velocities:
        #     assert_allclose_with_logging(
        #         imdf.velocities, universe.trajectory[1].velocities, atol=1e-03
        #     )
        # if imdsinfo.forces:
        #     assert_allclose_with_logging(
        #         imdf.forces, universe.trajectory[1].forces, atol=1e-03
        #     )
