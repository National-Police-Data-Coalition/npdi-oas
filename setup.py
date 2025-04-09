from setuptools import setup

# read the contents of your README file
from pathlib import Path
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name='npdi_oas',
    version='0.0.4',
    packages=['npdi_oas'],
    package_dir={'npdi_oas': 'src_gen'},
    url='https://github.com/codeforboston/police-data-trust/tree/main/oas',
    license='',
    author='zganger',
    author_email='zganger@icloud.com',
    description='OpenAPI spec for NPDI data models',
    long_description=long_description,
    long_description_content_type='text/markdown',
    install_requires=["pydantic"]
)
