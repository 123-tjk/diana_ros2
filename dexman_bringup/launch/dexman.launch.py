"""Bring up the Dexman dual-arm robot.

One robot description contains both Diana arms and the DexH13 hands.
Each arm has its own ros2_control hardware interface, IP, and prefix.
"""

import os
import tempfile

import xacro
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, Shutdown
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def _load_config(path):
    with open(path, 'r', encoding='utf-8') as stream:
        config = yaml.safe_load(stream)
    for key in ('robot_type', 'left', 'right', 'left_hand', 'right_hand'):
        if key not in config:
            raise RuntimeError(f'dexman config {path} is missing "{key}"')
    for side in ('left', 'right'):
        for field in ('arm_prefix', 'robot_ip'):
            if field not in config[side]:
                raise RuntimeError(
                    f'dexman config {path} is missing "{side}.{field}"'
                )
    return config


def _as_bool_string(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value).lower()


def generate_robot_nodes(context):
    config_path = LaunchConfiguration('robot_config_file').perform(context)
    config = _load_config(config_path)

    robot_type = LaunchConfiguration('robot_type').perform(context) or str(
        config['robot_type']
    )
    left_robot_ip = LaunchConfiguration('left_robot_ip').perform(context) or str(
        config['left']['robot_ip']
    )
    right_robot_ip = LaunchConfiguration('right_robot_ip').perform(context) or str(
        config['right']['robot_ip']
    )
    use_fake_hardware = _as_bool_string(
        LaunchConfiguration('use_fake_hardware').perform(context)
        or config.get('use_fake_hardware', 'false')
    )
    fake_sensor_commands = _as_bool_string(
        config.get('fake_sensor_commands', 'false')
    )
    use_rviz = _as_bool_string(
        LaunchConfiguration('use_rviz').perform(context)
        or config.get('use_rviz', 'true')
    )
    use_hands = _as_bool_string(
        LaunchConfiguration('use_hands').perform(context)
        or config.get('use_hands', 'false')
    )
    left_prefix = str(config['left']['arm_prefix'])
    right_prefix = str(config['right']['arm_prefix'])
    if left_prefix == right_prefix:
        raise RuntimeError(
            f'left and right arm_prefix must differ, both are "{left_prefix}"'
        )

    urdf_path = os.path.join(
        get_package_share_directory('dexman_bringup'),
        'urdf',
        'dexman.urdf.xacro',
    )
    robot_description = xacro.process_file(
        urdf_path,
        mappings={
            'robot_type': robot_type,
            'left_robot_ip': left_robot_ip,
            'right_robot_ip': right_robot_ip,
            'use_fake_hardware': use_fake_hardware,
            'fake_sensor_commands': fake_sensor_commands,
            'use_hands': use_hands,
            'left_hand': str(config['left_hand']),
            'right_hand': str(config['right_hand']),
        },
    ).toxml()

    controllers_yaml = PathJoinSubstitution(
        [FindPackageShare('dexman_bringup'), 'config', 'controllers.yaml']
    ).perform(context)
    # arm_prefix and robot_type come from the bringup config, so a config edit
    # stays aligned with the URDF without editing controllers.yaml.
    broadcaster_params = {
        'left_diana_robot_state_broadcaster': {
            'ros__parameters': {
                'robot_type': robot_type,
                'arm_prefix': left_prefix,
                'convenience_publish_rate': 1000,
            }
        },
        'right_diana_robot_state_broadcaster': {
            'ros__parameters': {
                'robot_type': robot_type,
                'arm_prefix': right_prefix,
                'convenience_publish_rate': 1000,
            }
        },
    }
    overlay = tempfile.NamedTemporaryFile(
        mode='w', prefix='dexman_controllers_', suffix='.yaml', delete=False
    )
    yaml.safe_dump(broadcaster_params, overlay)
    overlay.close()

    nodes = [
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_description}],
        ),
        Node(
            package='controller_manager',
            executable='ros2_control_node',
            output='screen',
            parameters=[
                {'robot_description': robot_description},
                controllers_yaml,
            ],
            on_exit=Shutdown(),
        ),
        Node(
            package='controller_manager',
            executable='spawner',
            output='screen',
            arguments=[
                'joint_state_broadcaster',
                '--controller-manager-timeout',
                '60',
                '--param-file',
                controllers_yaml,
            ],
        ),
        Node(
            package='controller_manager',
            executable='spawner',
            output='screen',
            arguments=[
                'left_diana_robot_state_broadcaster',
                'right_diana_robot_state_broadcaster',
                '--controller-manager-timeout',
                '60',
                '--param-file',
                controllers_yaml,
                '--param-file',
                overlay.name,
            ],
            condition=UnlessCondition(use_fake_hardware),
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            arguments=[
                '--display-config',
                PathJoinSubstitution(
                    [
                        FindPackageShare('dexman_description'),
                        'rviz',
                        'urdf.rviz',
                    ]
                ),
            ],
            condition=IfCondition(use_rviz),
        ),
    ]
    return nodes


def generate_launch_description():
    default_config = PathJoinSubstitution(
        [FindPackageShare('dexman_bringup'), 'config', 'dexman.config.yaml']
    )
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                'robot_config_file',
                default_value=default_config,
                description='Dual-arm bringup config. IPs and prefixes live here.',
            ),
            DeclareLaunchArgument(
                'robot_type',
                default_value='',
                description='Override robot_type from the config file.',
            ),
            DeclareLaunchArgument(
                'left_robot_ip',
                default_value='',
                description='Override the left arm IP. Default is 192.168.20.2.',
            ),
            DeclareLaunchArgument(
                'right_robot_ip',
                default_value='',
                description='Override the right arm IP. Default is 192.168.20.3.',
            ),
            DeclareLaunchArgument(
                'use_fake_hardware',
                default_value='',
                description='Override use_fake_hardware from the config file.',
            ),
            DeclareLaunchArgument(
                'use_rviz',
                default_value='',
                description='Override use_rviz from the config file.',
            ),
            DeclareLaunchArgument(
                'use_hands',
                default_value='',
                description='Override use_hands from the config file.',
            ),
            OpaqueFunction(function=generate_robot_nodes),
        ]
    )
