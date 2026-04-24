from setuptools import find_packages, setup

package_name = 'cam_imu_sync'

setup(
    name=package_name,
    version='0.2.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch',
         ['launch/cam_imu_sync.launch.py']),
    ],
    install_requires=['setuptools'],
    tests_require=['pytest'],
    zip_safe=True,
    maintainer='gxxl',
    maintainer_email='gxxl@todo.todo',
    description='Camera-IMU time-offset synchronization node',
    license='MIT',
    entry_points={
        'console_scripts': [
            'sync_node = cam_imu_sync.sync_node:main',
        ],
    },
)
