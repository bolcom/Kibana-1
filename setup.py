from setuptools import setup

setup(
    name='kibana',
    version='0.1',
    description='Kibana configuration index (.kibana in v4) command line interface and python API (visualization import/export and mappings refresh)',
    author='Ryan Farley',
    author_email='rfarley@mitre.org',
    packages=['kibana'],
    install_requires=(
        'elasticsearch',
        'requests>=2.5.0',
    )
)