"""Expand the Dexman xacro and write the URDF into the package root."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.logging import get_logger
from launch.substitutions import LaunchConfiguration
import xacro


def package_root(share_dir):
    """Return the dexman_description directory that contains package.xml.

    A symlink install already points at the source tree. A copied install
    lives under install/, so walk up to the workspace checkout.
    """
    real_share = os.path.realpath(share_dir)
    if os.path.isfile(os.path.join(real_share, "CMakeLists.txt")):
        return real_share

    xacro_path = os.path.realpath(
        os.path.join(share_dir, "robots", "dexman", "dexman.urdf.xacro")
    )
    source_from_xacro = os.path.abspath(
        os.path.join(os.path.dirname(xacro_path), os.pardir, os.pardir)
    )
    if os.path.isfile(os.path.join(source_from_xacro, "CMakeLists.txt")):
        return source_from_xacro

    current = real_share
    for _ in range(6):
        parent = os.path.dirname(current)
        candidate = os.path.join(parent, "dexman_description")
        if os.path.isfile(os.path.join(candidate, "CMakeLists.txt")) and os.path.isfile(
            os.path.join(candidate, "package.xml")
        ):
            return os.path.realpath(candidate)
        if parent == current:
            break
        current = parent
    return real_share


def _generate(context, *_args, **_kwargs):
    share = get_package_share_directory("dexman_description")
    xacro_path = os.path.join(share, "robots", "dexman", "dexman.urdf.xacro")
    output = LaunchConfiguration("output").perform(context).strip()
    if not output:
        output = os.path.join(package_root(share), "dexman.urdf")
    output = os.path.abspath(os.path.expanduser(output))

    # left_hand and right_hand stay at the defaults in dexman.urdf.xacro.
    document = xacro.process_file(xacro_path)
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w", encoding="utf-8") as stream:
        stream.write(document.toprettyxml(indent="  "))
    get_logger("dexman_description.generate_urdf").info(f"Wrote expanded URDF to {output}")
    return []


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            "output",
            default_value="",
            description="Expanded URDF path. Empty writes dexman.urdf in the package root.",
        ),
        OpaqueFunction(function=_generate),
    ])
