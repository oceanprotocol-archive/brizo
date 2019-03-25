#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0

from setuptools import setup, find_packages

with open('README.md') as readme_file:
    readme = readme_file.read()

with open('HISTORY.md') as history_file:
    history = history_file.read()

# Installed by pip install ocean-brizo
# or pip install -e .
install_requirements = [
    # Install squid-py and all its dependencies first
    'squid-py==0.5.7',  # gets PyYAML, coloredlogs, web3
    'Flask==1.0.2',
    'Flask-Cors==3.0.6',
    'Flask-RESTful==0.3.6',
    'flask-swagger==0.2.13',
    'flask-swagger-ui==3.6.0',
    'gunicorn==19.9.0',
    'osmosis-azure-driver==0.0.4',
    'osmosis-aws-driver==0.0.2',
    'osmosis-driver-interface==0.0.6',
    'osmosis-on-premise-driver==0.0.6',
    'Werkzeug==0.14.1',
]

# Required to run setup.py:
setup_requirements = ['pytest-runner', ]

test_requirements = [
    'codacy-coverage',
    'coverage',
    'docker',
    'mccabe',
    'pylint',
    'pytest',
    'pytest-watch',
    'tox',
]

# Possibly required by developers of ocean-brizo:
dev_requirements = [
    'bumpversion',
    'pkginfo',
    'twine',
    'watchdog',
]

setup(
    author="leucothia",
    author_email='devops@oceanprotocol.com',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    description="🐳 Ocean Brizo.",
    extras_require={
        'test': test_requirements,
        'dev': dev_requirements + test_requirements,
    },
    install_requires=install_requirements,
    license="Apache Software License 2.0",
    long_description=readme,
    long_description_content_type="text/markdown",
    include_package_data=True,
    keywords='ocean-brizo',
    name='ocean-brizo',
    packages=find_packages(include=['brizo', 'brizo.app']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/oceanprotocol/brizo',
    version='0.2.10',
    zip_safe=False,
)
