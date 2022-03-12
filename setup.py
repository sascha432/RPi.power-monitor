#
# Author: sascha_lammers@gmx.de
#

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='INA3221 Power Monitor',
    version="0.0.2",
    author="Sascha Lammers",
    author_email="sascha_lammers@gmx.de",
    packages=setuptools.find_packages(),
    url='https://github.com/sascha432/RPi.power-monitor',
    description='Power Monitor for the INA3221 sensor with headless mode, TCP server/client and tkinter GUI running on Linux/Raspberry Pi and Windows',
    # long_description=open('README.md').read(),
    install_requires=[
        "numpy>=1.19.4",
        "smbus>=1.1.post2",
        "matplotlib>=3.3.1",
        "commentjson>=0.9.0",
        "paho-mqtt>=1.5.1",
        "colorlog>=4.6.2",
        "influxdb>=5.3.1",
        "beeprint>=2.4.10"
    ],
    # dependency_links=[
    #     "git+git://github.com/Peter92/unit-convert.git"
    # ],
    include_package_data=True,
)
