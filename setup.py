from setuptools import setup, find_packages, Command

version = __import__("thermostat_nw").get_version()

long_description = """
This is a fork of EPA's Connected Thermostat library (https://github.com/EPAENERGYSTAR/epathermostat), 
intended to calculate connected thermostat temperature and run-time savings. This version adds 
several metrics that are being used to evaluate real-world smart thermostat savings in the Northwestern USA.
"""


setup(
    name="thermostat_nw",
    version=version,
    description="Calculate connected thermostat savings",
    long_description=long_description,
    url="https://github.com/hshaban/epathermostat_nw",
    author="Empower Dataworks + Apex Analytics. Forked from https://github.com/EPAENERGYSTAR/epathermostat.",
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    keywords="thermostat savings EPA",
    packages=find_packages(),
    package_data={"": ["*.csv", "*.json"]},
    install_requires=[
        "eemeter==2.5.2",
        "eeweather==0.3.24",
        "pandas==0.25.3",
        "numpy==1.19.4",
        "sqlalchemy==1.3.1",
        "zipcodes==1.1.2",
    ],
)
